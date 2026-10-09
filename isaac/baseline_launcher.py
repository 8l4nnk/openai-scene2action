"""Run one normal-only Isaac baseline and bind evidence to a fresh run ID."""
import json
import subprocess
import time
import uuid
from pathlib import Path


def run_baseline(root, code_dir, runner=subprocess.run):
    root.mkdir(parents=True,exist_ok=True)
    run_id='normal-'+uuid.uuid4().hex
    state={'run_id':run_id,'state':'RUNNING','process_exit':None,'started_at':time.time()}
    def save():
        temporary=root/'current.json.tmp'
        temporary.write_text(json.dumps(state),encoding='utf-8')
        temporary.replace(root/'current.json')
    save()
    try:
        result=runner(['/isaac-sim/python.sh',str(code_dir/'normal_workcell.py'),
                       '--scenario','S05','--run-id',run_id,'--output-root',str(root)],
                      cwd=code_dir,timeout=900,check=False)
        code=result.returncode
    except subprocess.TimeoutExpired:
        code=124
    except OSError:
        code=125
    state.update(state='FINISHED',process_exit=code,finished_at=time.time())
    save()
    print('S2A_BASELINE_PROCESS',json.dumps(state),flush=True)
    return run_id


if __name__=='__main__':
    run_baseline(Path('/tmp/s2a-normal-evidence'),Path('/tmp/s2a-normal-code'))
