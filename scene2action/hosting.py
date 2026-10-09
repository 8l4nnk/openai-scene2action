"""Authenticated HTTPS gateway, used only by the explicit hosted entry point."""
import hashlib
import hmac
import os
import re
import secrets
import time
from collections import deque
from http.cookies import CookieError, SimpleCookie
from urllib.parse import parse_qs

from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .app import create_app

SESSION_COOKIE = '__Host-s2a_session'
SESSION_SECONDS = 28800
LOGIN_HTML = '''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scene2Action · 로그인</title><link rel="stylesheet" href="/login.css"></head>
<body><main><div class="brand">S2A</div><p class="label">K-Scene2Action · AWS</p>
<h1>실행 검증 워크스페이스</h1><p>팀 전용 비밀번호로 대시보드에 접속하세요.</p>
<form method="post" action="/login"><label for="password">접속 비밀번호</label>
<input id="password" name="password" type="password" autocomplete="current-password"
required maxlength="128"><button type="submit">워크스페이스 열기 →</button></form>
<small>2D 시뮬레이션 환경 · 실제 로봇 연결 없음</small></main></body></html>'''
LOGIN_CSS = '''*{box-sizing:border-box}body{margin:0;background:#f2f5fa;color:#192d45;
font:14px "Segoe UI","Malgun Gothic",sans-serif;min-height:100vh;display:grid;place-items:center;
padding:24px}main{width:100%;max-width:430px;background:white;border:1px solid #dfe5ee;
border-radius:16px;padding:36px}.brand{display:grid;place-items:center;width:48px;height:48px;
border-radius:12px;background:#2764e7;color:white;font-weight:700}.label,small{color:#5d6b80;
font-size:12px}h1{font-size:25px;letter-spacing:-1px;line-height:1.4}p{line-height:1.8;
color:#5d6b80}form{margin:28px 0}label{display:block;margin-bottom:10px;font-weight:600}
input,button{width:100%;font:inherit;padding:13px;border-radius:8px;border:1px solid #dfe5ee}
button{margin-top:14px;color:white;background:#2764e7;border-color:#2764e7;font-weight:600;
cursor:pointer}input:focus-visible,button:focus-visible{outline:3px solid #80a9ff;outline-offset:3px}'''
SECURITY_HEADERS = {
    'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
    # Form POST navigation must retain its Origin for the same-origin gate.
    # Suppress referrers to external sites without making login Origin opaque.
    'Referrer-Policy': 'same-origin',
    'Content-Security-Policy': "default-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
}


class HostedGateway:
    def __init__(self, app, *, hostname, password_hash, signing_key, clock=time.time):
        if (not re.fullmatch(r'[a-z0-9-]+\.cloudfront\.net', hostname)
                or not re.fullmatch(r'[0-9a-f]{64}', password_hash)
                or not re.fullmatch(r'[0-9a-f]{64}', signing_key)):
            raise ValueError('Hosted gateway requires a CloudFront host and strong credentials')
        self.app, self.hostname = app, hostname
        self.origin = f'https://{hostname}'
        self.password_hash, self.key = password_hash, bytes.fromhex(signing_key)
        self.clock = clock
        self.attempts = {}

    def _token(self):
        payload = f'{int(self.clock())}.{secrets.token_hex(16)}'
        return f'{payload}.{hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()}'

    def _authenticated(self, headers):
        try:
            cookies = SimpleCookie()
            cookies.load(headers.get(b'cookie', b'').decode('latin1'))
            token = cookies[SESSION_COOKIE].value
            if not re.fullmatch(r'[0-9]{1,12}\.[0-9a-f]{32}\.[0-9a-f]{64}', token):
                return False
            payload, signature = token.rsplit('.', 1)
            expected = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
            age = self.clock() - int(payload.split('.')[0])
            return 0 <= age <= SESSION_SECONDS and hmac.compare_digest(signature, expected)
        except (CookieError, KeyError, ValueError):
            return False

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            return await send({'type': 'websocket.close', 'code': 1008})
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])

        async def reply(response):
            response.headers.update(SECURITY_HEADERS)
            await response(scope, receive, send)

        def error(status, message):
            return JSONResponse({'detail': message}, status_code=status)

        for name in (b'host', b'origin', b'cookie'):
            if sum(key == name for key, _ in scope['headers']) > 1:
                return await reply(error(400, 'Duplicate security header'))
        if headers.get(b'host') != self.hostname.encode() or scope['scheme'] != 'https':
            return await reply(error(400, 'Hosted HTTPS host required'))
        origin = headers.get(b'origin')
        public_navigation = (scope['method'] == 'GET' and scope['path'] in ('/', '/login')
                             and origin is None
                             and headers.get(b'sec-fetch-mode') == b'navigate'
                             and headers.get(b'sec-fetch-dest') == b'document')
        if ((origin is not None and origin != self.origin.encode())
                or (headers.get(b'sec-fetch-site') == b'cross-site' and not public_navigation)
                or (scope['method'] not in ('GET', 'HEAD', 'OPTIONS') and origin != self.origin.encode())):
            return await reply(error(403, 'Same-origin request required'))
        if scope['path'] == '/login.css' and scope['method'] == 'GET':
            return await reply(Response(LOGIN_CSS, media_type='text/css'))
        if scope['path'] == '/login':
            if scope['method'] == 'GET':
                return await reply(HTMLResponse(LOGIN_HTML))
            if scope['method'] != 'POST':
                return await reply(error(405, 'Method not allowed'))
            now = self.clock()
            for client, attempts in list(self.attempts.items()):
                while attempts and now - attempts[0] > 60:
                    attempts.popleft()
                if not attempts:
                    del self.attempts[client]
            # Uvicorn trusts only loopback nginx. Nginx preserves the last IP
            # CloudFront appends; viewer-controlled prefixes are never the key.
            client = (scope.get('client') or ('unknown', 0))[0]
            if client not in self.attempts and len(self.attempts) >= 1024:
                return await reply(error(429, '로그인 요청이 많습니다. 잠시 후 다시 시도하세요.'))
            attempts = self.attempts.setdefault(client, deque())
            if len(attempts) >= 5:
                return await reply(error(429, '로그인 시도가 많습니다. 1분 후 다시 시도하세요.'))
            # Reserve before the first await so concurrent requests share the cap.
            attempts.append(now)
            body = bytearray()
            while True:
                chunk = await receive()
                if chunk['type'] == 'http.disconnect':
                    return
                body.extend(chunk.get('body', b''))
                if len(body) > 2048:
                    return await reply(error(413, 'Request too large'))
                if not chunk.get('more_body', False):
                    break
            if headers.get(b'content-type', b'').split(b';')[0] != b'application/x-www-form-urlencoded':
                return await reply(error(415, 'Form input required'))
            try:
                fields = parse_qs(body.decode('utf-8'), strict_parsing=True, max_num_fields=2)
                password = fields.get('password', [])
                valid = len(password) == 1 and hmac.compare_digest(
                    hashlib.sha256(password[0].encode()).hexdigest(), self.password_hash)
            except (UnicodeError, ValueError):
                valid = False
            if not valid:
                return await reply(error(401, '비밀번호를 확인해 주세요.'))
            response = RedirectResponse('/', status_code=303)
            response.set_cookie(SESSION_COOKIE, self._token(), max_age=SESSION_SECONDS,
                                secure=True, httponly=True, samesite='strict', path='/')
            return await reply(response)
        if not self._authenticated(headers):
            if scope['path'] == '/' and scope['method'] == 'GET':
                return await reply(RedirectResponse('/login', status_code=303))
            return await reply(error(401, '로그인이 필요합니다.'))
        # Public checks above are complete. Preserve the existing inner local boundary.
        local_scope = dict(scope, scheme='http')
        local_scope['headers'] = [(k, v) for k, v in scope['headers'] if k not in (b'host', b'origin')]
        local_scope['headers'].extend([(b'host', b'127.0.0.1:8765'), (b'origin', b'http://127.0.0.1:8765')])
        return await self.app(local_scope, receive, send)


def create_hosted_app():
    app = create_app()
    app.add_middleware(HostedGateway, hostname=os.environ['S2A_PUBLIC_HOST'],
                       password_hash=os.environ['S2A_LOGIN_PASSWORD_SHA256'],
                       signing_key=os.environ['S2A_SESSION_SECRET'])
    return app
