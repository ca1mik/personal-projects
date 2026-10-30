const taskStatuses={todo:'К выполнению',in_progress:'В работе',review:'На проверке',done:'Завершена'};
let taskDraft=null,taskSource=null,taskSnapshot='',taskListSequence=0,taskUser=null;
const managesTasks=()=>['admin','director'].includes(role());
$('#work-screen').insertAdjacentHTML('beforebegin',`<section id="tasks-page" data-workspace-page hidden><div class="section-head"><div><div class="eyebrow">ОТ ПРОБЛЕМЫ К ДЕЙСТВИЮ</div><h2>Задачи и проверка результата</h2><p>Поручения сохраняются отдельно от показателей. Исправление данных не закрывает задачу автоматически.</p></div><button id="task-from-issue" class="primary">Выбрать проблему →</button></div><div class="panel task-filters"><label>Участок<select id="task-area-filter"></select></label><label>Статус<select id="task-status-filter"><option value="">Все статусы</option>${Object.entries(taskStatuses).map(([s,n])=>`<option value="${s}">${n}</option>`).join('')}</select></label><label class="check"><input type="checkbox" id="task-mine"> Только назначенные мне</label><span class="table-note">Период панели не ограничивает поручения.</span></div><div id="task-board" class="task-board"></div></section>`);
document.body.insertAdjacentHTML('beforeend',`<dialog id="task-dialog"><form id="task-form"><div class="dialog-head"><div><div class="eyebrow" id="task-source-label"></div><h2 id="task-form-title">Новая задача</h2></div><button type="button" id="task-close" class="icon-button" aria-label="Закрыть задачу">×</button></div><div id="task-source-warning"></div><div class="form-grid"><label class="wide-field">Название<input name="title" maxlength="160" required></label><label>Участок<select name="area"></select></label><label>Ответственный<select name="assignee" required></select></label><label>Срок<input name="due" type="date" required></label><label>Статус<select name="status"></select></label><label class="wide-field">Что нужно сделать<textarea name="description" maxlength="2000" rows="3"></textarea></label><label class="wide-field">Комментарий или результат<textarea name="comment" maxlength="1000" rows="3" placeholder="Что проверили, что исправили, что осталось сделать"></textarea></label></div><div class="task-dialog-links"><button type="button" id="task-open-source" class="text-button">Открыть источник ↗</button><button type="button" id="task-comment" class="text-button">Добавить комментарий</button></div><p id="task-form-error" class="error" role="alert"></p><div class="dialog-actions"><span class="table-note">Закрывает задачу руководитель после проверки.</span><button id="task-save" type="submit" class="primary">Сохранить задачу</button></div><div id="task-events" class="task-events"></div></form></dialog><dialog id="changes-dialog"><div class="dialog-head"><div><div class="eyebrow">ПРИЧИНЫ ИЗМЕНЕНИЯ ПОКАЗАТЕЛЕЙ</div><h2>Почему менялись цифры</h2></div><button id="changes-close" class="icon-button" aria-label="Закрыть объяснение">×</button></div><p id="changes-context" class="table-note"></p><div id="changes-items"></div></dialog>`);
const taskNav=document.createElement('button');taskNav.dataset.page='tasks';taskNav.innerHTML='<span>☑</span>Задачи и проблемы';taskNav.onclick=()=>switchView('tasks');$('nav').append(taskNav);
function showTaskPage(){
 $('#dashboard').hidden=true;$('#work-screen').hidden=true;
 document.querySelectorAll('[data-workspace-page]').forEach(el=>el.hidden=el.id!=='tasks-page');
 document.querySelectorAll('[data-view]').forEach(el=>el.classList.remove('active'));document.querySelectorAll('[data-page]').forEach(el=>el.classList.toggle('active',el.dataset.page==='tasks'));
 $('#title').textContent='Задачи по рабочим данным';$('#subtitle').textContent='Ответственный, срок, обсуждение и проверка результата — рядом с причиной.';$('#crumb').textContent='ЗАДАЧИ';refreshTasks();
}
function refreshFlow(){if(view==='tasks')refreshTasks()}
async function refreshTasks(){
 if(!state)return;
 const current=$('#task-area-filter').value;$('#task-area-filter').innerHTML='<option value="">Все доступные</option>'+Object.entries(state.areas).map(([a,n])=>`<option value="${a}" ${a===current?'selected':''}>${esc(n)}</option>`).join('');
 if(taskUser!==window.sessionContext.user.id){taskUser=window.sessionContext.user.id;$('#task-mine').checked=!managesTasks()}
 $('#task-from-issue').hidden=!managesTasks();const seq=++taskListSequence;
 try{let q=new URLSearchParams({area:$('#task-area-filter').value,status:$('#task-status-filter').value,mine:String($('#task-mine').checked)});let result=await api('/api/tasks?'+q);if(seq!==taskListSequence)return;
  $('#task-board').innerHTML=Object.entries(taskStatuses).map(([status,label])=>{let items=result.items.filter(t=>t.status===status);return `<section class="task-column"><h3>${label}<span>${items.length}</span></h3>${items.map(t=>`<button class="task-card" data-task-open="${t.id}"><span class="badge ${t.overdue?'warn':''}">${esc(state.areas[t.area])} · №${t.id}</span><strong>${esc(t.title)}</strong><span>${esc(t.source.label)}</span><small>${esc(t.assignee_name)}${t.assignee_active?'':' (доступ отключён)'} · до ${esc(t.due)}</small>${t.overdue?'<span class="task-overdue">Срок прошёл</span>':''}${t.source.issues.length?'<span class="task-source-issue">В исходных данных остаются замечания</span>':''}</button>`).join('')||'<p class="empty-task">Пока нет задач</p>'}</section>`}).join('');
  document.querySelectorAll('[data-task-open]').forEach(b=>b.onclick=()=>openTask(+b.dataset.taskOpen));
 }catch(e){toast(e.message)}
}
for(const id of ['task-area-filter','task-status-filter','task-mine'])$('#'+id).onchange=refreshTasks;
$('#task-from-issue').onclick=()=>{let issues=[...report.records,...report.undated].filter(r=>!r.valid);details(issues.length?issues:report.records,'Выберите запись для поручения')};
function addTaskAction(card,row){if(!managesTasks())return;let b=document.createElement('button');b.className='text-button';b.textContent='Создать задачу →';b.onclick=()=>{$('#detail').close();newTask({area:row.area,source_type:'record',source_key:String(row.id),label:row.values.record_id,title:'Проверить '+row.values.record_id,description:advice(row).join('\n')||'Проверить запись и зафиксировать результат.'})};card.append(b)}
function addBatchTaskAction(rows){
 if(!managesTasks()||!rows.length)return;
 let name=$('#detail-title').textContent;const batch=rows.find(r=>r.values.batch_id===name)?.values.batch_id;if(!batch)return;
 let b=document.createElement('button');b.className='primary';b.textContent='Создать задачу по партии →';b.onclick=()=>{$('#detail').close();newTask({area:rows.find(r=>r.area==='production')?.area||rows[0].area,source_type:'batch',source_key:batch,label:'Партия '+batch,title:'Проверить обеспеченность '+batch,description:'Проверить данные и согласовать действия по партии. Период панели: '+report.start+' — '+report.end+'.'})};$('#detail-content').append(b)
}
async function eligible(area,selected=null){
 let result=await api('/api/tasks/assignees?area='+area);
 let opts=result.users.map(u=>`<option value="${u.id}" ${u.id===selected?'selected':''}>${esc(u.name)} (${esc(u.username)})</option>`);
 if(selected&&!result.users.some(u=>u.id===selected))opts.unshift(`<option selected value="${selected}">Текущий ответственный недоступен — выберите другого</option>`);
 $('#task-form').elements.assignee.innerHTML=opts.join('');
 if(!selected){let worker=result.users.find(u=>u.username===area);if(worker)$('#task-form').elements.assignee.value=worker.id}
}
async function newTask(source){
 taskDraft=null;taskSource=source;const f=$('#task-form');f.reset();f.elements.comment.closest('label').hidden=true;$('#task-events').innerHTML='';$('#task-form-error').textContent='';$('#task-source-warning').textContent='';$('#task-source-label').textContent=source.label;$('#task-form-title').textContent='Новая задача';
 f.elements.title.value=source.title;f.elements.description.value=source.description;f.elements.area.innerHTML=Object.entries(state.areas).filter(([a])=>source.source_type==='batch'?a!=='docs':a===source.area).map(([a,n])=>`<option value="${a}" ${a===source.area?'selected':''}>${esc(n)}</option>`).join('');
 for(const name of ['title','description','area','assignee','due','status'])f.elements[name].disabled=false;
 f.elements.status.innerHTML='<option value="todo">К выполнению</option>';f.elements.status.disabled=true;f.elements.due.value=new Date(Date.now()+2*86400000).toLocaleDateString('sv-SE',{timeZone:'Europe/Moscow'});
 $('#task-comment').hidden=true;$('#task-save').hidden=false;
 try{await eligible(source.area);taskSnapshot=taskFormValue();$('#task-dialog').showModal()}catch(e){toast(e.message)}
}
$('#task-form').elements.area.onchange=async e=>{try{await eligible(e.target.value)}catch(e){toast(e.message)}};
async function openTask(id){
 try{const result=await api('/api/tasks/'+id);taskDraft=result.task;taskSource={area:taskDraft.area,source_type:taskDraft.source_type,source_key:taskDraft.source_key,label:taskDraft.source.label};const f=$('#task-form');f.reset();f.elements.comment.closest('label').hidden=false;$('#task-form-error').textContent='';$('#task-form-title').textContent='Задача №'+id;$('#task-source-label').textContent=taskDraft.source.label;
  f.elements.title.value=taskDraft.title;f.elements.description.value=taskDraft.description;f.elements.due.value=taskDraft.due;f.elements.area.innerHTML=`<option value="${taskDraft.area}">${esc(state.areas[taskDraft.area])}</option>`;
  if(result.can_manage)await eligible(taskDraft.area,taskDraft.assignee);else f.elements.assignee.innerHTML=`<option value="${taskDraft.assignee}">${esc(taskDraft.assignee_name)}</option>`;
  let allowed=result.can_manage?Object.keys(taskStatuses):[taskDraft.status,...({todo:['in_progress'],in_progress:['review'],review:['in_progress'],done:[]}[taskDraft.status])];
  f.elements.status.innerHTML=[...new Set(allowed)].map(s=>`<option value="${s}" ${s===taskDraft.status?'selected':''}>${taskStatuses[s]}</option>`).join('');
  for(const name of ['title','description','assignee','due'])f.elements[name].disabled=!result.can_manage;
  f.elements.area.disabled=true;f.elements.status.disabled=!result.can_progress;$('#task-save').hidden=!result.can_progress;$('#task-comment').hidden=false;
  $('#task-source-warning').innerHTML=taskDraft.source.issues.length?`<div class="banner"><strong>Источник требует внимания</strong><span>${taskDraft.source.issues.map(esc).join('; ')}. Статус поручения сам по себе эти замечания не устраняет.</span></div>`:'';
  $('#task-events').innerHTML='<h3>Обсуждение и действия</h3>'+result.events.map(e=>`<article class="task-event"><strong>${esc(e.actor)}</strong> <time>${new Date(e.at).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'})} МСК</time><p>${e.kind==='create'?'Создал задачу':e.kind==='comment'?'Комментарий':e.before?.status!==e.after?.status?esc(taskStatuses[e.before?.status]||'—')+' → '+esc(taskStatuses[e.after?.status]||'—'):'Обновил параметры задачи'}</p>${e.comment?'<blockquote>'+esc(e.comment)+'</blockquote>':''}</article>`).join('');
  taskSnapshot=taskFormValue();if(!$('#task-dialog').open)$('#task-dialog').showModal();
 }catch(e){toast(e.message)}
}
function taskFormValue(){return JSON.stringify(Object.fromEntries(new FormData($('#task-form'))))}
function closeTask(){if(taskSnapshot!==taskFormValue()&&!confirm('Закрыть без сохранения задачи или комментария?'))return;$('#task-dialog').close()}
$('#task-close').onclick=closeTask;$('#task-dialog').addEventListener('cancel',e=>{e.preventDefault();closeTask()});
$('#task-form').onsubmit=async e=>{e.preventDefault();let f=e.target,btn=e.submitter;btn.disabled=true;
 try{let d={comment:f.elements.comment.value,status:f.elements.status.value};
  if(!taskDraft){d={area:f.elements.area.value,source_type:taskSource.source_type,source_key:taskSource.source_key,title:f.elements.title.value,description:f.elements.description.value,assignee:+f.elements.assignee.value,due:f.elements.due.value};}
  else{d.revision=taskDraft.revision;if(managesTasks())Object.assign(d,{title:f.elements.title.value,description:f.elements.description.value,assignee:+f.elements.assignee.value,due:f.elements.due.value})}
  let r=await api('/api/tasks'+(taskDraft?'/'+taskDraft.id:''),{method:taskDraft?'PUT':'POST',body:JSON.stringify(d)});$('#task-dialog').close();await load();switchView('tasks');toast(taskDraft?'Задача обновлена':'Задача создана');
 }catch(e){$('#task-form-error').textContent=e.message}finally{btn.disabled=false}
};
$('#task-comment').onclick=async()=>{if(!taskDraft)return;const current=Object.fromEntries(new FormData($('#task-form'))),original=JSON.parse(taskSnapshot);delete current.comment;delete original.comment;if(JSON.stringify(current)!==JSON.stringify(original)){$('#task-form-error').textContent='Сначала сохраните изменения параметров задачи вместе с комментарием.';return}try{await api('/api/tasks/'+taskDraft.id+'/comments',{method:'POST',body:JSON.stringify({comment:$('#task-form').elements.comment.value})});await openTask(taskDraft.id);toast('Комментарий сохранён')}catch(e){$('#task-form-error').textContent=e.message}};
$('#task-open-source').onclick=()=>{
 if(taskSource.source_type==='record'){let r=state.rows.find(r=>r.id===+taskSource.source_key);if(!r){toast('Запись удалена или недоступна. Смотрите её историю.');return}if(taskSnapshot!==taskFormValue()&&!confirm('Открыть источник без сохранения правок задачи?'))return;$('#task-dialog').close();details([r],r.values.record_id)}
 else{if(taskSnapshot!==taskFormValue()&&!confirm('Открыть источник без сохранения правок задачи?'))return;let rows=state.rows.filter(r=>r.area===taskSource.area&&r.values.batch_id===taskSource.source_key);$('#task-dialog').close();details(rows,taskSource.source_key)}
};
function enhanceMetricChanges(){
 const groups=[...$('#metrics').querySelectorAll('.metric'),...document.querySelectorAll('#worker-overview .metric')];
 groups.forEach((el,i)=>{if(el.querySelector('.metric-explain'))return;let isWorker=el.closest('#worker-overview');let area=isWorker?view:['production','welding','docs','all'][i];if(area!=='all'&&!state.areas[area])return;let b=document.createElement('button');b.className='metric-explain';b.textContent='Почему менялись цифры?';b.onclick=e=>{e.stopPropagation();openChanges(area)};el.append(b)})
}
async function openChanges(area='all'){
 $('#changes-context').textContent=report.start+' — '+report.end;$('#changes-items').innerHTML='<p>Пересчитываю влияние записанных правок…</p>';$('#changes-dialog').showModal();
 try{let result=await api('/api/changes?'+dates()+'&area='+area);const value=(key,v)=>v==null?'не определено':key==='ratio'?num(v*100)+'%':num(v);
  $('#changes-context').textContent=report.start+' — '+report.end+'. '+result.note;
  $('#changes-items').innerHTML=result.items.map(e=>`<article class="change-explanation"><div class="section-head"><h3>${esc(e.record_id)} · ${esc(state.areas[e.area])}</h3><time>${new Date(e.at).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'})}</time></div><p>${esc(e.actor)} · ${e.fields.map(f=>esc(labels[f.field]||f.field)+': '+esc(f.before??'пусто')+' → '+esc(f.after??'пусто')).join('; ')}</p>${e.metrics.map(m=>`<div class="change"><span>${esc(state.areas[m.area])} · ${esc(m.label)}</span><del>${value(m.metric,m.before)}</del><span>→</span><strong>${value(m.metric,m.after)}</strong></div>`).join('')}${e.batches.map(b=>`<p class="batch-change">${esc(b.batch)}: дефицит / избыток ${b.before==null?'неизвестен':num(b.before)} → ${b.after==null?'неизвестен':num(b.after)}</p>`).join('')}</article>`).join('')||'<div class="empty-state">Среди последних записанных правок нет изменений числовых показателей этого периода. Посмотреть все действия можно в истории.</div>';
 }catch(e){$('#changes-items').textContent=e.message}
}
$('#changes-close').onclick=()=>$('#changes-dialog').close();
for(const d of [$('#task-dialog'),$('#changes-dialog')]){let down=false;d.addEventListener('pointerdown',e=>down=e.target===d&&outside(d,e));d.addEventListener('click',e=>{if(down&&e.target===d&&outside(d,e)){if(d.id==='task-dialog')closeTask();else d.close()}down=false})}
if(typeof state!=='undefined'&&state?.initialized)enhanceMetricChanges();
