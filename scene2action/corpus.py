"""Read existing cases and evaluate a defensive classifier, never execute actions."""
import argparse
import base64
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .guard import classify


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_cases(source, root):
    return load_dataset(source, root)['cases']


def load_dataset(source, root):
    root = Path(root).resolve()
    source = Path(source).resolve()
    if not source.is_relative_to(root) or source.suffix != '.jsonl':
        raise ValueError('JSONL source must be within the dataset root')
    if source.stat().st_size > 64*1024*1024:
        raise ValueError('Dataset exceeds 64 MiB')
    snapshot=source.read_bytes()
    if len(snapshot)>64*1024*1024:
        raise ValueError('Dataset exceeds 64 MiB')
    cases, ids = [], set()
    for line_no, line in enumerate(snapshot.decode('utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        case_id = row.get('case_id')
        if not isinstance(case_id,str) or not case_id or case_id in ids:
            raise ValueError(f'Missing or duplicate case ID at line {line_no}')
        ids.add(case_id)
        mode = {'TEXT_ONLY':'TEXT', 'TEXT':'TEXT', 'IMAGE':'IMAGE', 'IMAGE_TEXT':'IMAGE_TEXT',
                'IMAGE_ONLY':'IMAGE', 'IMAGE_ONLY_WITH_MAPPING_SYSTEM_PROMPT':'IMAGE'}.get(
                    row.get('input_modality',row.get('input_channel')))
        if not mode:
            raise ValueError(f'Unsupported mode at line {line_no}')
        text = row.get('operator_text',row.get('model_user_text')) or ''
        if not isinstance(text,str) or len(text)>16000 or (mode=='IMAGE' and text) or (mode!='IMAGE' and not text.strip()):
            raise ValueError(f'Invalid text at line {line_no}')
        text_hash = sha(text.encode())
        declared = row.get('operator_text_sha256',row.get('model_user_text_sha256'))
        if declared and declared != text_hash:
            raise ValueError(f'Text hash mismatch at line {line_no}')
        image, image_hash = None, None
        if mode != 'TEXT':
            ref = row.get('image_card_path',row.get('image_path'))
            if not isinstance(ref,str) or not ref:
                raise ValueError(f'Missing image at line {line_no}')
            image = (root/ref).resolve()
            if not image.is_relative_to(root):
                raise ValueError('Image escapes dataset root')
            if image.stat().st_size > 8*1024*1024:
                raise ValueError('Image exceeds 8 MiB')
            image_hash = sha(image.read_bytes())
            expected = row.get('image_card_sha256',row.get('image_sha256'))
            if not expected or expected != image_hash:
                raise ValueError(f'Image hash missing or mismatched at line {line_no}')
            with Image.open(image) as im:
                if im.format not in ('PNG','JPEG') or im.width*im.height > 16_000_000:
                    raise ValueError('Unsupported image format or size')
                im.verify()
        label = {'ATTACK_TEST':'ATTACK','MATCHED_CONTROL':'CONTROL'}.get(row.get('record_type'),'UNKNOWN')
        cases.append(dict(case_id=case_id, line=line_no, mode=mode, text=text, image=image,
                          label=label, text_sha256=text_hash, image_sha256=image_hash,
                          fingerprint=sha(json.dumps([mode,text_hash,image_hash]).encode())))
    if not cases:
        raise ValueError('No cases')
    return dict(cases=cases, source_sha256=sha(snapshot))


def image_data(case):
    if case['image'] is None:
        return None
    data = case['image'].read_bytes()
    if sha(data) != case['image_sha256']:
        raise ValueError('Image changed after validation')
    mime = 'image/png' if data.startswith(b'\x89PNG') else 'image/jpeg'
    return 'data:'+mime+';base64,'+base64.b64encode(data).decode()


def summarize(rows):
    dry_runs=sum(row['error']=='DRY_RUN' for row in rows)
    rows=[row for row in rows if row['error']!='DRY_RUN']
    groups = {}
    for row in rows:
        g=groups.setdefault(row['label'],dict(BLOCK=0,HOLD=0,PASS=0,errors=0,n=0))
        g[row['decision']]+=1
        g['errors']+=bool(row['error'])
        g['n']+=1
    times=sorted(row['latency_ms'] for row in rows)
    return dict(n=len(rows),dry_runs=dry_runs,by_label=groups,
                latency_ms={f'p{q}':times[math.ceil(len(times)*q/100)-1] if times else None for q in (50,95,99)},
                interpretation='Label agreement only; controls require trusted normal-work mapping before false-positive claims. HOLD and provider errors are not counted as successful detections.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--policy',type=Path,default=Path('policies/industrial-input-screening.txt'))
    parser.add_argument('--provider',choices=('openai','openrouter','runpod'),default='openrouter')
    parser.add_argument('--model')
    parser.add_argument('--limit',type=int,default=8)
    parser.add_argument('--live',action='store_true',help='Send bounded selected inputs to the configured model; may incur cost')
    args=parser.parse_args()
    if not 1<=args.limit<=2000 or (args.live and not args.model):
        parser.error('limit must be 1..2000; live requires an explicit model')
    dataset=load_dataset(args.source,args.root)
    cases=dataset['cases']
    # Interleave available label groups; preserve source order within each group.
    buckets={label:[c for c in cases if c['label']==label] for label in sorted({c['label'] for c in cases})}
    selected=[]
    while len(selected)<min(args.limit,len(cases)):
        for bucket in buckets.values():
            if bucket and len(selected)<args.limit:
                selected.append(bucket.pop(0))
    policy=args.policy.read_text(encoding='utf-8')
    manifest=dict(source=str(args.source.resolve()),source_sha256=dataset['source_sha256'],
                  policy_sha256=sha(policy.encode()),model=args.model,provider=args.provider,
                  created_at=datetime.now(timezone.utc).isoformat(),total=len(cases),selected=len(selected),
                  labels=dict(Counter(c['label'] for c in cases)),
                  duplicate_inputs=len(cases)-len({c['fingerprint'] for c in cases}),live=args.live)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[]
    with (args.output/'results.jsonl').open('w',encoding='utf-8') as output:
        for c in selected:
            record={k:c[k] for k in ('case_id','line','mode','label','fingerprint')}
            if args.live:
                record.update(classify(policy,c['mode'],c['text'],image_data(c),args.model,args.provider))
            else:
                record.update(decision='HOLD',category='UNCERTAIN',error='DRY_RUN',latency_ms=0)
            rows.append(record)
            output.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
            output.flush()
    summary=summarize(rows)
    (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(manifest=manifest,summary=summary),ensure_ascii=False))


if __name__=='__main__':
    main()
