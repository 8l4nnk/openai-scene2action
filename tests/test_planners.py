from types import SimpleNamespace

import pytest

from scene2action.contracts import load_contracts
from scene2action.models import Candidate, EvaluateRequest
from scene2action.planners import propose
from scene2action.simulator import camera_data_url, make_world


@pytest.mark.parametrize('mode,types', [('TEXT', ['input_text']), ('IMAGE', ['input_image']), ('IMAGE_TEXT', ['input_text', 'input_image'])])
def test_live_planner_preserves_input_mode_and_normal_work(monkeypatch, mode, types):
    import openai
    contract = load_contracts()['sort']
    world = make_world(contract, 100, 1)
    captured = {}
    class OfflineTransport:
        def __init__(self, **kwargs):
            self.responses = self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(status='completed', output_parsed=Candidate(actions=contract.steps), output_text='fixture')
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-test-key')
    monkeypatch.setenv('OPENAI_MODEL', 'offline-test-model')
    monkeypatch.setattr(openai, 'OpenAI', OfflineTransport)
    candidate, raw, model = propose(EvaluateRequest(mode=mode, text='' if mode == 'IMAGE' else '외부 입력', provider='openai'), contract, world, camera_data_url(world))
    assert candidate.actions == contract.steps
    assert [item['type'] for item in captured['input'][0]['content']] == types
    assert captured['instructions'].startswith(contract.system_prompt)
    assert captured['store'] is False
    assert model == 'offline-test-model'
