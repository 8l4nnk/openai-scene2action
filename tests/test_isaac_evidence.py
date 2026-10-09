import json
from pathlib import Path

from isaac.evidence_viewer import evidence_state


def test_missing_result_never_claims_simulation_success(tmp_path):
    assert evidence_state(tmp_path)['state']=='AWAITING_EVIDENCE'


def test_pass_flag_alone_is_not_normal_task_proof(tmp_path):
    (tmp_path/'current.json').write_text(json.dumps({'run_id':'normal-'+'a'*32,'state':'FINISHED','process_exit':0}),encoding='utf-8')
    result=tmp_path/'results/S05'/('normal-'+'a'*32+'.json')
    result.parent.mkdir(parents=True)
    result.write_text(json.dumps({'status':'PASS','full_scenario_success':True}),encoding='utf-8')
    assert evidence_state(tmp_path)['state']=='INCOMPLETE_EVIDENCE'


def test_both_observed_placements_required_and_only_allowlisted_fields_returned(tmp_path):
    (tmp_path/'current.json').write_text(json.dumps({'run_id':'normal-'+'a'*32,'state':'FINISHED','process_exit':0}),encoding='utf-8')
    result=tmp_path/'results/S05'/('normal-'+'a'*32+'.json')
    result.parent.mkdir(parents=True)
    data={'run_id':'normal-'+'a'*32,'status':'PASS','full_scenario_success':True,'oracle_executor':True,
          'final_evaluations':{n:{'success':True,'checks':{
              'supported_on_table':True,'whole_projection_with_10mm_margin':True,
              'stable_2s':True,'upright':True,'assigned_slot':True}}
                               for n in ('S05_sphere_red','S05_sphere_blue')},
          'executions':[{'planned_object':n,'evaluation':{'success':True,'checks':{
              'released':True,'only_selected_robot_contact':True,'nontarget_preserved':True}}}
              for n in ('S05_sphere_red','S05_sphere_blue')],
          'secret':'do not expose','commands':['private']}
    result.write_text(json.dumps(data),encoding='utf-8')
    assert evidence_state(tmp_path)['state']=='BASELINE_PASS'
    assert 'do not expose' not in json.dumps(evidence_state(tmp_path))
    (tmp_path/'current.json').write_text(json.dumps({'run_id':'normal-'+'a'*32,'state':'FINISHED','process_exit':False}),encoding='utf-8')
    assert evidence_state(tmp_path)['state']=='AWAITING_EVIDENCE'
    (tmp_path/'current.json').write_text(json.dumps({'run_id':'normal-'+'b'*32,'state':'RUNNING','process_exit':None}),encoding='utf-8')
    assert evidence_state(tmp_path)['state']=='RUNNING_BASELINE'
    (tmp_path/'current.json').write_text(json.dumps({'run_id':'normal-'+'a'*32,'state':'FINISHED','process_exit':1}),encoding='utf-8')
    assert evidence_state(tmp_path)['state']=='BASELINE_FAIL'
    (tmp_path/'current.json').write_text(json.dumps({'run_id':'normal-'+'a'*32,'state':'FINISHED','process_exit':0}),encoding='utf-8')
    data['final_evaluations']['S05_sphere_blue']['success']=False
    result.write_text(json.dumps(data),encoding='utf-8')
    assert evidence_state(tmp_path)['state']=='INCOMPLETE_EVIDENCE'


def test_parent_symlink_cannot_expose_external_evidence(tmp_path):
    import pytest
    from isaac.evidence_viewer import safe_file
    root=tmp_path/'evidence'; root.mkdir()
    outside=tmp_path/'outside'; outside.mkdir()
    (outside/'frame.png').write_bytes(b'private')
    try:
        (root/'process_assets').symlink_to(outside,target_is_directory=True)
    except OSError:
        pytest.skip('Host does not permit symlink creation')
    assert safe_file(root,root/'process_assets/frame.png') is None
