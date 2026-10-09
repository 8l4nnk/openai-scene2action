from pathlib import Path
from copy import deepcopy
from fastapi.testclient import TestClient
from scene2action.app import create_app
from scene2action.demo import DemoCorpus, evaluate, normal_steps


def test_existing_corpus_counts_and_no_dispatch():
    corpus=DemoCorpus(Path('demo'))
    summary=corpus.summary()
    assert summary['total']==334
    assert summary['qwen_execute']==207
    assert summary['groups']['TEXT']['qwen_execute']==183
    assert summary['groups']['IMAGE']['qwen_execute']==24
    assert all(not corpus.detail(cid)['evaluation']['isaac_dispatched'] for cid in corpus.cases)


def test_execute_distribution_counts_skip_separately_and_selects_real_record():
    corpus = DemoCorpus(Path('demo'))
    summary = corpus.summary()
    distribution = summary['execute_distribution']
    assert distribution['denominator'] == 207
    assert distribution['first_block'] == {'F1': 0, 'F2': 207, 'F3': 0, 'NO_BLOCK': 0}
    assert distribution['stages']['F1']['PASS'] == 207
    assert distribution['stages']['F3']['SKIP'] == 207
    assert distribution['stages']['F3']['PASS'] == 0
    assert all(sum(counts.values()) == 207 for counts in distribution['stages'].values())
    cid = summary['representative_case_id']
    assert corpus.results[cid]['decision'] == 'EXECUTE'
    # Aggregation must reflect fresh evaluation, not a hardcoded 207/207 chart.
    corpus.results[cid]['parsed_plan'] = {'decision': 'EXECUTE', 'steps': normal_steps()}
    changed = corpus.summary()['execute_distribution']
    assert changed['first_block']['F2'] == 206
    assert changed['first_block']['NO_BLOCK'] == 1
    assert changed['stages']['F3']['HOLD'] == 1


def test_tampering_and_unknown_actions_fail_before_execution():
    corpus=DemoCorpus(Path('demo'))
    cid=next(k for k,v in corpus.cases.items() if v['modality']=='TEXT')
    case=deepcopy(corpus.cases[cid]); case['operator_text']+='tamper'
    result=evaluate(case,corpus.results[cid],Path('demo'))
    assert result['stages'][0]['decision']=='BLOCK'
    assert result['stages'][1]['decision']=='SKIP'
    case=corpus.cases[cid]; response=deepcopy(corpus.results[cid])
    response.update(decision='EXECUTE',parsed_plan={'decision':'EXECUTE','steps':[{'action':'unsupported','object':'other','destination':'other'}]})
    result=evaluate(case,response,Path('demo'))
    assert result['stages'][1]['decision']=='BLOCK'
    assert result['stages'][2]['decision']=='SKIP'


def test_real_screened_batch_keeps_hold_distinct_and_binds_input_hash():
    import pytest
    corpus=DemoCorpus(Path('demo'))
    batch=corpus.screened_batch()
    assert batch['total']==183
    assert batch['first_block']=={'F1':167,'F2':4,'F3':0,'HOLD':12}
    assert batch['stages']['F2']['SKIP']==179
    assert all(sum(v.values())==183 for v in batch['stages'].values())
    assert [s['decision'] for s in batch['examples']['F1']['evaluation']['stages']]==['BLOCK','SKIP','SKIP']
    assert [s['decision'] for s in batch['examples']['F2']['evaluation']['stages']]==['PASS','BLOCK','SKIP']
    cid=batch['examples']['F2']['case']['case_id']
    assert batch['new_model_calls']==0 and batch['isaac_dispatched'] is False
    corpus.screens[cid]['fingerprint']='0'*64
    with pytest.raises(ValueError,match='provenance'):
        corpus.screened_batch()


def test_screen_error_never_becomes_f1_pass():
    corpus=DemoCorpus(Path('demo'))
    cid=corpus.screened_batch()['examples']['F2']['case']['case_id']
    corpus.screens[cid]['error']='MODEL_TIMEOUT'
    d=corpus.screened_detail(cid)
    assert [s['decision'] for s in d['evaluation']['stages']]==['HOLD','SKIP','SKIP']


def test_normal_proposal_cannot_turn_recorded_output_into_live_approval():
    corpus=DemoCorpus(Path('demo'));cid=next(k for k,v in corpus.cases.items() if v['modality']=='TEXT')
    response=deepcopy(corpus.results[cid]); response.update(decision='EXECUTE',parsed_plan={'decision':'EXECUTE','steps':normal_steps()})
    result=evaluate(corpus.cases[cid],response,Path('demo'))
    assert [s['decision'] for s in result['stages']]==['PASS','PASS','HOLD']
    assert result['isaac_dispatched'] is False


def test_dashboard_corpus_read_only_boundary(tmp_path):
    with TestClient(create_app(tmp_path/'test.sqlite',ticker=False),base_url='http://127.0.0.1:8765') as c:
        data=c.get('/api/demo/cases').json()
        cid=data['cases'][0]['case_id']
        assert c.get('/api/demo/cases/'+cid).status_code==200
        assert c.post('/api/demo/cases/'+cid+'/execute').status_code==404
        assert c.get('/api/isaac/arbitrary').status_code==404
        assert c.get('/api/demo/cases/unknown').status_code==404


def test_malformed_suffix_and_verify_parameters_cannot_pass_f2():
    corpus=DemoCorpus(Path('demo'));cid=next(k for k,v in corpus.cases.items() if v['modality']=='TEXT')
    for extra in [None, {'action':'verify','object':'red_ball','destination':'none','seconds':5}]:
        response=deepcopy(corpus.results[cid])
        response.update(decision='EXECUTE',parsed_plan={'decision':'EXECUTE','steps':normal_steps()+[extra]})
        assert evaluate(corpus.cases[cid],response,Path('demo'))['stages'][1]['decision']=='BLOCK'
