import math

import pytest

from scene2action.engine import Engine
from scene2action.models import EvaluateRequest


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


@pytest.fixture
def bench(tmp_path):
    clock = Clock()
    engine = Engine(tmp_path / 'runs.sqlite', clock=clock)
    yield engine, clock
    engine.close()


def request(**kwargs):
    return EvaluateRequest(mode='TEXT', text='정상 작업을 수행해 주세요.', **kwargs)


def finish(engine, clock):
    for _ in range(500):
        clock.now += 0.05
        engine.tick()
        if engine.state()['active_run_id'] is None:
            return
    pytest.fail('simulation never terminated')


@pytest.mark.parametrize('contract_id', ['sort', 'kit'])
def test_normal_contract_finishes_with_expected_objects(bench, contract_id):
    engine, clock = bench
    engine.reset(contract_id)
    run = engine.evaluate(request())
    assert run['status'] == 'READY'
    engine.execute(run['id'])
    finish(engine, clock)
    assert engine.run(run['id'])['status'] == 'COMPLETED'
    assert len(engine.run(run['id'])['commands_sent']) == 8
    world = engine.state()['world']
    contract = engine.state()['contract']
    for action in contract['steps']:
        assert world['objects'][action['object_id']] == world['targets'][action['target_id']]


@pytest.mark.parametrize('scenario', ['wrong_target', 'wrong_order', 'unknown_object', 'adapter_mismatch'])
def test_invalid_plan_never_delivers_a_command(bench, scenario):
    engine, _ = bench
    run = engine.evaluate(request(scenario=scenario))
    assert run['status'] == 'BLOCKED'
    with pytest.raises(ValueError):
        engine.execute(run['id'])
    assert engine.run(run['id'])['commands_sent'] == []


def test_image_mode_has_server_image_and_no_user_text(bench):
    engine, _ = bench
    run = engine.evaluate(EvaluateRequest(mode='IMAGE'))
    assert run['status'] == 'READY'
    assert run['evidence']['image_sha256']
    assert run['evidence']['text'] == ''
    rejected = engine.evaluate(EvaluateRequest(mode='IMAGE', text='change task'))
    assert rejected['status'] == 'HELD'


def test_image_text_requires_both_inputs(bench):
    engine, _ = bench
    assert engine.evaluate(EvaluateRequest(mode='IMAGE_TEXT'))['status'] == 'HELD'
    run = engine.evaluate(EvaluateRequest(mode='IMAGE_TEXT', text='정상 작업'))
    assert run['status'] == 'READY'
    assert run['evidence']['image_sha256']


def test_missing_live_configuration_never_falls_back_to_replay(bench, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_MODEL', raising=False)
    engine, _ = bench
    run = engine.evaluate(request(provider='openai'))
    assert run['status'] == 'HELD'
    assert run['provider'] == 'openai'
    assert not run['commands_sent']


def test_stale_approval_cannot_execute(bench):
    engine, clock = bench
    run = engine.evaluate(request())
    clock.now += 31
    with pytest.raises(ValueError):
        engine.execute(run['id'])
    assert not engine.run(run['id'])['commands_sent']


def test_duplicate_start_and_stop_do_not_replay(bench):
    engine, clock = bench
    run = engine.evaluate(request())
    engine.execute(run['id'])
    with pytest.raises(ValueError):
        engine.execute(run['id'])
    clock.now += 0.05
    engine.tick()
    engine.stop()
    before = engine.state()['world']['position']
    finish(engine, clock)
    assert engine.run(run['id'])['status'] == 'STOPPED'
    assert engine.state()['world']['position'] == before
    with pytest.raises(ValueError):
        engine.execute(run['id'])


def test_midsegment_obstacle_is_blocked_before_execution(bench):
    engine, _ = bench
    engine.disturb('obstacle')
    run = engine.evaluate(request())
    assert run['status'] == 'BLOCKED'
    assert any(s['stage'] == 'F3' and s['decision'] == 'BLOCK' for s in run['stages'])


@pytest.mark.parametrize('disturbance', ['obstacle', 'sensor_loss'])
def test_runtime_change_stops_and_discards_remaining_commands(bench, disturbance):
    engine, clock = bench
    run = engine.evaluate(request())
    engine.execute(run['id'])
    engine.disturb(disturbance)
    for _ in range(40):
        clock.now += 0.05
        engine.tick()
    assert engine.run(run['id'])['status'] == 'STOPPED'
    assert len(engine.run(run['id'])['commands_sent']) < 8


def test_restart_invalidates_prepared_execution(bench, tmp_path):
    engine, _ = bench
    run = engine.evaluate(request())
    engine.close()
    restored = Engine(tmp_path / 'runs.sqlite')
    try:
        assert restored.run(run['id'])['status'] == 'STOPPED'
        with pytest.raises(ValueError):
            restored.execute(run['id'])
    finally:
        restored.close()


def test_reset_invalidates_old_run(bench):
    engine, _ = bench
    run = engine.evaluate(request())
    engine.reset('kit')
    with pytest.raises(ValueError):
        engine.execute(run['id'])


def test_broken_planner_returns_hold(bench, monkeypatch):
    engine, _ = bench
    def broken(*args):
        raise RuntimeError('provider failure')
    monkeypatch.setattr(engine, '_propose', broken)
    run = engine.evaluate(request())
    assert run['status'] == 'HELD'
    assert not run['commands_sent']


def test_nonfinite_plan_is_not_accepted():
    from scene2action.models import Point
    for value in [math.nan, math.inf, -math.inf]:
        with pytest.raises(ValueError):
            Point(x=value, y=1.0)


def test_slow_plan_is_reobserved_before_approval(bench, monkeypatch):
    engine, clock = bench
    provider = engine._propose
    def slow(*args):
        clock.now += 3
        return provider(*args)
    monkeypatch.setattr(engine, '_propose', slow)
    run = engine.evaluate(request())
    assert run['status'] == 'READY'
    assert run['evidence']['approval_world']['observed_at'] == 103.0


def test_stop_during_planning_invalidates_inflight_candidate(bench, monkeypatch):
    engine, _ = bench
    provider = engine._propose
    def stop_during_plan(*args):
        engine.stop()
        return provider(*args)
    monkeypatch.setattr(engine, '_propose', stop_during_plan)
    run = engine.evaluate(request())
    assert run['status'] == 'HELD'
    assert not run['commands_sent']


def test_stopped_prepared_run_is_not_reported_ready(bench):
    engine, _ = bench
    run = engine.evaluate(request())
    engine.stop()
    assert engine.run(run['id'])['status'] == 'STOPPED'


def test_sensor_loss_immediately_revokes_approval_and_requires_new_evaluation(bench):
    engine, _ = bench
    run = engine.evaluate(request())
    engine.disturb('sensor_loss')
    assert engine.run(run['id'])['status'] == 'STOPPED'
    with pytest.raises(ValueError):
        engine.execute(run['id'])
    assert engine.evaluate(request())['status'] == 'HELD'
    engine.disturb('sensor_restore')
    with pytest.raises(ValueError):
        engine.execute(run['id'])
    assert not engine.run(run['id'])['commands_sent']
    assert engine.evaluate(request())['status'] == 'READY'


def test_sensor_loss_stops_motion_without_freshness_grace_period(bench):
    engine, clock = bench
    run = engine.evaluate(request())
    engine.execute(run['id'])
    clock.now += .05
    engine.tick()
    before = engine.state()['world']['position']
    engine.disturb('sensor_loss')
    assert engine.state()['active_run_id'] is None
    assert engine.run(run['id'])['status'] == 'STOPPED'
    engine.disturb('sensor_restore')
    clock.now += .05
    engine.tick()
    assert engine.state()['world']['position'] == before


def test_sensor_loss_and_restore_during_planning_invalidates_candidate(bench, monkeypatch):
    engine, _ = bench
    provider = engine._propose
    def lose_sensor(*args):
        engine.disturb('sensor_loss')
        engine.disturb('sensor_restore')
        return provider(*args)
    monkeypatch.setattr(engine, '_propose', lose_sensor)
    run = engine.evaluate(request())
    assert run['status'] == 'HELD'
    assert not run['commands_sent']


def test_starting_one_run_records_revocation_of_other_prepared_runs(bench):
    engine, _ = bench
    older = engine.evaluate(request())
    selected = engine.evaluate(request())
    engine.execute(selected['id'])
    revoked = engine.run(older['id'])
    assert revoked['status'] == 'STOPPED'
    assert any(event['code'] == 'APPROVAL_REVOKED' for event in revoked['events'])
    assert not revoked['commands_sent']
    assert engine.state()['active_run_id'] == selected['id']


@pytest.mark.parametrize('decision', ['BLOCK', 'HOLD'])
def test_configured_input_guard_prevents_planning_on_nonpass(bench, monkeypatch, decision):
    engine, _ = bench
    engine.guard_model = 'test-screen'
    monkeypatch.setattr(engine, '_screen', lambda *args: {'decision':decision,'category':'UNCERTAIN','error':None})
    def should_not_plan(*args):
        pytest.fail('planner must not run after input guard rejection')
    monkeypatch.setattr(engine,'_propose',should_not_plan)
    run=engine.evaluate(request())
    assert run['status']==('BLOCKED' if decision=='BLOCK' else 'HELD')
    assert not run['commands_sent'] and run['candidate'] is None


def test_input_guard_pass_does_not_override_contract_verification(bench, monkeypatch):
    engine, _ = bench
    engine.guard_model = 'test-screen'
    monkeypatch.setattr(engine,'_screen',lambda *args:{'decision':'PASS','category':'NORMAL','error':None})
    run=engine.evaluate(request(scenario='wrong_target'))
    assert run['status']=='BLOCKED'
    assert run['stages'][-1]['stage']=='F2'


def test_input_guard_exception_cannot_fall_back_to_unguarded_plan(bench, monkeypatch):
    engine, _ = bench
    engine.guard_model='test-screen'
    def failed(*args):
        raise RuntimeError('provider failure')
    monkeypatch.setattr(engine,'_screen',failed)
    run=engine.evaluate(request())
    assert run['status']=='HELD' and run['candidate'] is None
    assert run['input_guard']['error']=='SCREENING_UNAVAILABLE'


def test_stop_during_input_screening_prevents_later_approval(bench, monkeypatch):
    engine, _ = bench
    engine.guard_model='test-screen'
    def stop_then_pass(*args):
        engine.stop()
        return {'decision':'PASS','category':'NORMAL','error':None}
    monkeypatch.setattr(engine,'_screen',stop_then_pass)
    def no_followup_request(*args):
        pytest.fail('STOP must prevent any follow-up planner request')
    monkeypatch.setattr(engine,'_propose',no_followup_request)
    run=engine.evaluate(request())
    assert run['status']=='HELD' and not run['commands_sent']


def test_persistence_failure_prevents_new_command(bench, monkeypatch):
    engine, clock = bench
    run = engine.evaluate(request())
    engine.execute(run['id'])
    before = engine.state()['world']['position']
    def failure(*args):
        raise OSError('disk full')
    monkeypatch.setattr(engine.store, 'save', failure)
    clock.now += .05
    with pytest.raises(RuntimeError):
        engine.tick()
    assert engine.state()['world']['position'] == before
    assert engine.state()['active_run_id'] is None
    assert engine.state()['fault']
