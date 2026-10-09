"""Dashboard evidence routes; only fixed read-only upstream resources."""
from functools import lru_cache
import json
import httpx
from fastapi import HTTPException
from fastapi.responses import Response
from .demo import DemoCorpus, sha

ISAAC='https://80wnh6z0nu0o82-8888.proxy.runpod.net'


@lru_cache(maxsize=1)
def corpus():
    return DemoCorpus()


def install(app):
    @app.get('/api/demo/screened-batch')
    def screened_batch():
        return corpus().screened_batch()

    @app.get('/api/demo/cases')
    def cases():
        c=corpus()
        return dict(summary=c.summary(),cases=[dict(case_id=k,modality=v['modality'],dataset=v['dataset'],
            harmful_action_id=v.get('harmful_action_id'),qwen_decision=c.results[k]['decision']) for k,v in c.cases.items()])

    @app.get('/api/demo/cases/{case_id}')
    def detail(case_id:str):
        return corpus().detail(case_id)

    @app.get('/api/demo/images/{case_id}')
    def image(case_id:str):
        c=corpus();case=c.cases[case_id]
        if case['modality']!='IMAGE': raise HTTPException(404)
        p=(c.root/case['image_path']).resolve()
        if not p.is_relative_to(c.root.resolve()): raise HTTPException(404)
        b=p.read_bytes()
        if sha(b)!=case['input_sha256']: raise HTTPException(409,'이미지 무결성 오류')
        return Response(b,media_type='image/png')

    @app.get('/api/isaac/{resource}')
    async def isaac(resource:str):
        paths={'state':'/api/state','observer':'/observer.jpg','rgb':'/rgb.jpg'}
        if resource not in paths: raise HTTPException(404)
        try:
            async with httpx.AsyncClient(timeout=5,follow_redirects=False,trust_env=False) as client:
                async with client.stream('GET',ISAAC+paths[resource]) as r:
                    if r.status_code!=200: raise HTTPException(503,'Isaac 카메라 응답 대기')
                    data=bytearray()
                    async for chunk in r.aiter_bytes():
                        data.extend(chunk)
                        if len(data)>4*1024*1024: raise HTTPException(502,'카메라 응답 크기 초과')
            if resource=='state':
                s=json.loads(data)
                keys=('state','normal_motion_verified','filter_integration','camera_age_s','run_id','completed_commands','error')
                return {k:s.get(k) for k in keys}
            if not data.startswith(b'\xff\xd8'): raise HTTPException(502,'카메라 이미지 형식 오류')
            return Response(bytes(data),media_type='image/jpeg')
        except (httpx.HTTPError,ValueError,TypeError):
            raise HTTPException(503,'Isaac 연결을 확인하세요') from None
