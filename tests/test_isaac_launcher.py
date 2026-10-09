import json
import subprocess

from isaac.baseline_launcher import run_baseline


def test_failed_retry_gets_new_identity_and_never_retains_success(tmp_path):
    def run(*args,**kwargs):
        return subprocess.CompletedProcess(args[0],0)
    first=run_baseline(tmp_path,tmp_path,runner=run)
    def fail(*args,**kwargs):
        return subprocess.CompletedProcess(args[0],1)
    second=run_baseline(tmp_path,tmp_path,runner=fail)
    state=json.loads((tmp_path/'current.json').read_text(encoding='utf-8'))
    assert first!=second
    assert state['run_id']==second
    assert state['state']=='FINISHED' and state['process_exit']==1


def test_process_timeout_is_recorded_as_failure(tmp_path):
    def timeout(*args,**kwargs):
        raise subprocess.TimeoutExpired('test',900)
    run_baseline(tmp_path,tmp_path,runner=timeout)
    state=json.loads((tmp_path/'current.json').read_text(encoding='utf-8'))
    assert state['process_exit']==124
