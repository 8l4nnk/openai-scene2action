import copy
import json
from pathlib import Path

import pytest

from isaac.normal_baseline.contract import validate


def config():
    root=Path(__file__).resolve().parents[1]/'isaac/normal_baseline'
    return (json.loads((root/'S05_config.json').read_text(encoding='utf-8')),
            json.loads((root/'k2a_workcell_v1.json').read_text(encoding='utf-8')))


def test_normal_s05_contract_has_only_ordered_ball_placements():
    scenario, settings=config()
    validate(scenario,settings)


def test_nonexecuting_mode_is_rejected_before_isaac_import():
    import subprocess
    import sys
    script=Path(__file__).resolve().parents[1]/'isaac/normal_baseline/normal_workcell.py'
    result=subprocess.run([sys.executable,str(script),'--scenario','S05','--run-id','test',
                           '--mode','setup'],capture_output=True,text=True)
    assert result.returncode==2
    assert "invalid choice: 'setup'" in result.stderr


@pytest.mark.parametrize('change', ['order','target','person','nan','out_of_zone'])
def test_modified_normal_contract_rejected_before_simulator_start(change):
    scenario, settings=copy.deepcopy(config())
    if change=='order': scenario['oracle_plan'].reverse()
    if change=='target': scenario['oracle_plan'][0]['zone']='2'
    if change=='person': scenario['oracle_plan'][0]['object_id']='person'
    if change=='nan': scenario['oracle_plan'][0]['target_position_table_m'][0]=float('nan')
    if change=='out_of_zone': scenario['oracle_plan'][0]['target_position_table_m'][0]=0.5
    with pytest.raises(ValueError): validate(scenario,settings)
