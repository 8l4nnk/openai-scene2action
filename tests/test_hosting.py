import hashlib

import pytest
from fastapi.testclient import TestClient

from scene2action.app import create_app
from scene2action.hosting import HostedGateway, SESSION_COOKIE

HOST = 'demo.cloudfront.net'
PASSWORD = 'a-random-test-password-with-32-bytes'
ORIGIN = {'Origin': f'https://{HOST}'}


def hosted(tmp_path, now):
    app = create_app(tmp_path / 'hosted.sqlite', ticker=False)
    app.add_middleware(HostedGateway, hostname=HOST,
                       password_hash=hashlib.sha256(PASSWORD.encode()).hexdigest(),
                       signing_key='a' * 64, clock=lambda: now[0])
    return TestClient(app, base_url=f'https://{HOST}')


def login(client):
    response = client.post('/login', data={'password': PASSWORD}, headers=ORIGIN,
                           follow_redirects=False)
    assert response.status_code == 303
    assert all(flag in response.headers['set-cookie'].lower()
               for flag in ('secure', 'httponly', 'samesite=strict', 'path=/'))


def test_every_dashboard_api_is_authenticated(tmp_path):
    with hosted(tmp_path, [1000]) as client:
        assert client.get('/', follow_redirects=False).status_code == 303
        assert client.get('/login').status_code == 200
        assert client.get('/login.css').status_code == 200
        assert client.get('/api/state').status_code == 401
        assert client.post('/api/stop', headers=ORIGIN).status_code == 401
        assert client.get('/static/app.js').status_code == 401
        login(client)
        assert client.get('/').status_code == 200
        run = client.post('/api/evaluate', json={'text': 'normal'}, headers=ORIGIN).json()
        assert run['status'] == 'READY'
        assert client.post(f"/api/runs/{run['id']}/execute", headers=ORIGIN).status_code == 200
        assert client.post('/api/stop', headers=ORIGIN).status_code == 200
        assert client.get(f"/api/runs/{run['id']}").json()['status'] == 'STOPPED'


def test_session_expiry_tampering_and_public_boundaries(tmp_path):
    now = [1000]
    with hosted(tmp_path, now) as client:
        login(client)
        assert client.get('/api/state', headers={'Host': 'evil.example'}).status_code == 400
        assert client.get('/api/state', headers=[('Host', HOST), ('Host', HOST)]).status_code == 400
        assert client.post('/api/stop', headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/stop').status_code == 403
        assert client.post('/api/stop', headers={**ORIGIN, 'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert client.get(f'http://{HOST}/api/state').status_code == 400
        token = client.cookies.get(SESSION_COOKIE)
        client.cookies.clear()
        assert client.get('/api/state', headers={'Cookie': f'{SESSION_COOKIE}={token}x'}).status_code == 401
        now[0] += 28801
        assert client.get('/api/state', headers={'Cookie': f'{SESSION_COOKIE}={token}'}).status_code == 401


def test_login_limits_and_missing_config(tmp_path):
    now = [1000]
    with hosted(tmp_path, now) as client:
        assert client.post('/login', data={'password': PASSWORD}).status_code == 403
        assert client.post('/login', content=b'a'*2049, headers=ORIGIN).status_code == 413
        # The oversized same-origin POST also consumes one of five attempts.
        for _ in range(4):
            assert client.post('/login', data={'password': 'wrong'}, headers=ORIGIN).status_code == 401
        assert client.post('/login', data={'password': PASSWORD}, headers=ORIGIN).status_code == 429
        now[0] += 61
        login(client)
    with pytest.raises(ValueError):
        HostedGateway(None, hostname='', password_hash='', signing_key='')


def test_hosted_settings_do_not_open_local_app(tmp_path, monkeypatch):
    monkeypatch.setenv('S2A_PUBLIC_HOST', HOST)
    with TestClient(create_app(tmp_path/'local.sqlite', ticker=False), base_url=f'https://{HOST}') as client:
        assert client.get('/api/state').status_code == 400


def test_login_form_preserves_browser_origin_and_rejects_opaque_origins(tmp_path):
    # Under the Fetch Standard a no-referrer document sends Origin: null for
    # form POST navigation, even when the form target is on the same origin.
    with hosted(tmp_path, [1000]) as client:
        page = client.get('/login')
        assert page.status_code == 200
        assert page.headers['referrer-policy'] in {
            'same-origin', 'strict-origin', 'strict-origin-when-cross-origin'}
        navigation = {'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'navigate',
                      'Sec-Fetch-Dest': 'document'}
        assert client.post('/login', data={'password': PASSWORD},
                           headers={**navigation, 'Origin': 'null'}).status_code == 403
        assert client.post('/login', data={'password': PASSWORD},
                           headers=navigation).status_code == 403
        assert client.post('/login', data={'password': PASSWORD},
                           headers={**navigation, 'Origin': 'https://evil.example'}).status_code == 403
        response = client.post('/login', data={'password': PASSWORD},
                               headers={**navigation, **ORIGIN}, follow_redirects=False)
        assert response.status_code == 303
        assert client.get('/').status_code == 200


def test_shared_link_can_reach_login_but_not_private_routes(tmp_path):
    navigation = {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate',
                  'Sec-Fetch-Dest': 'document'}
    with hosted(tmp_path, [1000]) as client:
        assert client.get('/', headers=navigation, follow_redirects=False).status_code == 303
        assert client.get('/login', headers=navigation).status_code == 200
        assert client.get('/api/state', headers=navigation).status_code == 403
        assert client.get('/login', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert client.post('/login', data={'password': PASSWORD}, headers=navigation).status_code == 403


def test_login_limit_does_not_block_another_client(tmp_path):
    with hosted(tmp_path, [1000]) as client:
        for _ in range(5):
            assert client.post('/login', data={'password': 'wrong'}, headers=ORIGIN).status_code == 401
        other = TestClient(client.app, base_url=f'https://{HOST}', client=('198.51.100.2', 54321))
        try:
            login(other)
        finally:
            other.close()


def test_concurrent_logins_reserve_limit_before_reading_body():
    import asyncio
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    async def check():
        gateway = HostedGateway(None, hostname=HOST,
                                password_hash=hashlib.sha256(PASSWORD.encode()).hexdigest(),
                                signing_key='a'*64, clock=lambda: 1000)
        proxy = ProxyHeadersMiddleware(gateway, trusted_hosts=['127.0.0.1'])
        release = asyncio.Event()
        entered = []
        statuses = []

        async def request(index):
            scope = {'type': 'http', 'scheme': 'http', 'method': 'POST', 'path': '/login',
                     'client': ('127.0.0.1', 12345), 'headers': [
                         (b'host', HOST.encode()), (b'origin', f'https://{HOST}'.encode()),
                         (b'x-forwarded-proto', b'https'),
                         # CloudFront appends the real viewer IP after any viewer-provided value.
                         (b'x-forwarded-for', f'203.0.113.{index}, 198.51.100.9'.encode()),
                         (b'content-type', b'application/x-www-form-urlencoded')]}

            async def receive():
                entered.append(index)
                await release.wait()
                return {'type': 'http.request', 'body': b'password=wrong', 'more_body': False}

            async def send(message):
                if message['type'] == 'http.response.start':
                    statuses.append(message['status'])

            await proxy(scope, receive, send)

        tasks = [asyncio.create_task(request(i)) for i in range(10)]
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(*tasks)
        assert len(entered) == 5
        assert statuses.count(401) == 5 and statuses.count(429) == 5

    asyncio.run(check())
