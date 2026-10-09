'use strict';
(()=>{
  const el=id=>document.getElementById(id);
  let cases=[],sequence=0,batch=null;
  const text=(tag,value,cls)=>{const n=document.createElement(tag);n.textContent=value;if(cls)n.className=cls;return n;};
  async function get(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw Error('응답 확인 필요');return r.json();}
  async function showCase(){
    const seq=++sequence,cid=el('demo-case').value;
    if(!cid)return;
    try{
      const d=await get('/api/demo/cases/'+encodeURIComponent(cid));if(seq!==sequence)return;
      renderDetail(d);
    }catch{if(seq===sequence){el('demo-selected').textContent='선택 사례 확인 불가';el('demo-input').textContent='';el('demo-response').textContent='';el('demo-image').hidden=true;el('demo-provenance').textContent='';el('demo-stages').replaceChildren(text('p','사례를 읽지 못했습니다.'));el('demo-dispatch').textContent='현재 판정 확인 불가';}}
  }
  function renderDetail(d){
      const cid=d.case.case_id;
      el('demo-selected').textContent=`선택 사례 ${cid} · 과거 Qwen ${d.qwen.decision} → ${d.evaluation.final} · ${d.input_screen?'기존 Astra 입력 선별 + 현재 계약 검사':'무결성 + 현재 계약 검사'}`;
      el('demo-input').textContent=d.case.modality==='TEXT'?d.case.operator_text:'IMAGE ONLY · 사용자 텍스트 없음';
      el('demo-image').hidden=d.case.modality!=='IMAGE';
      if(d.case.modality==='IMAGE')el('demo-image').src='/api/demo/images/'+encodeURIComponent(cid);
      el('demo-response').textContent=typeof d.qwen.raw_response==='string'?d.qwen.raw_response:JSON.stringify(d.qwen.raw_response,null,2);
      el('demo-stages').replaceChildren(...d.evaluation.stages.map(s=>{const box=text('div','',`demo-stage ${s.decision}`);box.append(text('strong',`${s.stage} · ${{PASS:'통과',BLOCK:'차단',HOLD:'보류',SKIP:'미실행'}[s.decision]}`),text('p',s.reason));return box;}));
      el('demo-dispatch').textContent=`Isaac 전송: ${d.evaluation.isaac_dispatched?'전송됨':'0건 · 실행되지 않음'} / 최종 ${d.evaluation.final}`;
      el('demo-provenance').textContent=`${d.case.dataset} · ${d.qwen.model} · 기존 판정 ${d.qwen.decision} · ${d.qwen.finished_at_utc||'시각 미기록'} · 입력 SHA-256 ${d.case.input_sha256}`;
  }
  function filter(){
    const selected=cases.filter(c=>(el('demo-mode').value==='ALL'||c.modality===el('demo-mode').value)&&(el('demo-verdict').value==='ALL'||c.qwen_decision===el('demo-verdict').value));
    el('demo-case').replaceChildren(...selected.map(c=>{const o=text('option',`${c.case_id} · ${c.qwen_decision}`);o.value=c.case_id;return o;}));showCase();
  }
  function distribution(d){
    el('demo-distribution-scope').textContent=`텍스트 EXECUTE ${d.total}건 재검사 완료 · 모델 신규 호출 0건 · Isaac 전송 0건`;
    el('demo-block-bars').replaceChildren(...Object.entries(d.first_block).map(([stage,count])=>{
      const box=text('div','', 'demo-block-row'),bar=document.createElement('progress');
      bar.max=Math.max(d.total,1);bar.value=count;
      const label=stage==='HOLD'?'보류 · 차단 성공 제외':`${stage} 최초 차단`;
      bar.setAttribute('aria-label',label);
      box.append(text('span',label),bar,text('strong',`${count}건 · ${d.total?(count/d.total*100).toFixed(1):'0.0'}%`));return box;
    }));
    el('demo-distribution').replaceChildren(...Object.entries(d.stages).map(([stage,counts])=>{
      const row=document.createElement('tr'),name=text('th',stage);name.scope='row';row.append(name);
      for(const verdict of ['PASS','BLOCK','HOLD','SKIP'])row.append(text('td',String(counts[verdict])));return row;
    }));
  }
  async function camera(){
    try{
      const s=await get('/api/isaac/state'),age=s.camera_age_s;
      const fresh=typeof age==='number'&&age<=10;
      el('isaac-status').textContent=`${fresh?'카메라 수신 중':'오래된 프레임 / 카메라 확인 필요'} · 촬영 후 ${age??'—'}초 · 정상 운반 ${s.normal_motion_verified?'성공 확인':'미검증'} · ${s.state||'대기'}`;
      el('isaac-status').dataset.fresh=String(fresh);
      for(const k of ['observer','rgb'])el('isaac-'+k).src='/api/isaac/'+k+'?t='+Date.now();
    }catch{el('isaac-status').textContent='Pod 카메라 연결 끊김 · 아래 영상은 현재 상태를 보장하지 않습니다.';el('isaac-status').dataset.fresh='false';}
    setTimeout(camera,3000);
  }
  el('demo-mode').addEventListener('change',filter);el('demo-verdict').addEventListener('change',filter);el('demo-case').addEventListener('change',showCase);
  el('demo-batch').addEventListener('click',async()=>{
    el('demo-batch').disabled=true;el('demo-distribution-scope').textContent='입력 해시·기존 판정·현재 계약 검사 중';
    try{batch=await get('/api/demo/screened-batch');distribution(batch);for(const stage of ['F1','F2'])el('demo-'+stage.toLowerCase()+'-example').disabled=!batch.examples[stage];}
    catch{batch=null;el('demo-distribution-scope').textContent='검사 실패 · 결과를 확인할 수 없습니다.';el('demo-block-bars').replaceChildren();el('demo-distribution').replaceChildren();for(const stage of ['f1','f2'])el('demo-'+stage+'-example').disabled=true;}
    finally{el('demo-batch').disabled=false;}
  });
  for(const stage of ['F1','F2'])el('demo-'+stage.toLowerCase()+'-example').addEventListener('click',()=>{
    const d=batch?.examples[stage];if(!d)return;
    el('demo-mode').value='TEXT';el('demo-verdict').value='EXECUTE';filter();++sequence;
    el('demo-case').value=d.case.case_id;el('demo-response-detail').open=true;renderDetail(d);
  });
  get('/api/demo/cases').then(d=>{cases=d.cases;const s=d.summary;el('demo-summary').textContent=`기존 Qwen EXECUTE: 텍스트 ${s.groups.TEXT.qwen_execute}/270 · 이미지 ${s.groups.IMAGE.qwen_execute}/64 · 전체 ${s.total}건`;filter();}).catch(()=>{el('demo-summary').textContent='코퍼스 파일·무결성 확인 필요';el('demo-distribution-scope').textContent='분포 집계 확인 불가';});
  camera();
})();
