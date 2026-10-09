from fastapi.testclient import TestClient

from scene2action.app import create_app


def test_operator_roundtrip_and_history(tmp_path):
    with TestClient(create_app(tmp_path / 'api.sqlite', ticker=False), base_url='http://127.0.0.1:8765') as client:
        assert client.get('/').status_code == 200
        state = client.get('/api/state').json()
        assert state['contract']['id'] == 'sort'
        run = client.post('/api/evaluate', json={'mode': 'TEXT', 'text': '정상 작업'}).json()
        assert run['status'] == 'READY'
        assert client.post(f"/api/runs/{run['id']}/execute").json()['status'] == 'RUNNING'
        assert client.post(f"/api/runs/{run['id']}/execute").status_code == 409
        assert client.post('/api/stop').status_code == 200
        assert client.get(f"/api/runs/{run['id']}").json()['status'] == 'STOPPED'
        assert client.get('/api/history').json()[0]['id'] == run['id']
        assert client.get(f"/api/runs/{run['id']}/export").headers['content-type'].startswith('application/json')


def test_cross_origin_and_unknown_host_are_rejected(tmp_path):
    with TestClient(create_app(tmp_path / 'api.sqlite', ticker=False), base_url='http://127.0.0.1:8765') as client:
        assert client.post('/api/stop', headers={'Origin': 'https://untrusted.example'}).status_code == 403
        assert client.get('/api/state', headers={'Host': 'untrusted.example'}).status_code == 400
        assert client.post('/api/stop', headers={'Origin': 'http://127.0.0.1:9999'}).status_code == 403


def test_unknown_fields_and_large_requests_fail_closed(tmp_path):
    with TestClient(create_app(tmp_path / 'api.sqlite', ticker=False), base_url='http://127.0.0.1:8765') as client:
        assert client.post('/api/evaluate', json={'mode': 'TEXT', 'text': '정상', 'policy': 'override'}).status_code == 422
        assert client.post('/api/evaluate', json={'mode': 'TEXT', 'text': 'x'*4001}).status_code == 422
        assert client.post('/api/evaluate', content=b'x'*20000, headers={'Content-Type': 'application/json'}).status_code == 413
        assert client.get('/api/history').json() == []


def test_live_config_absence_is_visible(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_MODEL', raising=False)
    with TestClient(create_app(tmp_path / 'api.sqlite', ticker=False), base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/config').json()['openai_ready'] is False
        result = client.post('/api/evaluate', json={'mode': 'IMAGE', 'provider': 'openai'}).json()
        assert result['status'] == 'HELD'


def test_blocked_model_call_does_not_block_stop_or_allow_stale_approval(tmp_path,monkeypatch):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    entered,release=threading.Event(),threading.Event()
    with TestClient(create_app(tmp_path/'slow.sqlite'),base_url='http://127.0.0.1:8765') as client:
        engine=client.app.state.engine
        prepared=client.post('/api/evaluate',json={'mode':'TEXT','text':'normal'}).json()
        before=engine.state()['world']['position']
        original=engine._propose
        def blocked(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test did not release planner')
            return original(*args)
        monkeypatch.setattr(engine,'_propose',blocked)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(client.post,'/api/evaluate',json={'mode':'TEXT','text':'normal'})
            try:
                assert entered.wait(2)
                assert not future.done()
                assert client.post(f"/api/runs/{prepared['id']}/execute").status_code==200
                deadline=time.monotonic()+2
                while engine.state()['world']['position']==before and time.monotonic()<deadline:
                    time.sleep(.01)
                assert engine.state()['world']['position']!=before
                stop=client.post('/api/stop')
                assert stop.status_code==200
                assert not future.done()
                assert engine.run(prepared['id'])['status']=='STOPPED'
            finally:
                release.set()
            run=future.result(timeout=3).json()
            assert run['status']=='HELD' and not run['commands_sent']
            assert client.post(f"/api/runs/{run['id']}/execute").status_code==409


def test_pending_model_does_not_block_monitor_or_stop(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    entered, release, moved = Event(), Event(), Event()
    with TestClient(create_app(tmp_path/'concurrent.sqlite'), base_url='http://127.0.0.1:8765') as client:
        engine = client.app.state.engine
        prepared = client.post('/api/evaluate', json={'text':'normal'}).json()
        original_propose, original_tick = engine._propose, engine.tick
        def pending(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test provider timed out')
            return original_propose(*args)
        def tick():
            before = engine.state()['world']['position']
            original_tick()
            if engine.state()['world']['position'] != before:
                moved.set()
        monkeypatch.setattr(engine, '_propose', pending)
        monkeypatch.setattr(engine, 'tick', tick)
        with ThreadPoolExecutor(max_workers=2) as pool:
            evaluation = pool.submit(client.post, '/api/evaluate', json={'text':'normal'})
            try:
                assert entered.wait(2)
                assert client.post(f"/api/runs/{prepared['id']}/execute").status_code == 200
                assert moved.wait(2), 'monitor must advance while model call is pending'
                stop = pool.submit(client.post, '/api/stop')
                assert stop.result(timeout=2).status_code == 200
                assert not evaluation.done()
                before = engine.state()['world']['position']
            finally:
                release.set()
            result = evaluation.result(timeout=2).json()
            assert result['status'] == 'HELD'
            assert result['commands_sent'] == []
            assert engine.state()['world']['position'] == before
            assert engine.run(prepared['id'])['status'] == 'STOPPED'
