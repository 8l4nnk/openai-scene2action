"""Copy the user-selected, existing corpus; never call a model or controller."""
import argparse
import hashlib
import json
from pathlib import Path
import re

MODEL = 'qwen/qwen3-vl-32b-instruct'


def digest(b):
    return hashlib.sha256(b).hexdigest()


def rows(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()]


def write(path, value):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False)+'\n' for r in value), encoding='utf-8')


def main(root, target):
    root, target = Path(root).resolve(), Path(target).resolve()
    if target.exists():
        raise ValueError('Destination already exists; refusing to overwrite')
    text_base = root/'2026-10-07/텍스트공격_축소8종_명시절차R15_20261007'
    image_base = root/'2026-10-08/VPI_논문방법비례_공격64_R19_20261008'
    sources = {
        'text': text_base/'텍스트공격_축소S8_270건_R15.jsonl',
        'image': image_base/'cases64_paper_weighted_attack_only.jsonl',
        'text_results': text_base/'VLM우선검사_3모델/텍스트공격270_3모델_VLM원문.jsonl',
        'image_results': image_base/'VLM우선검사_3모델_R23_사용자시스템프롬프트/패치이미지64_3모델_VLM원문.jsonl',
    }
    datasets = {k: rows(p) for k,p in sources.items()}
    assert len(datasets['text']) == 270 and len(datasets['image']) == 64
    cases, images = [], {}
    for kind in ('text','image'):
        seen = set()
        for r in datasets[kind]:
            cid = r['case_id']
            if not re.fullmatch(r'[A-Za-z0-9_-]+',cid) or cid in seen:
                raise ValueError('Invalid or duplicate case ID')
            seen.add(cid)
            c = dict(case_id=cid, modality=kind.upper(), dataset='R15' if kind=='text' else 'R23',
                     harmful_action_id=r.get('harmful_action_id'), operator_text=r.get('operator_text',''))
            if kind == 'text':
                assert digest(c['operator_text'].encode()) == r['operator_text_sha256']
                c['input_sha256'] = r['operator_text_sha256']
            else:
                assert not c['operator_text']
                source = (root.parent.parent/r['image_card_path']).resolve()
                assert source.is_relative_to(root)
                b = source.read_bytes()
                assert digest(b) == r['image_card_sha256']
                relative = 'images/'+cid+'.png'
                images[relative] = b
                c.update(image_path=relative,input_sha256=digest(b),image_goal_text=r.get('image_goal_text',''))
            cases.append(c)
    index = {r['case_id']:r for r in cases}
    assert len(index)==334
    results=[]
    for kind in ('text','image'):
        for r in datasets[kind+'_results']:
            c=index[r['case_id']]
            assert c['input_sha256']==r.get('operator_text_sha256',r.get('image_sha256'))
            keep=('case_id','model','model_label','decision','parsed_plan','raw_response','response_id',
                  'latency_s','error','finished_at_utc')
            result={k:r.get(k) for k in keep}
            result.update(input_sha256=c['input_sha256'],dataset=c['dataset'],source='historical_vlm_response',
                          physical_execution=False)
            results.append(result)
    qwen=[r for r in results if r['model']==MODEL]
    assert len(qwen)==334 and len({r['case_id'] for r in qwen})==334
    # Never copy request envelopes, credentials, base64 images, or source paths.
    serialized=json.dumps([cases,results],ensure_ascii=False)
    if re.search(r'(?:sk-(?:or-v1-)?[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN .*PRIVATE KEY)',serialized):
        raise ValueError('Potential secret detected; export stopped')
    target.mkdir()
    (target/'images').mkdir()
    for p,b in images.items(): (target/p).write_bytes(b)
    write(target/'text-270.jsonl',[r for r in cases if r['modality']=='TEXT'])
    write(target/'image-r23-64.jsonl',[r for r in cases if r['modality']=='IMAGE'])
    write(target/'vlm-results.jsonl',results)
    write(target/'qwen-results.jsonl',qwen)
    manifest=dict(version=1,counts={'text':270,'image':64,'qwen_results':334,'all_vlm_results':len(results)},
                  source_sha256={k:digest(p.read_bytes()) for k,p in sources.items()},
                  files={str(p.relative_to(target)).replace('\\','/'):digest(p.read_bytes()) for p in target.rglob('*') if p.is_file()})
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest['counts']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--target',default='demo')
    a=p.parse_args();main(a.root,a.target)
