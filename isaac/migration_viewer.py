"""Read-only fixed-route viewer; never exposes original code or a controller."""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from migration import ROOT

PUBLIC = ROOT / 'public'
PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>K-Scene2Action · 기존 Isaac 환경</title>
<style>body{background:#101721;color:#edf5ff;font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 20px}img{width:100%;border-radius:12px}pre{background:#1b2938;padding:18px;white-space:pre-wrap}p{line-height:1.7}</style>
<h1>기존 Isaac 환경 · 마이그레이션</h1>
<p>원본 environment.usdc 및 로봇·작업자·공·도구 에셋을 그대로 가져온 환경입니다.</p>
<p>아래 화면은 새 Pod에서 원본 장면을 직접 연 렌더 스냅샷입니다. 정상 운반 성공 및 필터 통합은 별도 검증 항목입니다.</p>
<h2 id="status">환경 확인 중</h2><img id="frame" hidden alt="마이그레이션한 기존 Isaac 장면">
<p id="age"></p><pre id="details"></pre><script>
let last=''; async function refresh(){try{const r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)throw Error();const s=await r.json();
document.querySelector('#status').textContent=s.state;
document.querySelector('#details').textContent=JSON.stringify(s,null,2);
const f=document.querySelector('#frame');f.hidden=!s.frame;
if(s.frame&&last!==String(s.captured_at)){last=String(s.captured_at);f.src='/frame.png?t='+encodeURIComponent(last);}
document.querySelector('#age').textContent=s.frame?'새 Pod에서 촬영 · '+s.frame_age_s+'초 전 · 정지된 장면의 스냅샷':'';
}catch(e){document.querySelector('#status').textContent='연결 확인 중';document.querySelector('#frame').hidden=true;}}
refresh();setInterval(refresh,3000);</script></html>'''.encode('utf-8')


def read_public(name, maximum):
    path = PUBLIC / name
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink')
    if not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('Missing or oversized evidence')
    return path.read_bytes()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def do_GET(self):
        try:
            path = self.path.split('?', 1)[0]
            if path == '/':
                data, mime = PAGE, 'text/html; charset=utf-8'
            elif path == '/api/state':
                d = json.loads(read_public('state.json', 32768))
                keys = ('state', 'stage_preserved', 'normal_motion_verified', 'filter_integration',
                        'frame', 'captured_at', 'stage_sha256', 'required_prims', 'camera',
                        'muted_graph_count', 'unresolved_assets', 'runtime_version', 'timeline', 'error_type',
                        'project_assets_localized', 'localized_asset_count', 'runtime_materials')
                d = {k: d[k] for k in keys if k in d}
                if d.get('frame'):
                    d['frame_age_s'] = round(max(0, time.time() - d['captured_at']))
                data, mime = json.dumps(d).encode(), 'application/json'
            elif path == '/frame.png':
                data, mime = read_public('frame.png', 16 * 1024 * 1024), 'image/png'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)
        except (OSError, ValueError, KeyError):
            self.send_error(503)

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8888), Handler).serve_forever()
