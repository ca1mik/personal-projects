let historyCursor=null,historyScope={},previewTimer=null,previewSequence=0,editorSnapshot='';
const canWrite=area=>window.sessionContext?.user?.role==='admin'||window.sessionContext?.user?.role===area;
const role=()=>window.sessionContext?.user?.role;
document.body.insertAdjacentHTML('beforeend',`<dialog id="history-dialog"><div class="dialog-head"><div><div class="eyebrow">ПРОЗРАЧНОСТЬ ИЗМЕНЕНИЙ</div><h2 id="history-title">История действий</h2></div><button class="icon-button" id="history-close" aria-label="Закрыть историю">×</button></div><div id="history-items"></div><button id="history-more" class="text-button" hidden>Показать более ранние</button></dialog><dialog id="users-dialog"><div class="dialog-head"><div><div class="eyebrow">АДМИНИСТРАТОР</div><h2>Пользователи и доступ</h2></div><button class="icon-button" id="users-close" aria-label="Закрыть пользователей">×</button></div><p class="table-note">Директор видит все данные без редактирования. Сотрудник читает и меняет только свой участок. Администратор управляет всеми участками и пользователями.</p><div id="users-list"></div><form id="user-form"><h3 id="user-form-title">Новый пользователь</h3><div class="form-grid"><label>Логин<input name="username" required pattern="[A-Za-z0-9_.-]{3,40}" autocomplete="off"></label><label>Имя<input name="name" required maxlength="100"></label><label>Роль<select name="role">${Object.entries(window.roleNames).map(([r,n])=>`<option value="${r}">${n}</option>`).join('')}</select></label><label>Пароль<input name="password" type="password" minlength="10" autocomplete="new-password"><small>При изменении пустое поле сохраняет прежний пароль.</small></label></div><label class="check"><input type="checkbox" name="active" checked> Доступ включён</label><p id="user-error" class="error" role="alert"></p><div class="dialog-actions"><button type="button" id="user-reset">Очистить форму</button><button class="primary" type="submit">Сохранить пользователя</button></div></form></dialog>`);
const historyButton=document.createElement('button');historyButton.id='history-button';historyButton.innerHTML='<span>↺</span>История действий';historyButton.onclick=()=>openHistory();$('nav').append(historyButton);
const adminButton=document.createElement('button');adminButton.id='users-button';adminButton.innerHTML='<span>⚙</span>Пользователи и доступ';adminButton.onclick=()=>openUsers();$('nav').append(adminButton);
$('.header-right').insertAdjacentHTML('beforeend','<div class="account-line"><span id="account-name"></span><button class="text-button" id="logout-button">Выйти</button></div>');
$('#logout-button').onclick=async()=>{try{await api('/api/logout',{method:'POST'})}finally{window.authRequired()}};
$('#history-close').onclick=()=>$('#history-dialog').close();$('#users-close').onclick=()=>$('#users-dialog').close();
function advice(row){
 let d=row.values,items=[];
 for(let issue of row.issues){
  if(issue.includes('Подозрительный')){let suffix=row.area==='docs'?'docs':'qty';items.push(`Факт ${d['fact_'+suffix]} при плане ${d['plan_'+suffix]}. Сверьте первичный документ и исправьте факт. До проверки связанный итог неизвестен.`)}
  else if(issue.includes('Повтор'))items.push('Номер повторяется. Сверьте обе строки: исправьте номер либо удалите подтверждённый дубль. Обе записи пока исключены из итогов.');
  else if(issue.includes('Не заполнено'))items.push(issue+'. Внесите подтверждённое значение; ноль ставьте только при реальном отсутствии результата.');
  else if(issue.includes('неотрицательное'))items.push(issue+'. Сверьте количество: отрицательные и дробные значения в этом учёте недопустимы.');
  else items.push(issue+'. Исправьте дату, чтобы запись попала в нужный период.');
 }
 return [...new Set(items)];
}
function enhanceRender(){
 const u=window.sessionContext?.user;if(!u)return;
 $('#account-name').textContent=u.name+' · '+window.roleNames[u.role];$('#users-button').hidden=u.role!=='admin';
 document.querySelectorAll('[data-view]').forEach(b=>b.hidden=b.dataset.view==='dashboard'?!['admin','director'].includes(u.role):!state.areas[b.dataset.view]);
 $('#add-record').hidden=!canWrite(view);$('#show-all').textContent='Все первичные записи ↗';
 let issues=[...report.records,...report.undated].filter(r=>!r.valid);
 if(!$('#insights'))$('#quality-banner').insertAdjacentHTML('afterend','<section id="insights" class="insights"></section>');
 const deficits=report.batches.filter(b=>!b.issues.length&&b.gap>0),blocked=report.batches.filter(b=>b.issues.length);
 $('#insights').innerHTML=`<div class="insight"><span class="eyebrow">ПРИОРИТЕТ ПРОВЕРКИ</span><h3>${issues.length?issues.length+' строк требуют проверки':'Данные проверены'}</h3><p>${issues.length?'Начните с дублей, пропусков и необычного факта. Частичные суммы не дают общей картины выпуска.':'В первичных записях выбранного периода замечаний нет.'}</p><button id="insight-issues" class="text-button">${issues.length?'Открыть проблемы':'Посмотреть записи'} →</button></div><div class="insight"><span class="eyebrow">ОБЕСПЕЧЕННОСТЬ СВАРКИ</span><h3>Партий с дефицитом: ${deficits.length}</h3><p>${blocked.length?'Партий без достоверной оценки: '+blocked.length+'. Нужна проверка данных.':'У всех показанных партий есть достоверная сверка.'} Предложение: сначала проверить неизвестные остатки, затем обсудить подтверждённый дефицит.</p><button id="insight-batches" class="text-button">Открыть сверку →</button></div>`;
 $('#insights').hidden=!['admin','director'].includes(u.role);
 $('#insight-issues').onclick=()=>details(issues.length?issues:report.records,issues.length?'Проблемы и следующие действия':'Первичные записи');
 $('#insight-batches').onclick=()=>$('#batch-rows').closest('.panel').scrollIntoView({behavior:'smooth',block:'start'});
 $('#metrics').querySelectorAll('.metric').forEach((el,i)=>{el.tabIndex=0;el.setAttribute('role','button');const areas=['production','welding','docs'];el.onclick=()=>details(i===3?issues:[...report.records,...report.undated].filter(r=>r.area===areas[i]),i===3?'Качество данных':state.areas[areas[i]]);el.onkeydown=e=>{if(e.target===el&&['Enter',' '].includes(e.key)){e.preventDefault();el.click()}}});
 if(typeof enhanceMetricChanges==='function')enhanceMetricChanges();enhanceWork();if(typeof refreshWorkspace==='function')refreshWorkspace();
}
function enhanceWork(){
 if(!state.fields[view])return;
 if(typeof renderWorkerOverview==='function')renderWorkerOverview();
 $('#add-record').hidden=!canWrite(view);
 if(!$('#work-search')){
  $('#work-screen .actions').insertAdjacentHTML('afterbegin','<input id="work-search" class="search-input" placeholder="Поиск: партия, номер, сотрудник" aria-label="Поиск записей">');
  $('#work-search').oninput=filterWork;
 }
 $('#work-body').querySelectorAll('[data-edit]').forEach(b=>{if(!canWrite(view)){b.textContent='Посмотреть';b.onclick=()=>details([state.rows.find(r=>r.id===+b.dataset.edit)],'Запись участка')}});
 filterWork();
}
function filterWork(){const q=($('#work-search')?.value||'').toLocaleLowerCase('ru');$('#work-body').querySelectorAll('tr').forEach(tr=>tr.hidden=q&&!tr.textContent.toLocaleLowerCase('ru').includes(q))}
function enhanceDetails(rows){
 $('#detail-content').querySelectorAll('.detail-card').forEach((card,i)=>{
  let row=rows[i];if(!row)return;
  const text=card.querySelector('p');text.innerHTML=advice(row).map(x=>esc(x)).join('<br>')||'Замечаний нет';
  if(!canWrite(row.area))card.querySelector('[data-detail-edit]')?.remove();
  let b=document.createElement('button');b.className='text-button';b.textContent='История этой записи ↗';b.onclick=()=>{$('#detail').close();openHistory({record:row.id,area:row.area},row.values.record_id)};card.append(b);if(typeof addTaskAction==='function')addTaskAction(card,row);
 });
 if(typeof addBatchTaskAction==='function')addBatchTaskAction(rows);
}
function enhanceEditor(row){
 clearTimeout(previewTimer);previewSequence++;editorSnapshot=JSON.stringify(Object.fromEntries(new FormData($('#edit-form'))));
 if(!$('#edit-preview'))$('#edit-error').insertAdjacentHTML('beforebegin','<div id="edit-preview" class="preview-box" aria-live="polite"></div>');
 $('#edit-preview').innerHTML='<p>Проверяю данные и влияние на расчёты…</p>';
 $('#delete-record').textContent='Удалить с восстановлением';
 $('#edit-form').oninput=()=>{clearTimeout(previewTimer);previewTimer=setTimeout(()=>previewEdit(row),250)};
 previewEdit(row);
}
async function previewEdit(row){
 const seq=++previewSequence;let area=$('#editor').dataset.area;
 try{let result=await api('/api/preview/'+area+'?'+dates(),{method:'POST',body:JSON.stringify({id:row?.id,values:Object.fromEntries(new FormData($('#edit-form')))})});if(seq!==previewSequence||!$('#editor').open)return;
  let lines=result.issues.length?result.issues.map(x=>`<p class="error">${esc(x)}</p>`).join(''):'<p class="preview-ok">Проверка пройдена. Запись войдёт в достоверные расчёты своего периода.</p>';
  const changed=Object.keys(state.areas).filter(a=>JSON.stringify(result.before[a])!==JSON.stringify(result.after[a]));
  lines+='<strong>После сохранения</strong>'+(changed.length?changed.map(a=>{let before=result.before[a],after=result.after[a];return `<p>${esc(state.areas[a])}: ${num(before.known_fact??before.known_need)} → ${num(after.known_fact??after.known_need)} по проверенным строкам${after.complete?'':' · итог неполный'}</p>`}).join(''):'<p>Показатели выбранного периода не изменятся.</p>');
  result.batches.forEach(b=>lines+=`<p>${esc(b.batch_id)}: ${b.gap==null?'дефицит пока неизвестен':b.gap>0?'дефицит '+num(b.gap):b.gap<0?'избыток '+num(-b.gap):'потребность обеспечена'}</p>`);
  $('#edit-preview').innerHTML=lines;
 }catch(e){if(seq===previewSequence)$('#edit-preview').textContent=e.message}
}
function hasDraft(){return $('#editor').open&&editorSnapshot!==JSON.stringify(Object.fromEntries(new FormData($('#edit-form'))))}
$('#close-edit').onclick=()=>{if(!hasDraft()||confirm('Закрыть без сохранения изменений?'))$('#editor').close()};
$('#editor').addEventListener('cancel',e=>{if(hasDraft()&&!confirm('Закрыть без сохранения изменений?'))e.preventDefault()});
async function openHistory(scope={},label=''){
 historyScope=scope;historyCursor=null;$('#history-title').textContent=label?'История · '+label:'История действий';$('#history-items').innerHTML='';if(!$('#history-dialog').open)$('#history-dialog').showModal();await historyPage();
}
async function historyPage(){
 try{let qs=new URLSearchParams(historyScope);if(historyCursor)qs.set('before',historyCursor);let result=await api('/api/history?'+qs),seen=new Set();
  $('#history-items').insertAdjacentHTML('beforeend',result.items.map(x=>{
   const actions={import:'Первоначальная загрузка',edit:'Изменение',create:'Новая запись',delete:'Удаление',restore:'Восстановление',login:'Вход в систему',logout:'Выход из системы',user_create:'Создание пользователя',user_update:'Изменение доступа',task_create:'Создание задачи',task_update:'Изменение задачи',task_comment:'Комментарий к задаче'};
   const canRestore=x.deleted&&canWrite(x.area)&&!seen.has(x.record);seen.add(x.record);
   return `<article class="history-entry"><div class="section-head"><strong>${esc(actions[x.action]||x.action)}${x.record?' · '+esc(x.label):''}</strong><time>${new Date(x.at).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'})} МСК</time></div><p>${esc(x.actor)}${x.area?' · '+esc(window.roleNames[x.area]):''}</p><div>${x.changes.map(v=>`<div class="change"><span>${esc(labels[v.field]||({role:'Роль',active:'Доступ',username:'Логин',name:'Имя',password_changed:'Пароль изменён'}[v.field])||v.field)}</span><del>${esc(v.before??'—')}</del><span>→</span><strong>${esc(v.after??'—')}</strong></div>`).join('')}</div>${canRestore?`<button class="text-button" data-restore="${x.record}" data-restore-area="${x.area}" data-revision="${x.revision}">Восстановить запись →</button>`:''}</article>`;
  }).join('')||'<div class="empty-state">Действий пока нет.</div>');
  historyCursor=result.next_before;$('#history-more').hidden=!historyCursor;
  document.querySelectorAll('[data-restore]').forEach(b=>b.onclick=async()=>{try{await api(`/api/records/${b.dataset.restoreArea}/${b.dataset.restore}/restore`,{method:'POST',body:JSON.stringify({revision:+b.dataset.revision})});await load();await openHistory(historyScope);toast('Запись восстановлена. Итоги пересчитаны.')}catch(e){toast(e.message)}});
 }catch(e){toast(e.message)}
}
$('#history-more').onclick=historyPage;
let userEditing=null,userList=[];
async function openUsers(){try{let data=await api('/api/users');userList=data.users;$('#users-list').innerHTML='<div class="table-wrap"><table><thead><tr><th>Пользователь</th><th>Роль</th><th>Доступ</th><th></th></tr></thead><tbody>'+data.users.map(u=>`<tr><td><strong>${esc(u.name)}</strong><br><small>${esc(u.username)}</small></td><td>${esc(window.roleNames[u.role])}</td><td><span class="badge ${u.active?'':'warn'}">${u.active?'Включён':'Отключён'}</span></td><td><button class="row-action" data-user-edit="${u.id}">Настроить</button></td></tr>`).join('')+'</tbody></table></div>';document.querySelectorAll('[data-user-edit]').forEach(b=>b.onclick=()=>userForm(userList.find(u=>u.id===+b.dataset.userEdit)));if(!$('#users-dialog').open)$('#users-dialog').showModal()}catch(e){toast(e.message)}}
function userForm(user=null){userEditing=user;let f=$('#user-form');f.elements.username.value=user?.username||'';f.elements.username.disabled=!!user;f.elements.name.value=user?.name||'';f.elements.role.value=user?.role||'production';f.elements.active.checked=user?!!user.active:true;f.elements.password.value='';f.elements.password.required=!user;$('#user-error').textContent='';$('#user-form-title').textContent=user?'Доступ · '+user.username:'Новый пользователь';if(typeof captureUserDraft==='function')captureUserDraft()}
$('#user-reset').onclick=()=>userForm();
$('#user-form').onsubmit=async e=>{e.preventDefault();let f=e.target,d=Object.fromEntries(new FormData(f));d.active=f.elements.active.checked;let btn=e.submitter;btn.disabled=true;try{await api('/api/users'+(userEditing?'/'+userEditing.id:''),{method:userEditing?'PUT':'POST',body:JSON.stringify(d)});userForm();await openUsers();toast('Доступ сохранён')}catch(e){$('#user-error').textContent=e.message}finally{btn.disabled=false}};
// Hooks are installed once; refresh any data that arrived before this script loaded.
if(typeof state!=='undefined'&&state?.initialized&&typeof report!=='undefined')enhanceRender();

userForm();
