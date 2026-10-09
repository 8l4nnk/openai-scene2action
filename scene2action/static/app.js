'use strict';
const $ = (id) => document.getElementById(id);
const statuses = {READY:'실행 준비', RUNNING:'실행 중', COMPLETED:'완료', BLOCKED:'차단', HELD:'보류', STOPPED:'정지'};
const stages = [['F1','입력·관측 검증'],['GUARD','선택적 모델 입력 필터'],['PLAN','계획 생성'],['F2','정상 작업 검증'],['ADAPTER','명령열 재검증'],['F3','실행 조건 검증']];
let selectedRun = null, worldState = null, busy = false, online = false, lastRunData = null, activeRunData = null;
function node(tag, text, cls) { const el=document.createElement(tag); if(text!==undefined)el.textContent=text; if(cls)el.className=cls; return el; }
async function api(path, method='GET', body) {
  const response=await fetch(path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
  let data; try {data=await response.json();} catch {throw new Error('서버 응답을 읽지 못했습니다.');}
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'입력 형식 또는 요청 상태를 확인하세요.');
  return data;
}
function notice(message){$('message').textContent=message;$('message').hidden=!message;}
function updateButtons(){
  $('evaluate').disabled=busy||!online||!!worldState?.active_run_id||!!worldState?.fault;
  $('evaluate').textContent=busy?'검증 중…':'계획 검증하기 →';
  $('execute').disabled=busy||!online||lastRunData?.status!=='READY'||!!worldState?.active_run_id||!!worldState?.fault;
  $('contract').disabled=busy||!!worldState?.active_run_id;
}
async function action(fn){try{notice('');await fn();await refresh();await history();}catch(error){notice(error.message);}finally{busy=false;updateButtons();}}
function inputMode(){
  const imageOnly=$('mode').value==='IMAGE';
  $('text-field').hidden=imageOnly;
  $('image-field').hidden=$('mode').value==='TEXT';
  if(!$('image-field').hidden)$('camera').src='/api/camera?t='+Date.now();
}
function providerMode(){
  const live=$('provider').value==='openai';$('scenario-field').hidden=live;
  $('provider-note').textContent=live?'서버의 OPENAI_API_KEY·OPENAI_MODEL을 사용합니다. 검증 버튼을 누르면 입력이 OpenAI로 전송되고 API 비용이 발생할 수 있습니다.':'합성 재생은 텍스트·이미지를 이해하지 않습니다. 준비된 계획으로 검증 엔진을 확인합니다.';
}
function svgElement(tag, attrs, text){const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))el.setAttribute(k,String(v));if(text!==undefined)el.textContent=text;return el;}
function drawScene(world){
  const group=$('scene-content');group.replaceChildren();
  const xy=(p)=>[35+p[0]*730,35+p[1]*500];
  const add=(tag,attrs,text)=>group.append(svgElement(tag,attrs,text));
  const preview = !worldState.active_run_id && lastRunData?.status==='READY' && lastRunData.evidence.approval_world?.revision===world.revision && world.sensor_online;
  const pathRun = worldState.active_run_id ? activeRunData : preview ? lastRunData : null;
  $('scene-run').textContent=pathRun?`${worldState.active_run_id?'현재 실행 경로':'선택한 승인 경로 미리보기'} · ${pathRun.id.slice(0,12)}`:'현재 실행 없음 · 과거 기록의 경로는 표시하지 않습니다.';
  if(pathRun?.commands?.length && pathRun.contract.id===worldState.contract.id){
    const points=[pathRun.evidence.world.position,...pathRun.commands.map(c=>c.position)].map(p=>xy(p).join(',')).join(' ');
    add('polyline',{points,fill:'none',stroke:'#426874','stroke-width':2,'stroke-dasharray':'5 6'});
  }
  Object.entries(world.targets).forEach(([id,p])=>{const[x,y]=xy(p);add('rect',{x:x-34,y:y-27,width:68,height:54,rx:6,fill:'#173c41',stroke:'#53ba9d','stroke-width':1.5});add('text',{x,y:y+46,fill:'#81aea9','text-anchor':'middle','font-size':12},id);});
  world.obstacles.forEach(box=>{const[a,b]=xy(box.slice(0,2)),[c,d]=xy(box.slice(2));add('rect',{x:a,y:b,width:c-a,height:d-b,rx:4,fill:'#795c3d',stroke:'#bc9364','stroke-width':2});add('text',{x:(a+c)/2,y:(b+d)/2,fill:'#f0d5a7','font-size':12,'text-anchor':'middle'},'OBSTACLE');});
  Object.entries(world.objects).forEach(([id,p],i)=>{const[x,y]=xy(p);const color=['#fa8a75','#80b7f2'][i%2];add('circle',{cx:x,cy:y,r:17,fill:color,'fill-opacity':'.18'});add('circle',{cx:x,cy:y,r:11,fill:color});add('text',{x,y:y-25,fill:'#c5d9df','text-anchor':'middle','font-size':12},id);});
  const[x,y]=xy(world.position);add('circle',{cx:x,cy:y,r:25,fill:'none',stroke:'#b5e3df','stroke-opacity':'.3','stroke-dasharray':'3 4'});add('circle',{cx:x,cy:y,r:14,fill:'#e5f7f1'});add('circle',{cx:x,cy:y,r:5,fill:'#3e716f'});
  add('text',{x:51,y:53,fill:'#7594a3','font-size':10,'letter-spacing':2},'SIMULATED WORKCELL');
}
function renderRun(run){
  lastRunData=run;
  $('pipeline').replaceChildren(...stages.map(([key,title],index)=>{
    const s=run?.stages.find(item=>item.stage===key),el=node('div',undefined,'step '+(s?.decision||''));
    el.append(node('span',s?.decision==='PASS'?'✓':s?.decision==='BLOCK'?'×':s?.decision==='HOLD'?'!':String(index+1),'step-icon'));
    const heading=node('div',undefined,'step-name');heading.append(node('span',title),node('span',s?`${s.duration_ms.toFixed(2)} ms`:'—','step-time'));el.append(heading);
    const description=node('p');if(s)description.append(node('span',({PASS:'통과',BLOCK:'차단',HOLD:'보류'})[s.decision]||s.decision,'step-decision '+s.decision));
    description.append(document.createTextNode(s?.reason||(key==='GUARD'&&run&&!run.input_guard?.enabled?'모델 입력 필터 미사용 · 서버 설정으로 활성화합니다.':'앞 단계의 검증 결과를 기다립니다.')));el.append(description);return el;
  }));
  $('verdict-status').textContent=run?(statuses[run.status]||run.status):'평가 대기';
  $('verdict').dataset.state=run?.status||'idle';
  $('verdict-reason').textContent=run?.reason||'계획 검증을 실행하면 단계별 근거가 여기에 표시됩니다.';
  $('export').classList.toggle('disabled',!run);$('export').setAttribute('aria-disabled',String(!run));
  if(run)$('export').href=`/api/runs/${run.id}/export`;else $('export').removeAttribute('href');
  const events=run?.events||[];$('timeline').classList.toggle('empty',!events.length);
  if(!events.length)$('timeline').textContent='명령이 전달되면 의도·완료·정지 이벤트를 순서대로 표시합니다.';
  else $('timeline').replaceChildren(...events.map(event=>{const el=node('div',undefined,'event '+(event.code==='STOP'?'stop':''));el.append(node('time',new Date(event.at).toLocaleTimeString('ko-KR')),node('b',event.code),node('span',event.message));return el;}));
  updateButtons();
}
async function refresh(){
  try{
    worldState=await api('/api/state');online=true;$('connection').textContent='서버 연결됨';
    $('connection').parentElement.dataset.state='online';
    $('backend-status').textContent=worldState.geometry_backend==='native'?'C++ 검사 엔진':worldState.geometry_backend==='python'?'Python 검사 엔진':'검사 엔진 확인 중';
    $('system-prompt').textContent=worldState.contract.system_prompt;$('scene-task').textContent=worldState.contract.title;
    $('contract').value=worldState.contract.id;
    $('sensor-status').textContent=worldState.world.sensor_online?'센서 정상':'센서 수신 중단';
    $('sensor-status').dataset.state=worldState.world.sensor_online?'online':'offline';
    $('sensor').textContent=worldState.world.sensor_online?'센서 끊기':'센서 복구';
    $('guard-note').textContent=worldState.input_guard?.enabled?`입력 필터: ${worldState.input_guard.provider} / ${worldState.input_guard.model}. 합성 계획에서도 평가 입력이 이 공급자로 전송되며 비용이 발생할 수 있습니다.`:'모델 입력 필터 미사용 · 합성 계획은 외부 API를 호출하지 않습니다.';
    if(worldState.fault)notice(worldState.fault);
    if(selectedRun)renderRun(await api(`/api/runs/${selectedRun}`));
    activeRunData=worldState.active_run_id?(worldState.active_run_id===lastRunData?.id?lastRunData:await api(`/api/runs/${worldState.active_run_id}`)):null;
    $('execution-status').textContent=worldState.fault?'실행 중단 · 서버 오류':worldState.active_run_id?'실행 중':'실행 없음';
    $('execution-status').dataset.state=worldState.fault?'fault':worldState.active_run_id?'running':'idle';
    drawScene(worldState.world);updateButtons();
  }catch(error){online=false;$('connection').textContent='연결 끊김';$('connection').parentElement.dataset.state='offline';updateButtons();notice('서버 연결이 끊겼습니다. 화면 상태를 실행 확인으로 사용하지 마세요.');}
}
function setMetric(id,value,unit){$(id).replaceChildren(document.createTextNode(String(value)),node('small',unit));}
async function history(){
  const rows=await api('/api/history');setMetric('metric-count',rows.length,'건');setMetric('metric-complete',rows.filter(r=>r.status==='COMPLETED').length,'건');
  const samples=rows.filter(r=>r.mode===$('mode').value&&r.provider===$('provider').value);
  const times=samples.map(r=>r.preparation_ms).sort((a,b)=>a-b);
  $('metric-scope').textContent=`${$('provider').value==='replay'?'합성 재생':'OpenAI'} · ${$('mode').value} · ${samples.length}개 표본`;
  setMetric('metric-latest',samples.length?samples[0].preparation_ms.toFixed(1):'—','ms');setMetric('metric-p95',times.length?times[Math.ceil(times.length*.95)-1].toFixed(1):'—','ms');
  if(!rows.length){const tr=node('tr'),td=node('td','아직 기록이 없습니다. 첫 계획을 검증해 보세요.','empty');td.colSpan=6;tr.append(td);$('history-body').replaceChildren(tr);return;}
  $('history-body').replaceChildren(...rows.map(r=>{const tr=node('tr');tr.append(node('td',new Date(r.created_at).toLocaleTimeString('ko-KR')),node('td',r.mode),node('td',r.provider==='replay'?'합성 재생':'OpenAI'));const state=node('td');state.append(node('span',statuses[r.status]||r.status,'state-tag '+r.status));const last=node('td'),button=node('button','보기');button.addEventListener('click',()=>action(async()=>{selectedRun=r.id;renderRun(await api(`/api/runs/${r.id}`));}));last.append(button);tr.append(state,node('td',r.preparation_ms.toFixed(2)+' ms'),last);return tr;}));
}
$('mode').addEventListener('change',inputMode);$('provider').addEventListener('change',providerMode);
$('evaluate').addEventListener('click',()=>action(async()=>{busy=true;updateButtons();const run=await api('/api/evaluate','POST',{mode:$('mode').value,text:$('mode').value==='IMAGE'?'':$('text').value,provider:$('provider').value,scenario:$('provider').value==='replay'?$('scenario').value:'normal'});selectedRun=run.id;renderRun(run);if(run.evidence.image)$('camera').src=run.evidence.image;}));
$('execute').addEventListener('click',()=>action(async()=>{if(!selectedRun)return;busy=true;updateButtons();renderRun(await api(`/api/runs/${selectedRun}/execute`,'POST'));}));
$('stop').addEventListener('click',()=>action(()=>api('/api/stop','POST')));
$('obstacle').addEventListener('click',()=>action(()=>api('/api/disturb','POST',{kind:'obstacle'})));
$('sensor').addEventListener('click',()=>action(()=>api('/api/disturb','POST',{kind:worldState?.world.sensor_online?'sensor_loss':'sensor_restore'})));
async function reset(){await api('/api/reset','POST',{contract_id:$('contract').value});selectedRun=null;renderRun(null);inputMode();}
$('reset').addEventListener('click',()=>action(reset));$('contract').addEventListener('change',()=>action(reset));
renderRun(null);inputMode();providerMode();
async function poll(){await refresh();setTimeout(poll,300);}
async function pollHistory(){try{await history();}catch{}setTimeout(pollHistory,2000);}
poll();pollHistory();
