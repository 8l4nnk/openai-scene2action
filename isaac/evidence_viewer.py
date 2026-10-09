"""Read-only public view of one isolated synthetic normal-work simulation.

No directory serving, input submission, shell, robot command or credential access.
"""
import json
import math
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OBJECTS=('S05_sphere_red','S05_sphere_blue')
ROOT=Path('/tmp/s2a-normal-evidence')
PAGE='''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>K-Scene2Action · Isaac 정상 작업 검증</title>
<style>body{background:#101721;color:#edf5ff;font:16px system-ui;margin:24px auto;max-width:1080px;padding:0 16px}h1{font-size:25px}img,video{width:100%;background:#1b2938;border-radius:12px}p{line-height:1.6}pre{white-space:pre-wrap;background:#1b2938;padding:16px;border-radius:12px}small{color:#adbfd1}</style>
<h1>Isaac 6.1 · 정상 작업 검증</h1>
<p>빨간 공 → 1구역 · 파란 공 → 2구역</p>
<p>현재 단계: 정상 제어기 단독 물리 시험. 워크벤치 필터 연결 및 SA 전체 방어 검증은 미완료입니다.</p>
<p id="status">증거 확인 중</p><img id="frame" alt="Isaac에서 촬영된 최신 스냅샷" hidden>
<small id="age"></small><pre id="checks"></pre>
<video id="video" controls preload="none" hidden></video>
<script>
let lastFrame='',videoSet=false;
async function refresh(){try{const r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)throw Error();const s=await r.json();
document.querySelector('#status').textContent=s.state+' · '+s.run_id;
document.querySelector('#checks').textContent=JSON.stringify(s.objects,null,2);
const f=document.querySelector('#frame');f.hidden=!s.frame;
if(s.frame&&s.frame!==lastFrame){f.src='/frame.png?v='+encodeURIComponent(s.frame);lastFrame=s.frame;}
document.querySelector('#age').textContent=s.frame?'촬영 후 '+s.frame_age_s+'초 · 실제 렌더 스냅샷 (실시간 스트림 아님)':'아직 촬영된 프레임이 없습니다.';
if(s.video&&!videoSet){const v=document.querySelector('#video');v.hidden=false;v.src='/video.mp4';videoSet=true;}
}catch(e){document.querySelector('#status').textContent='연결 실패 · 검증 결과 없음';document.querySelector('#frame').hidden=true;}}
refresh();setInterval(refresh,3000);
</script></html>'''.encode('utf-8')


def safe_file(root,path):
    try:
        if root.is_symlink() or not path.resolve().is_relative_to(root.resolve()): return None
        for p in (path,*path.parents):
            if p==root.parent: break
            if p.is_symlink(): return None
        return path if path.is_file() else None
    except OSError:
        return None


def current_run(root):
    path=safe_file(root,root/'current.json')
    if not path or path.stat().st_size>4096: return {}
    d=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(d,dict) or not isinstance(d.get('run_id'),str) or not re.fullmatch(r'normal-[0-9a-f]{32}',d['run_id']): return {}
    if d.get('state')=='RUNNING':
        if d.get('process_exit') is not None: return {}
    elif d.get('state')=='FINISHED':
        if type(d.get('process_exit')) is not int: return {}
    else: return {}
    return d


def latest_frame(root,run):
    if not run: return None
    files=[p for p in (root/'process_assets').glob(run+'-*.png')
           if safe_file(root,p) and 0<p.stat().st_size<16*1024*1024]
    return max(files,key=lambda p:p.stat().st_mtime) if files else None


def evidence_state(root):
    state={'run_id':None,'state':'AWAITING_EVIDENCE','objects':{},'frame':None,
           'frame_age_s':None,'video':False,'filter_integration':False}
    try:
        current=current_run(root)
        run=current.get('run_id')
        if not run: return state
        state['run_id']=run
        if current.get('state')=='RUNNING': state['state']='RUNNING_BASELINE'
        elif current.get('process_exit')!=0: state['state']='BASELINE_FAIL'
        result=safe_file(root,root/'results/S05'/f'{run}.json')
        if result and result.stat().st_size<32*1024*1024 and current.get('state')=='FINISHED':
            d=json.loads(result.read_text(encoding='utf-8'))
            final=d.get('final_evaluations',{})
            required=('supported_on_table','whole_projection_with_10mm_margin','stable_2s','upright','assigned_slot')
            observed=all(final.get(n,{}).get('success') is True and all(
                final[n].get('checks',{}).get(c) is True for c in required) for n in OBJECTS)
            executions=d.get('executions',[])
            released=len(executions)==2 and all(e.get('planned_object')==n and
                e.get('evaluation',{}).get('success') is True and all(
                    e['evaluation'].get('checks',{}).get(c) is True
                    for c in ('released','only_selected_robot_contact','nontarget_preserved'))
                for e,n in zip(executions,OBJECTS))
            passed=(current.get('process_exit')==0 and d.get('run_id')==run and d.get('status')=='PASS' and
                    d.get('oracle_executor') is True and d.get('full_scenario_success') is True and observed and released)
            state['state']='BASELINE_PASS' if passed else 'BASELINE_FAIL' if d.get('status')=='FAIL' or current.get('process_exit')!=0 else 'INCOMPLETE_EVIDENCE'
            state['objects']={n:{c:final.get(n,{}).get('checks',{}).get(c) is True for c in required} for n in OBJECTS}
            state['video']=bool(safe_file(root,root/'videos'/f'{run}.mp4'))
        frame=latest_frame(root,run)
        if frame:
            age=time.time()-frame.stat().st_mtime
            if math.isfinite(age) and age>=0:
                state.update(frame=frame.name,frame_age_s=round(age,1))
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        state.update(state='INCOMPLETE_EVIDENCE',objects={},video=False)
    return state


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self,*args):
        pass

    def do_GET(self):
        path=self.path.split('?',1)[0]
        file=None
        if path=='/': data,mime=PAGE,'text/html; charset=utf-8'
        elif path=='/api/state': data,mime=json.dumps(evidence_state(ROOT)).encode(),'application/json'
        elif path in ('/frame.png','/video.mp4'):
            state=evidence_state(ROOT)
            run=state['run_id']
            if path=='/frame.png': file,mime=latest_frame(ROOT,run),'image/png'
            else: file,mime=safe_file(ROOT,ROOT/'videos'/f'{run}.mp4') if state['video'] else None,'video/mp4'
        else: self.send_error(404);return
        try:
            if path in ('/frame.png','/video.mp4'):
                if file is None or not file.is_file() or file.is_symlink(): self.send_error(404);return
                size=file.stat().st_size
            else: size=len(data)
            self.send_response(200)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(size))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            if file:
                with file.open('rb') as source:
                    while chunk:=source.read(65536): self.wfile.write(chunk)
            else: self.wfile.write(data)
        except (OSError,ConnectionError):
            return


if __name__=='__main__':
    ThreadingHTTPServer(('0.0.0.0',8888),Handler).serve_forever()
