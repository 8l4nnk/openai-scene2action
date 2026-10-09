"""Public, read-only camera and normal trial evidence. No command routes."""
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path('/workspace/s2a_normal_validation_20261009')
LIVE = ROOT/'live'
PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>K-Scene2Action · Isaac 실증</title><style>body{font:16px system-ui;background:#0e1726;color:#ecf3ff;max-width:1200px;margin:32px auto;padding:0 24px}h1{font-size:32px}.tag{color:#8ae5c1}img{width:100%;background:#18263c;border-radius:14px;min-height:160px}section{display:grid;grid-template-columns:1fr 1fr;gap:20px}pre{background:#18263c;padding:20px;white-space:pre-wrap}p{line-height:1.7}@media(max-width:700px){section{grid-template-columns:1fr}}</style>
<div class="tag">K-Scene2Action / Isaac Sim / L4</div><h1>정상 운반 실증</h1><p>빨간 공 → 1구역 · 파란 공 → 2구역<br>기존 장면 · Direct IK · ROS2 Control · 시뮬레이션 전용</p>
<h2 id="status">상태 확인 중</h2><p id="fresh"></p><section><div><h3>관찰 카메라</h3><img id="observer" alt="Isaac 관찰 카메라"></div><div><h3>RGB-D 입력 카메라</h3><img id="rgb" alt="Isaac RGB-D 입력 카메라"></div></section>
<p>카메라는 주기적으로 촬영한 실제 Isaac 프레임입니다. 정상 작업 성공과 필터 방어 검증은 별개이며, 이 페이지에는 로봇 실행 기능이 없습니다.</p>
<pre id="details"></pre><h3>실증 촬영 기록</h3><img id="replay" hidden alt="실증 중 촬영한 프레임"><p id="playlabel"></p>
<script>let replayIndex=0;async function refresh(){try{let r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)throw Error();let s=await r.json();document.querySelector('#status').textContent=s.state;document.querySelector('#details').textContent=JSON.stringify(s,null,2);document.querySelector('#fresh').textContent='카메라 촬영 후 '+s.camera_age_s+'초 · 필터 통합 검증: '+(s.filter_integration?'완료':'미완료');for(let k of ['observer','rgb'])document.querySelector('#'+k).src='/'+k+'.jpg?t='+Date.now();let f=document.querySelector('#replay');f.hidden=!s.recorded_frames;if(s.recorded_frames){replayIndex%=s.recorded_frames;f.src='/replay/'+replayIndex+'.jpg?run='+s.run_id;document.querySelector('#playlabel').textContent='촬영 기록 재생 '+(replayIndex+1)+' / '+s.recorded_frames;replayIndex++;}}catch(e){document.querySelector('#status').textContent='연결 또는 관측 확인 필요';}}refresh();setInterval(refresh,2000);</script></html>'''.encode()


def read(path, limit=16*1024*1024):
    if any(p.is_symlink() for p in (path,*path.parents)) or path.stat().st_size > limit:
        raise ValueError('Invalid evidence path')
    return path.read_bytes()


def run_dir():
    run = json.loads(read(ROOT/'current.json',4096))['run_id']
    if not re.fullmatch(r'normal-[0-9a-f]{32}', run):
        raise ValueError('Invalid run ID')
    return ROOT/run


def state():
    try:
        d = json.loads(read(run_dir()/'result.json',1024*1024))
    except FileNotFoundError:
        d = {'state':'WAITING_FOR_TRIAL','normal_motion_verified':False}
    allowed = ('run_id','state','normal_motion_verified','filter_integration','pipeline',
               'started_at','finished_at','criteria','samples','sample_frames','error','cancel_acknowledged')
    data = {k:d[k] for k in allowed if k in d}
    data['filter_integration'] = False
    data['completed_commands'] = len(d.get('steps',[]))
    data['recorded_frames'] = len(list(run_dir().glob('frames/[0-9][0-9][0-9][0-9].jpg'))) if d.get('run_id') else 0
    try:
        data['camera_age_s'] = round(max(0,time.time()-(LIVE/'latest_observer_rgb.jpg').stat().st_mtime),1)
    except FileNotFoundError:
        data['camera_age_s'] = None
        if data.get('state') == 'WAITING_FOR_TRIAL':
            data['state'] = 'WAITING_FOR_CAMERA'
    return data


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)
    def do_GET(self):
        path = self.path.split('?',1)[0]
        try:
            if path == '/':
                body, mime = PAGE, 'text/html; charset=utf-8'
            elif path == '/api/state':
                body, mime = json.dumps(state(),ensure_ascii=False).encode(), 'application/json'
            elif path in ('/observer.jpg','/rgb.jpg'):
                name = 'latest_observer_rgb.jpg' if path == '/observer.jpg' else 'latest_rgb.jpg'
                body, mime = read(LIVE/name), 'image/jpeg'
            elif re.fullmatch(r'/replay/[0-9]{1,3}\.jpg',path):
                index = int(path.split('/')[-1].split('.')[0])
                body, mime = read(run_dir()/'frames'/f'{index:04}.jpg'), 'image/jpeg'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.end_headers()
            self.wfile.write(body)
        except (OSError,ValueError,KeyError,TypeError):
            self.send_error(503)
    def log_message(self,*_):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0',8888),Handler).serve_forever()
