import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('l4_viewer', Path(__file__).parents[1]/'isaac/l4_evidence_viewer.py')
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


def test_camera_startup_has_readable_state(tmp_path, monkeypatch):
    monkeypatch.setattr(viewer, 'ROOT', tmp_path)
    monkeypatch.setattr(viewer, 'LIVE', tmp_path/'live')
    state = viewer.state()
    assert state['state'] == 'WAITING_FOR_CAMERA'
    assert state['camera_age_s'] is None
    assert state['normal_motion_verified'] is False


def test_evidence_is_whitelisted_and_traversal_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(viewer,'ROOT',tmp_path)
    monkeypatch.setattr(viewer,'LIVE',tmp_path)
    run = 'normal-'+'a'*32
    (tmp_path/run).mkdir()
    (tmp_path/'current.json').write_text(json.dumps({'run_id':run}))
    (tmp_path/'latest_observer_rgb.jpg').write_bytes(b'jpeg')
    (tmp_path/run/'result.json').write_text(json.dumps({'run_id':run,'state':'RUNNING','secret':'exclude','dependency_sha256':{'private':'exclude'}}))
    state = viewer.state()
    assert 'secret' not in state and 'dependency_sha256' not in state
    assert state['filter_integration'] is False
    (tmp_path/'current.json').write_text(json.dumps({'run_id':'../../secrets'}))
    with pytest.raises(ValueError):
        viewer.run_dir()
