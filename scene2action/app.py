import asyncio
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .engine import Engine
from .models import DisturbRequest, EvaluateRequest, ResetRequest
from .simulator import camera_png


class LocalBoundary:
    """Loopback host/origin boundary and bounded request bodies (including chunks)."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        host = headers.get(b'host', b'').decode('latin1')
        hostname = host.split(':')[0]
        status, message = None, None
        if hostname not in ('127.0.0.1', 'localhost'):
            status, message = 400, 'Loopback host required'
        origin = headers.get(b'origin')
        if origin and origin.decode('latin1') != f"{scope['scheme']}://{host}":
            status, message = 403, 'Cross-origin request rejected'
        if headers.get(b'sec-fetch-site') == b'cross-site':
            status, message = 403, 'Cross-site request rejected'
        if status:
            return await JSONResponse({'detail': message}, status_code=status)(scope, receive, send)
        body = bytearray()
        while True:
            chunk = await receive()
            if chunk['type'] == 'http.disconnect':
                return
            body.extend(chunk.get('body', b''))
            if len(body) > 16384:
                return await JSONResponse({'detail': 'Request too large'}, status_code=413)(scope, receive, send)
            if not chunk.get('more_body', False):
                break
        consumed = False
        async def bounded_receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        async def secured_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = [*message.get('headers', []),
                    (b'x-content-type-options', b'nosniff'),
                    (b'cache-control', b'no-store'),
                    (b'content-security-policy', b"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'"),
                    (b'referrer-policy', b'no-referrer')]
            await send(message)
        await self.app(scope, bounded_receive, secured_send)


def create_app(db_path=None, ticker=True):
    static = Path(__file__).resolve().parent / 'static'
    evaluation_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        engine = Engine(db_path or Path('.data/runs.sqlite'))
        app.state.engine = engine
        shutdown = threading.Event()
        def advance():
            while not shutdown.wait(0.05):
                try:
                    engine.tick()
                except Exception:
                    with engine.lock:
                        engine.active = None
                        engine.approvals.clear()
                        engine.fault = '감시 또는 기록 오류: 실행 중단. 서버 상태를 확인하세요.'
        worker = threading.Thread(target=advance, daemon=True, name='sim-monitor')
        if ticker:
            worker.start()
        try:
            yield
        finally:
            shutdown.set()
            if ticker:
                worker.join(timeout=2)
            engine.close()

    app = FastAPI(title='K-Scene2Action local simulator', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(LocalBoundary)

    @app.exception_handler(ValueError)
    async def invalid_operation(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing_run(request, exc):
        return JSONResponse({'detail': '기록을 찾을 수 없습니다.'}, status_code=404)

    @app.exception_handler(RuntimeError)
    async def engine_error(request, exc):
        return JSONResponse({'detail': '엔진 오류로 실행을 중단했습니다. 상태를 확인하세요.'}, status_code=503)

    @app.get('/')
    def index():
        return FileResponse(static / 'index.html')

    @app.get('/api/config')
    def config(request: Request):
        return {'contracts': [c.model_dump() for c in request.app.state.engine.contracts.values()],
                'openai_ready': bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL')),
                'openai_model': os.getenv('OPENAI_MODEL') or None,
                'simulation_only': True, 'policy_engine': 'local-contract-v1'}

    @app.get('/api/state')
    def state(request: Request):
        return request.app.state.engine.state()

    @app.get('/api/camera')
    def camera(request: Request):
        return Response(camera_png(request.app.state.engine.state()['world']), media_type='image/png')

    @app.post('/api/evaluate')
    async def evaluate(payload: EvaluateRequest, request: Request):
        if evaluation_lock.locked():
            raise HTTPException(429, '다른 평가가 진행 중입니다.')
        async with evaluation_lock:
            return await run_in_threadpool(request.app.state.engine.evaluate, payload)

    @app.post('/api/runs/{run_id}/execute')
    def execute(run_id: str, request: Request):
        return request.app.state.engine.execute(run_id)

    @app.post('/api/stop')
    def stop(request: Request):
        return request.app.state.engine.stop()

    @app.post('/api/reset')
    def reset(payload: ResetRequest, request: Request):
        return request.app.state.engine.reset(payload.contract_id)

    @app.post('/api/disturb')
    def disturb(payload: DisturbRequest, request: Request):
        return request.app.state.engine.disturb(payload.kind)

    @app.get('/api/history')
    def history(request: Request):
        return [{k: r[k] for k in ('id', 'created_at', 'status', 'reason', 'provider', 'mode', 'scenario', 'preparation_ms')}
                for r in request.app.state.engine.history()]

    @app.get('/api/runs/{run_id}')
    def run(run_id: str, request: Request):
        return request.app.state.engine.run(run_id)

    @app.get('/api/runs/{run_id}/export')
    def export(run_id: str, request: Request):
        run = request.app.state.engine.run(run_id)
        return JSONResponse(run, headers={'Content-Disposition': f'attachment; filename="run-{run["id"]}.json"'})

    app.mount('/static', StaticFiles(directory=static), name='static')
    from .demo_routes import install
    install(app)
    return app
