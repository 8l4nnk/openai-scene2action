import hashlib
import json

import pytest

from scene2action.guard import GuardVerdict, build_messages, classify
from scene2action.corpus import load_cases, summarize


def test_openai_request_uses_supported_parameters_and_no_router_settings():
    requests=[]
    def transport(**body):
        requests.append(body)
        return {'model':'gpt-6-astra','choices':[{'finish_reason':'stop','message':{
            'content':'{"decision":"BLOCK","category":"INJECTION"}'}}]}
    result=classify('normal','TEXT','untrusted input',None,'gpt-6-astra',
                    provider='openai',transport=transport)
    assert result['decision']=='BLOCK'
    assert result['response_model']=='gpt-6-astra'
    assert requests[0]['max_completion_tokens']==1024
    assert requests[0]['reasoning_effort']=='low'
    assert requests[0]['store'] is False
    assert not {'max_tokens','provider','reasoning','tools'} & requests[0].keys()


def test_openai_key_alias_and_fixed_endpoint(monkeypatch):
    from scene2action.guard import endpoint_config
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setenv('OPENAI_KEY','alias-test-credential')
    monkeypatch.setenv('OPENAI_BASE_URL','https://untrusted.invalid')
    assert endpoint_config('openai')==('https://api.openai.com/v1','alias-test-credential')
    monkeypatch.setenv('OPENAI_API_KEY','primary-test-credential')
    assert endpoint_config('openai')[1]=='primary-test-credential'


@pytest.mark.parametrize('message,finish', [({'content':None,'refusal':'refused'},'stop'),
                                          ({'content':'{"decision":"PASS","category":"NORMAL"}'},'length')])
def test_openai_refusal_or_truncation_is_hold(message,finish):
    result=classify('normal','TEXT','input',None,'gpt-6-astra',provider='openai',
                    transport=lambda **kw: {'choices':[{'finish_reason':finish,'message':message}]})
    assert result['decision']=='HOLD'
    assert result['error']=='INVALID_RESPONSE_OR_CONFIGURATION'


@pytest.mark.parametrize('model,expected', [('qwen/qwen3-vl-32b-instruct', None),
                                           ('anthropic/claude-opus-5.5', {'effort':'low'})])
def test_openrouter_reasoning_only_for_confirmed_supported_model(model, expected):
    requests=[]
    def transport(**body):
        requests.append(body)
        return {'choices':[{'finish_reason':'stop','message':{
            'content':'{"decision":"PASS","category":"NORMAL"}'}}]}
    result=classify('normal','TEXT','normal',None,model,transport=transport)
    assert result['decision']=='PASS'
    assert requests[0].get('reasoning')==expected
    assert requests[0]['provider']=={'require_parameters':True,'allow_fallbacks':False}


def test_image_only_request_does_not_invent_user_text_or_leak_labels():
    messages = build_messages('Normal work.', 'IMAGE', '', 'data:image/png;base64,YQ==')
    assert messages[0]['role'] == 'system'
    assert messages[1]['content'] == [{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,YQ=='}}]


def test_classifier_error_is_hold_and_does_not_expose_credentials():
    def failed(*args, **kwargs):
        raise RuntimeError('secret-key')
    result = classify('normal', 'TEXT', 'normal', None, 'test', transport=failed)
    assert result['decision'] == 'HOLD'
    assert result['error'] == 'MODEL_UNAVAILABLE'
    assert 'secret-key' not in json.dumps(result)


@pytest.mark.parametrize('reply', ['{"decision":"PASS","category":"NORMAL","actions":[]}',
                                 '{"decision":"ALLOW","category":"NORMAL"}',
                                 'not json'])
def test_bad_classifier_output_fails_closed(reply):
    def transport(**kwargs):
        return {'choices':[{'finish_reason':'stop','message':{'content':reply}}]}
    assert classify('normal','TEXT','normal',None,'test',transport=transport)['decision'] == 'HOLD'


def test_corpus_preserves_labels_but_only_passes_input_to_model(tmp_path):
    p=tmp_path/'cases.jsonl'
    row={'case_id':'a','record_type':'MATCHED_CONTROL','input_modality':'TEXT_ONLY',
         'operator_text':'normal','operator_text_sha256':hashlib.sha256(b'normal').hexdigest(),
         'expected_plan_for_scoring_only':['never send this']}
    p.write_text(json.dumps(row)+'\n',encoding='utf-8')
    cases=load_cases(p,tmp_path)
    assert cases[0]['label']=='CONTROL'
    assert 'never send this' not in json.dumps(build_messages('policy',cases[0]['mode'],cases[0]['text'],None))
    row['operator_text']='changed'
    p.write_text(json.dumps(row),encoding='utf-8')
    with pytest.raises(ValueError,match='hash'):
        load_cases(p,tmp_path)


def test_image_path_cannot_escape_dataset_root(tmp_path):
    p=tmp_path/'cases.jsonl'
    p.write_text(json.dumps({'case_id':'x','input_channel':'IMAGE_ONLY_WITH_MAPPING_SYSTEM_PROMPT',
                            'image_card_path':'../private.png','image_card_sha256':'0'*64}),encoding='utf-8')
    with pytest.raises(ValueError,match='root'):
        load_cases(p,tmp_path)


def test_metrics_separate_block_hold_pass_and_transport_failures():
    rows=[{'label':'ATTACK','decision':'BLOCK','latency_ms':10,'error':None},
          {'label':'ATTACK','decision':'HOLD','latency_ms':20,'error':'MODEL_UNAVAILABLE'},
          {'label':'CONTROL','decision':'PASS','latency_ms':30,'error':None}]
    result=summarize(rows)
    assert result['by_label']['ATTACK']=={'BLOCK':1,'HOLD':1,'PASS':0,'errors':1,'n':2}
    assert result['latency_ms']['p95']==30
    assert 'accuracy' not in result


def test_dry_run_is_not_reported_as_model_latency_or_detection():
    result=summarize([{'label':'UNKNOWN','decision':'HOLD','error':'DRY_RUN','latency_ms':0}])
    assert result['n']==0 and result['dry_runs']==1
    assert not result['by_label']
    assert result['latency_ms']['p95'] is None


def test_manifest_hash_matches_parsed_snapshot_if_source_changes(tmp_path, monkeypatch):
    from pathlib import Path
    from scene2action.corpus import main
    source=tmp_path/'source.jsonl'
    original=json.dumps({'case_id':'a','input_modality':'TEXT_ONLY','operator_text':'normal'}).encode()
    source.write_bytes(original)
    policy=tmp_path/'policy.txt'
    policy.write_text('policy',encoding='utf-8')
    output=tmp_path/'report'
    read_bytes,read_text=Path.read_bytes,Path.read_text
    changed=False
    def change_after_read(path,value):
        nonlocal changed
        if path==source and not changed:
            changed=True
            source.write_bytes(original.replace(b'normal',b'changed'))
        return value
    monkeypatch.setattr(Path,'read_bytes',lambda p:change_after_read(p,read_bytes(p)))
    monkeypatch.setattr(Path,'read_text',lambda p,*a,**kw:change_after_read(p,read_text(p,*a,**kw)))
    monkeypatch.setattr('sys.argv',['corpus','--source',str(source),'--root',str(tmp_path),
                                  '--output',str(output),'--policy',str(policy)])
    main()
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    assert changed
    assert manifest['source_sha256']==hashlib.sha256(original).hexdigest()
