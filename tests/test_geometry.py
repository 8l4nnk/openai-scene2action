import os
import random
from pathlib import Path

import pytest


def backend():
    from scene2action.geometry import NativeGeometry
    path=Path(os.environ.get('S2A_NATIVE_LIBRARY', '.data/native/s2a_geometry.dll' if os.name == 'nt' else '.data/native/libs2a_geometry.so'))
    if not path.is_file() and os.getenv('S2A_REQUIRE_NATIVE_TESTS')!='1':
        pytest.skip('Build scripts/build_native.py to exercise compiled native geometry')
    return NativeGeometry(path)


@pytest.mark.parametrize('start,end,boxes,radius,blocked', [
    ((.1,.5),(.9,.5),[(.4,.4,.6,.6)],.02,True),
    ((.1,.3),(.9,.3),[(.4,.4,.6,.6)],.11,True),
    ((.1,.3),(.9,.3),[(.4,.4,.6,.6)],.02,False),
    ((.5,.5),(.5,.5),[(.4,.4,.6,.6)],.02,True),
    ((.1,.2),(.9,.2),[],.02,False),
    ((.01,.2),(.9,.2),[],.02,True),
    ((.1,.375),(.9,.375),[(.4,.4,.6,.6)],.025,True),
    ((.5,.38-2e-13),(.5,.38+2e-13),[(.4,.4,.6,.6)],.02,True),
])
def test_compiled_geometry_catches_crossing_clearance_contact_and_bounds(start,end,boxes,radius,blocked):
    assert backend().segment_blocked(start,end,boxes,radius) is blocked


@pytest.mark.parametrize('start,end,boxes,radius', [
    ((float('nan'),.5),(.8,.5),[],.02),
    ((.2,.5),(float('inf'),.5),[],.02),
    ((.2,.5),(.8,.5),[(.6,.4,.4,.6)],.02),
    ((.2,.5),(.8,.5),[(.4,.4,float('nan'),.6)],.02),
    ((.2,.5),(.8,.5),[],-.1),
    ((.2,.5),(.8,.5),[],float('nan')),
    ((.2,.5),(.8,.5),[(.1,.2,.3)],.02),
])
def test_invalid_geometry_never_clears_native_path(start,end,boxes,radius):
    assert backend().segment_blocked(start,end,boxes,radius)


def test_native_and_python_agree_on_deterministic_random_paths():
    from scene2action.geometry import PythonGeometry
    native,python=backend(),PythonGeometry()
    rng=random.Random(20261009)
    for _ in range(500):
        boxes=[]
        for _ in range(rng.randrange(0,12)):
            x0,x1=sorted([rng.random(),rng.random()])
            y0,y1=sorted([rng.random(),rng.random()])
            boxes.append((x0,y0,x1,y1))
        start,end=[rng.random(),rng.random()],[rng.random(),rng.random()]
        radius=rng.uniform(0,.15)
        assert native.segment_blocked(start,end,boxes,radius)==python.segment_blocked(start,end,boxes,radius)


def test_tiny_segment_crossing_expanded_boundary_is_blocked_by_both_backends():
    from scene2action.geometry import PythonGeometry
    start,end=(.35-5e-14,.5),(.35+5e-14,.5)
    boxes=[(.4,.4,.6,.6)]
    assert backend().segment_blocked(start,end,boxes,.05)
    assert PythonGeometry().segment_blocked(start,end,boxes,.05)


def test_c_abi_itself_rejects_invalid_data_and_oversized_counts():
    import ctypes
    native=backend()
    points=(ctypes.c_double*4)(.2,.5,float('nan'),.5)
    assert native._function(points,2,None,0,.02)!=1
    assert native._function(points,1025,None,0,.02)==-1
    assert native._function(None,2,None,0,.02)==-1
    assert native._function(points,2,None,4097,.02)==-1


def test_native_path_checks_all_segments_and_rejects_empty_command_sequence():
    world={'position':[.1,.2],'obstacles':[(.4,.4,.6,.6)]}
    native=backend()
    assert native.path_clear([{'position':[.9,.2]}],world)
    assert not native.path_clear([{'position':[.1,.5]},{'position':[.9,.5]}],world)
    assert not native.path_clear([],world)


def test_near_parallel_boundary_contact_agrees_with_python():
    from scene2action.geometry import PythonGeometry
    start,end=(.5,.38-2e-13),(.5,.38+2e-13)
    boxes=[(.4,.4,.6,.6)]
    assert backend().segment_blocked(start,end,boxes,.02)
    assert PythonGeometry().segment_blocked(start,end,boxes,.02)


@pytest.mark.parametrize('contract_id',['sort','kit'])
def test_native_engine_completes_normal_contract(tmp_path,monkeypatch,contract_id):
    from scene2action.engine import Engine
    from scene2action.models import EvaluateRequest
    monkeypatch.setenv('S2A_GEOMETRY_BACKEND','native')
    now=[100.]
    engine=Engine(tmp_path/f'{contract_id}.sqlite',clock=lambda:now[0])
    try:
        engine.reset(contract_id)
        run=engine.evaluate(EvaluateRequest(text='normal'))
        assert run['status']=='READY'
        engine.execute(run['id'])
        for _ in range(500):
            now[0]+=.05
            engine.tick()
            if engine.state()['active_run_id'] is None:
                break
        result=engine.run(run['id'])
        assert result['status']=='COMPLETED'
        assert len(result['commands_sent'])==8
        world=engine.state()['world']
        for action in engine.contract.steps:
            assert world['objects'][action.object_id]==world['targets'][action.target_id]
    finally:
        engine.close()


def test_native_missing_library_and_invalid_backend_stop_engine_startup(tmp_path,monkeypatch):
    from scene2action.engine import Engine
    monkeypatch.setenv('S2A_GEOMETRY_BACKEND','native')
    monkeypatch.setenv('S2A_NATIVE_LIBRARY',str(tmp_path/'missing.dll'))
    with pytest.raises(RuntimeError,match='native geometry'):
        Engine(tmp_path/'missing.sqlite')
    monkeypatch.setenv('S2A_GEOMETRY_BACKEND','typo')
    with pytest.raises(ValueError,match='geometry backend'):
        Engine(tmp_path/'bad.sqlite')


def test_native_backend_records_evidence_and_preserves_stop_interlock(tmp_path,monkeypatch):
    from scene2action.engine import Engine
    from scene2action.models import EvaluateRequest
    backend()
    monkeypatch.setenv('S2A_GEOMETRY_BACKEND','native')
    now=[100.]
    engine=Engine(tmp_path/'native.sqlite',clock=lambda:now[0])
    try:
        run=engine.evaluate(EvaluateRequest(text='normal'))
        assert run['status']=='READY'
        assert run['evidence']['geometry_backend']=='native'
        engine.execute(run['id'])
        now[0]+=.05
        engine.tick()
        engine.stop()
        position=engine.state()['world']['position']
        now[0]+=.05
        engine.tick()
        assert engine.state()['geometry_backend']=='native'
        assert engine.state()['world']['position']==position
        with pytest.raises(ValueError):
            engine.execute(run['id'])
    finally:
        engine.close()
