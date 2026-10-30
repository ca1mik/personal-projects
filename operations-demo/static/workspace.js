// Visible workspaces: reports, role distribution and the employee's area dashboard.
let reportArea='',reportGroup='employee',pivotSequence=0,userDraft='';
$('#work-screen').insertAdjacentHTML('beforebegin',`<section id="reports-page" data-workspace-page hidden><div class="section-head"><div><div class="eyebrow">АНАЛИТИКА И ВЫГРУЗКА</div><h2>Отчёты и сводная таблица</h2><p>Выберите период сверху и разрез данных ниже. Из итога можно перейти к записям.</p></div><div class="actions"><button id="download-xlsx" class="primary">↓ Excel с диаграммами</button><button id="download-csv">↓ CSV</button></div></div><div class="panel"><div class="report-controls"><label>Участок<select id="report-area"></select></label><label>Группировать по<select id="report-group"></select></label><div class="report-context" id="report-context"></div></div><div id="pivot-chart"></div><div class="table-wrap"><table><thead id="pivot-head"></thead><tbody id="pivot-body"></tbody></table></div><p class="table-note report-note">Звёздочка и оранжевый цвет — частичная сумма проверенных строк, общий итог неизвестен. Сводка рассчитана по выбранной группировке. Ошибки не превращаются в достоверный ноль: частичные суммы помечены. В XLSX — обзор, сводка, партии, первичные записи и диаграммы; CSV сохраняется для обмена данными.</p></div></section><section id="roles-page" data-workspace-page hidden><div class="section-head"><div><div class="eyebrow">АДМИНИСТРИРОВАНИЕ</div><h2>Кто что может</h2><p>Роль определяет доступ к данным и действиям. Ограничения действуют и в API.</p></div><button class="primary" id="assign-role">Назначить роль пользователю →</button></div><div id="role-cards" class="role-cards"></div><div class="panel"><h2>Матрица разрешений</h2><div class="table-wrap"><table><thead><tr><th>Роль</th><th>Чтение данных</th><th>Редактирование</th><th>Отчёты</th><th>История / восстановление</th><th>Пользователи</th><th>Задачи</th></tr></thead><tbody id="roles-matrix"></tbody></table></div><p class="table-note report-note">Пять встроенных ролей. Администратор назначает их пользователям, меняет пароли и включает/отключает доступ в разделе «Пользователи и доступ».</p></div></section>`);
for(const [id,title,icon] of [['reports','Отчёты и сводная','▥'],['roles','Роли и права','⊞']]){
 const b=document.createElement('button');b.dataset.page=id;b.innerHTML=`<span>${icon}</span>${title}`;b.onclick=()=>switchView(id);$('nav').append(b);
}
$('#assign-role').onclick=()=>openUsers();
$('#export').textContent='▥ Отчёты и выгрузка';$('#export').onclick=()=>switchView('reports');
function showWorkspacePage(next){
 if(next==='tasks'&&typeof showTaskPage==='function'){showTaskPage();return true}if(!['reports','roles'].includes(next))return false;
 if(next==='roles'&&role()!=='admin'){view='dashboard';switchView('dashboard');return true}
 $('#dashboard').hidden=true;$('#work-screen').hidden=true;
 document.querySelectorAll('[data-workspace-page]').forEach(el=>el.hidden=el.id!==next+'-page');
 document.querySelectorAll('[data-view]').forEach(el=>el.classList.remove('active'));
 document.querySelectorAll('[data-page]').forEach(el=>el.classList.toggle('active',el.dataset.page===next));
 $('#crumb').textContent=next==='reports'?'ОТЧЁТЫ':'РОЛИ И ПРАВА';$('#title').textContent=next==='reports'?'Отчёты по работе участков':'Роли и права доступа';
 $('#subtitle').textContent=next==='reports'?'Сводная таблица, диаграммы и оформленный Excel по выбранному периоду.':'Кто видит данные, кто их изменяет и кто управляет пользователями.';
 refreshWorkspace();return true;
}
function refreshWorkspace(){
 if(typeof refreshGuide==='function')refreshGuide();
 document.querySelector('[data-page="roles"]').hidden=role()!=='admin';
 if(view==='reports')renderReportPage();
 if(view==='roles')renderRoles();if(typeof refreshFlow==='function')refreshFlow();
}
function renderWorkerOverview(){
 if(!state.fields[view])return;
 if(!$('#worker-overview'))$('#work-screen').insertAdjacentHTML('afterbegin','<div id="worker-overview"></div>');
 const t=report.totals[view];if(!t)return;
 const count=visibleRows().filter(r=>!r.valid).length;
 const isWeld=view==='welding';
 $('#worker-overview').innerHTML=`<div class="access-note"><strong>${role()==='admin'?'Рабочий экран · '+esc(state.areas[view]):'Мой участок · '+esc(state.areas[view])}</strong><span>${canWrite(view)?'Можно добавлять, исправлять и восстанавливать записи участка.':'Просмотр без редактирования.'} ${['admin','director'].includes(role())?'Доступ ко всем участкам.':'Другие участки недоступны.'}</span></div><div class="metrics worker-metrics">${metric(isWeld?'Потребность':'Факт за период',num(isWeld?t.known_need:t.known_fact),isWeld?'Введённая потребность участка':'По проверенным строкам',t.complete?'Данные проверены':'Частичная сумма',!t.complete)}${metric(isWeld?'Записей участка':'План за период',num(isWeld?t.rows:t.known_plan),'За выбранный период',isWeld?'Потребность учитывается отдельно':pct(t.ratio),!t.complete)}${metric('Требуют внимания',num(count),t.valid_rows+' из '+t.rows+' строк проверены',count?'Проверьте записи ниже':'Замечаний нет',!!count)}</div>${isWeld?'':`<div class="panel worker-chart"><div class="section-head"><h2>План и факт участка</h2><button class="text-button" id="worker-report">Открыть отчёт →</button></div><div id="worker-chart"></div></div>`}`;
 if(!isWeld){chart('worker-chart',view,'#388976');$('#worker-report').onclick=()=>{reportArea=view;switchView('reports')}}if(typeof enhanceMetricChanges==='function')enhanceMetricChanges();
}
function groupOptions(area){return area==='docs'?{employee:'Сотрудник',date:'Дата'}:area==='welding'?{batch_id:'Партия',date:'Дата'}:{employee:'Сотрудник',batch_id:'Партия',date:'Дата'}}
async function renderReportPage(){
 if(!state||!report)return;
 if(!state.areas[reportArea])reportArea=Object.keys(state.areas)[0];
 const options=groupOptions(reportArea);if(!options[reportGroup])reportGroup=Object.keys(options)[0];
 $('#report-area').innerHTML=Object.entries(state.areas).map(([a,n])=>`<option value="${a}" ${a===reportArea?'selected':''}>${esc(n)}</option>`).join('');
 $('#report-group').innerHTML=Object.entries(options).map(([a,n])=>`<option value="${a}" ${a===reportGroup?'selected':''}>${n}</option>`).join('');
 $('#report-context').textContent=report.start+' → '+report.end+' · '+state.areas[reportArea];
 const seq=++pivotSequence;
 try{const p=await api('/api/pivot?'+dates()+'&area='+reportArea+'&group_by='+reportGroup);if(seq!==pivotSequence)return;
  $('#pivot-head').innerHTML='<tr><th>'+options[reportGroup]+'</th><th class="number">План</th><th class="number">Факт / потребность</th><th class="number">Выполнение</th><th>Проверено</th><th></th></tr>';
  $('#pivot-body').innerHTML=p.rows.map((r,i)=>`<tr><td class="batch-name">${esc(r.group)}</td><td class="number">${num(r.plan)}</td><td class="number">${num(r.fact)}</td><td class="number">${r.ratio==null?'—':num(r.ratio*100)+'%'}</td><td><span class="badge ${r.complete?'':'warn'}">${r.valid_rows}/${r.rows}${r.complete?'':' · частично'}</span></td><td><button class="row-action" data-pivot-row="${i}">Записи ↗</button></td></tr>`).join('')||'<tr><td colspan="6" class="empty-state">В выбранном периоде нет записей</td></tr>';
  document.querySelectorAll('[data-pivot-row]').forEach(b=>b.onclick=()=>{let r=p.rows[+b.dataset.pivotRow];details([...report.records,...report.undated].filter(x=>r.record_ids.includes(x.id)),state.areas[reportArea]+' · '+r.group)});
  let max=Math.max(1,...p.rows.map(r=>r.fact));
  $('#pivot-chart').innerHTML=p.rows.length?'<div class="eyebrow">СУММА ПРОВЕРЕННЫХ СТРОК ПО ГРУППАМ</div>'+p.rows.map(r=>`<div class="pivot-bar ${r.complete?'':'partial'}"><span>${esc(r.group)}</span><div><i style="width:${r.fact/max*100}%"></i></div><strong>${num(r.fact)}${r.complete?'':'*'}</strong></div>`).join(''):'';
 }catch(e){toast(e.message)}
}
$('#report-area').onchange=e=>{reportArea=e.target.value;renderReportPage()};$('#report-group').onchange=e=>{reportGroup=e.target.value;renderReportPage()};
$('#download-xlsx').onclick=()=>{window.location.href='/api/export.xlsx?'+dates()+'&area='+reportArea+'&group_by='+reportGroup};
$('#download-csv').onclick=()=>{window.location.href='/api/export?'+dates()};
async function renderRoles(){
 try{let data=await api('/api/roles');const areaNames={production:'Заготовка',welding:'Сварка',docs:'Документация'};const names=arr=>arr.length===3?'Все участки':arr.map(a=>areaNames[a]).join(', ')||'Нет';
  $('#role-cards').innerHTML=data.roles.map(r=>`<article class="role-card"><h3>${esc(r.name)}</h3><p>Видит: ${esc(names(r.read_areas))}</p><p>Меняет: ${esc(names(r.edit_areas))}</p><span class="badge ${r.manage_users?'':'empty'}">${r.manage_users?'Управление доступом':r.id==='director'?'Приёмка задач':'Свой участок'}</span></article>`).join('');
  $('#roles-matrix').innerHTML=data.roles.map(r=>`<tr><td class="batch-name">${esc(r.name)}</td><td>${esc(names(r.read_areas))}</td><td>${esc(names(r.edit_areas))}</td><td>${esc(names(r.read_areas))}</td><td>${esc(names(r.read_areas))}<br><small>${r.restore?'Восстановление записей: '+names(r.edit_areas):'Без восстановления'}</small></td><td>${r.manage_users?'Создание, роли, пароли, отключение':'Нет'}</td><td>${r.assign_tasks?'Назначает и проверяет':'Выполняет назначенные своего участка'}</td></tr>`).join('');
 }catch(e){toast(e.message)}
}
// Light dismiss: both press and release must be outside the dialog's rectangle.
function outside(dialog,event){let r=dialog.getBoundingClientRect();return event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom}
function captureUserDraft(){userDraft=JSON.stringify(Object.fromEntries(new FormData($('#user-form'))))}
function closeDialog(dialog){
 if(dialog.id==='editor'){$('#close-edit').click();return}
 if(dialog.id==='users-dialog'&&userDraft!==JSON.stringify(Object.fromEntries(new FormData($('#user-form'))))&&!confirm('Закрыть без сохранения настроек пользователя?'))return;
 dialog.close();
}
document.querySelectorAll('dialog').forEach(dialog=>{
 let pressedOutside=false;
 dialog.addEventListener('pointerdown',e=>{pressedOutside=e.target===dialog&&outside(dialog,e)});
 dialog.addEventListener('click',e=>{if(pressedOutside&&e.target===dialog&&outside(dialog,e))closeDialog(dialog);pressedOutside=false});
});
$('#users-close').onclick=()=>closeDialog($('#users-dialog'));
$('#users-dialog').addEventListener('cancel',e=>{e.preventDefault();closeDialog($('#users-dialog'))});
captureUserDraft();
if(typeof state!=='undefined'&&state?.initialized){refreshWorkspace();if(state.fields[view])renderWorkerOverview()}
