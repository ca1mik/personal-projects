const $=s=>document.querySelector(s),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names={passed:'Доставлена',failed:'Сбой обнаружен',error:'Проверка не завершена',running:'Проверяю…'};
let state,selected=null,poll=null,working=false;
const time=x=>new Date(x).toLocaleString('ru-RU',{timeZone:'Europe/Moscow',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'})+' МСК';
async function api(path,body){let r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','x-guardian-token':state.token},body:JSON.stringify(body)});let d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Проверьте запрос');return d}
function render(){
 const busy=state.runs.some(r=>r.status==='running');if(!working)$('#mode').value=state.mode;$('#mode').disabled=busy||working;$('#run').disabled=busy||working;$('#run').textContent=busy?'Проверка выполняется…':'Проверить путь заявки ↗';
 if(selected===null&&state.runs.length)selected=state.runs[0].id;
 const r=state.runs.find(r=>r.id===selected)||state.runs[0];
 if(r){const d=r.result;$('#current').className='result panel '+r.status;$('#current').innerHTML=`<div class="result-head"><div><div class="eyebrow">ПРОВЕРКА №${r.id} / ${time(r.started)}</div><h2>${r.status==='running'?'Проверяю путь тестовой заявки…':r.status==='passed'?'Заявка дошла. Есть квитанция.':r.status==='failed'?'Поломка найдена. Есть доказательство.':'Успех не подтверждён'}</h2></div><span class="badge">${esc(state.modes[r.mode])}</span></div><p>${esc(d.message||(r.status==='running'?'Открываю браузер, отправляю форму и ожидаю запись в тестовой CRM.':'Нет результата'))}</p><div class="steps">${(d.steps||[]).map(s=>`<span class="step ${s.ok?'':'bad'}">${s.ok?'✓':'×'} ${esc(s.name)}</span>`).join('')}</div>${d.diagnostic?'<details><summary>Подробности для настройки проверки</summary><p class="trace">'+esc(d.diagnostic)+'</p></details>':''}<div class="result-head"><p class="trace">Метка: ${esc(r.marker)}${d.elapsed_ms?' · '+(d.elapsed_ms/1000).toFixed(1)+' с':''}</p>${d.screenshot?'<button id="show-shot">Снимок страницы ↗</button>':''}</div>`;if(d.screenshot)$('#show-shot').onclick=()=>{$('#shot').src='/artifacts/'+encodeURIComponent(d.screenshot);$('#shot-dialog').showModal()}}
 $('#counts').textContent=state.runs.length?'Последние '+state.runs.length:'';
 $('#history').innerHTML=state.runs.map(r=>`<button class="run-row" data-run="${r.id}"><span>№${r.id} · ${esc(state.modes[r.mode])}<small>${time(r.started)}</small></span><strong class="run-status ${r.status}">${names[r.status]}</strong></button>`).join('')||'<p>Проверок пока нет.</p>';
 document.querySelectorAll('[data-run]').forEach(b=>b.onclick=()=>{selected=+b.dataset.run;render()});
 $('#leads').innerHTML=state.leads.map(l=>`<article class="lead"><strong>✓ Тестовая заявка №${l.id}</strong><code>${esc(l.marker)}</code><small>${time(l.at)}</small></article>`).join('')||'<p class="small">Пока нет доставленных тестовых заявок.</p>';
 if(busy&&!poll)poll=setInterval(refresh,800);if(!busy&&poll){clearInterval(poll);poll=null}
}
async function refresh(){try{state=await api('/api/state');render()}catch(e){$('#action-error').hidden=false;$('#action-error').textContent=e.message;if(poll){clearInterval(poll);poll=null}}}
async function act(path,body){working=true;$('#action-error').hidden=true;render();try{return await api(path,body)}catch(e){$('#action-error').hidden=false;$('#action-error').textContent=e.message;return null}finally{working=false;await refresh()}}
$('#mode').onchange=async e=>{const mode=e.target.value;await act('/api/mode',{mode})};
$('#run').onclick=async()=>{const r=await act('/api/run',{});if(r){selected=r.id;render()}};
$('#close-shot').onclick=()=>$('#shot-dialog').close();$('#shot-dialog').onclick=e=>{if(e.target===$('#shot-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close()}};
refresh();
