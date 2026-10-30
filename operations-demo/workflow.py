"""Actionable problems and deterministic explanations using the same reporting rules."""
from datetime import date,datetime,timezone,timedelta
import json
from fastapi import HTTPException,Request
from access import can_read,can_edit
from domain import AREAS,summary,validate

STATUSES={'todo':'К выполнению','in_progress':'В работе','review':'На проверке','done':'Завершена'}
MSK=timezone(timedelta(hours=3))

def explain(c,current_rows,user,start,end,area='all'):
    """Reverse recorded row mutations, re-evaluate the period around each event.

    Duplicate validation, missing values and linked batches are recomputed, not guessed
    from a raw field difference. No user/administration/task events count as data edits.
    """
    allowed=[a for a in AREAS if can_read(user,a)]
    if area!='all' and area not in allowed:raise HTTPException(403,'Нет доступа к этому участку')
    rows={r['id']:dict(r) for r in current_rows if r['area'] in allowed}
    metadata={r['id']:dict(r) for r in c.execute('SELECT id,area,revision,source_row FROM records')}
    placeholders=','.join('?' for _ in allowed)
    events=c.execute(f'''SELECT a.* FROM audit a LEFT JOIN records r ON r.id=a.record
        WHERE a.action IN ('create','edit','delete','restore') AND a.record IS NOT NULL
        AND COALESCE(NULLIF(a.area,''),r.area) IN ({placeholders}) ORDER BY a.id DESC LIMIT 100''',allowed).fetchall()
    items=[]
    for event in events:
        ident=event['record'];meta=metadata.get(ident)
        if not meta:break  # A legacy physically deleted row cannot be reconstructed honestly.
        after=summary(list(rows.values()),start,end)
        old=json.loads(event['before']) if event['before'] else None
        new=json.loads(event['after']) if event['after'] else None
        if event['action'] in ('create','restore'):rows.pop(ident,None)
        elif old is not None:rows[ident]={**meta,'values':old}
        else:break
        before=summary(list(rows.values()),start,end)
        changes=[]
        for a in allowed:
            if area!='all' and a!=area:continue
            for key,label in [('known_plan','План проверенных строк'),('known_fact','Факт проверенных строк'),('known_need','Потребность проверенных строк'),('problem_rows','Проблемные строки'),('ratio','Выполнение плана')]:
                b=before['totals'][a].get(key);v=after['totals'][a].get(key)
                if b!=v:changes.append({'area':a,'metric':key,'label':label,'before':b,'after':v,'delta':v-b if b is not None and v is not None else None})
        batches=[]
        if area in ('all','production','welding'):
            b0={b['batch_id']:b for b in before['batches']};b1={b['batch_id']:b for b in after['batches']}
            for key in sorted(set(b0)|set(b1)):
                b=b0.get(key);v=b1.get(key)
                if (b or {}).get('gap')!=(v or {}).get('gap') or (b or {}).get('issues')!=(v or {}).get('issues'):
                    batches.append({'batch':key,'before':(b or {}).get('gap'),'after':(v or {}).get('gap'),
                                    'before_issues':(b or {}).get('issues',['Нет партии в периоде']),
                                    'after_issues':(v or {}).get('issues',['Нет партии в периоде'])})
        if changes or batches:
            fields=[{'field':f,'before':(old or {}).get(f),'after':(new or {}).get(f)} for f in dict.fromkeys(list(old or {})+list(new or {})) if (old or {}).get(f)!=(new or {}).get(f)]
            items.append({'id':event['id'],'at':event['at'],'actor':event['actor'] or 'Автор не указан','action':event['action'],
                          'area':meta['area'],'record':ident,'record_id':(new or old or {}).get('record_id',str(ident)),
                          'fields':fields,'metrics':changes,'batches':batches})
    return {'items':items[:20],'scanned':len(events),'period':{'start':start,'end':end},
            'note':'Влияние последних записанных правок пересчитано для выбранного периода по текущим правилам. Входы в систему и задачи цифры не меняют.'}

def register_workflow(app,db,read_rows,audit):
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS work_items(id INTEGER PRIMARY KEY AUTOINCREMENT,area TEXT NOT NULL,
          source_type TEXT NOT NULL,source_key TEXT NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL,
          assignee INTEGER NOT NULL,due TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'todo',
          created_by TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS work_events(id INTEGER PRIMARY KEY AUTOINCREMENT,task INTEGER NOT NULL,
          at TEXT NOT NULL,actor TEXT NOT NULL,kind TEXT NOT NULL,before TEXT,after TEXT,comment TEXT NOT NULL DEFAULT '');
        ''')
    def now():return datetime.now(timezone.utc).isoformat()
    def manager(u):return u['role'] in ('admin','director')
    def must_manage(request):
        if not manager(request.state.user):raise HTTPException(403,'Создавать и назначать задачи может директор или администратор')
    async def body(request):
        try:d=await request.json()
        except ValueError:raise HTTPException(422,'Некорректный JSON')
        if not isinstance(d,dict):raise HTTPException(422,'Ожидается объект')
        return d
    def text(value,label,limit,required=False):
        if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):raise HTTPException(422,f'Проверьте поле «{label}» (до {limit} символов)')
        return value.strip()
    def source(c,area,kind,key):
        if not isinstance(area,str) or area not in AREAS:raise HTTPException(422,'Неизвестный участок')
        if kind=='record':
            try:ident=int(key)
            except (ValueError,TypeError):raise HTTPException(422,'Некорректная запись')
            r=c.execute('SELECT * FROM records WHERE id=? AND area=?',(ident,area)).fetchone()
            if not r:raise HTTPException(422,'Исходная запись не найдена на этом участке')
            d=json.loads(r['payload'])
            checked=next((x for x in validate(read_rows(c)) if x['id']==ident),None)
            return {'label':d.get('record_id',str(ident)),'record':ident,'deleted':bool(r['deleted']),
                    'issues':checked['issues'] if checked else ['Исходная запись удалена'],
                    'values':d,'area':area}
        if kind=='batch':
            key=text(key,'Партия',200,True)
            rs=[r for r in read_rows(c) if r['area']==area and r['values'].get('batch_id')==key]
            if not rs:raise HTTPException(422,'Партия не найдена на этом участке')
            return {'label':'Партия '+key,'record':None,'deleted':False,'issues':[i for r in validate(read_rows(c)) if r['id'] in {x['id'] for x in rs} for i in r['issues']],
                    'values':{'batch_id':key},'area':area}
        raise HTTPException(422,'Выберите запись или партию как источник задачи')
    def assignee(c,ident,area):
        if type(ident) is not int:raise HTTPException(422,'Выберите ответственного')
        u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(ident,)).fetchone()
        if not u or not can_edit(u,area):raise HTTPException(422,'Ответственный должен иметь доступ к работе с этим участком')
        return ident
    def deadline(value):
        try:return date.fromisoformat(value).isoformat()
        except (ValueError,TypeError):raise HTTPException(422,'Укажите корректный срок')
    def record_event(c,ident,kind,user,old,new,comment=''):
        c.execute('INSERT INTO work_events(task,at,actor,kind,before,after,comment) VALUES(?,?,?,?,?,?,?)',
                  (ident,now(),user['username'],kind,json.dumps(old,ensure_ascii=False),json.dumps(new,ensure_ascii=False),comment))
        area=(new or old or {}).get('area','')
        audit(c,'task_'+kind,None,{'task':ident,**(old or {})},{'task':ident,**(new or {})},user['username'],area)
    def get_task(c,ident,user):
        t=c.execute('SELECT * FROM work_items WHERE id=?',(ident,)).fetchone()
        if not t:raise HTTPException(404,'Задача не найдена')
        if not can_read(user,t['area']):raise HTTPException(403,'Нет доступа к задачам другого участка')
        return dict(t)
    def serialized(c,t):
        u=c.execute('SELECT username,name,active,role FROM users WHERE id=?',(t['assignee'],)).fetchone()
        try:s=source(c,t['area'],t['source_type'],t['source_key'])
        except HTTPException:s={'label':t['source_key'],'record':None,'deleted':False,'issues':['Источник недоступен'],'values':{},'area':t['area']}
        return {**t,'assignee_name':u['name'] if u else 'Пользователь удалён','assignee_username':u['username'] if u else '',
                'assignee_active':bool(u and u['active']),'source':s,
                'overdue':t['status']!='done' and t['due']<datetime.now(MSK).date().isoformat()}
    @app.get('/api/tasks/assignees')
    def candidates(request:Request,area:str):
        must_manage(request)
        if area not in AREAS:raise HTTPException(422,'Неизвестный участок')
        with db() as c:return {'users':[{'id':u['id'],'username':u['username'],'name':u['name']} for u in c.execute('SELECT * FROM users WHERE active=1 ORDER BY id') if can_edit(u,area)]}
    @app.get('/api/tasks')
    def tasks(request:Request,area:str='',status:str='',mine:bool=False):
        if area and not can_read(request.state.user,area):raise HTTPException(403,'Нет доступа к этому участку')
        if status and status not in STATUSES:raise HTTPException(422,'Неизвестный статус')
        with db() as c:
            rows=[dict(t) for t in c.execute('SELECT * FROM work_items ORDER BY CASE WHEN status=\'done\' THEN 1 ELSE 0 END,due,id DESC') if can_read(request.state.user,t['area'])]
            rows=[t for t in rows if (not area or t['area']==area) and (not status or t['status']==status) and (not mine or t['assignee']==request.state.user['id'])]
            return {'items':[serialized(c,t) for t in rows],'statuses':STATUSES,'can_manage':manager(request.state.user)}
    @app.post('/api/tasks')
    async def create(request:Request):
        must_manage(request);d=await body(request);area=d.get('area');kind=d.get('source_type','record');key=str(d.get('source_key',''))
        title=text(d.get('title',''),'Название',160,True);description=text(d.get('description',''),'Описание',2000)
        due=deadline(d.get('due'))
        with db() as c:
            c.execute('BEGIN IMMEDIATE');source(c,area,kind,key);who=assignee(c,d.get('assignee'),area)
            stamp=now();ident=c.execute('INSERT INTO work_items(area,source_type,source_key,title,description,assignee,due,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (area,kind,key,title,description,who,due,request.state.user['username'],stamp,stamp)).lastrowid
            new=get_task(c,ident,request.state.user);record_event(c,ident,'create',request.state.user,None,new)
        return {'id':ident}
    @app.get('/api/tasks/{ident}')
    def task(request:Request,ident:int):
        with db() as c:
            t=get_task(c,ident,request.state.user)
            events=[{**dict(e),'before':json.loads(e['before']) if e['before'] else None,'after':json.loads(e['after']) if e['after'] else None} for e in c.execute('SELECT * FROM work_events WHERE task=? ORDER BY id',(ident,))]
            return {'task':serialized(c,t),'events':events,'can_manage':manager(request.state.user),
                    'can_progress':manager(request.state.user) or (t['assignee']==request.state.user['id'] and can_edit(request.state.user,t['area']))}
    @app.put('/api/tasks/{ident}')
    async def update(request:Request,ident:int):
        d=await body(request)
        with db() as c:
            c.execute('BEGIN IMMEDIATE');old=get_task(c,ident,request.state.user)
            if type(d.get('revision')) is not int or d['revision']!=old['revision']:raise HTTPException(409,'Задача уже изменена. Обновите карточку')
            manage=manager(request.state.user)
            if not manage and (old['assignee']!=request.state.user['id'] or not can_edit(request.state.user,old['area'])):raise HTTPException(403,'Менять статус может только ответственный')
            permitted={'revision','status','comment'}|({'title','description','assignee','due'} if manage else set())
            if set(d)-permitted:raise HTTPException(403,'Нет доступа к изменению этих полей задачи')
            status=d.get('status',old['status'])
            if not isinstance(status,str) or status not in STATUSES:raise HTTPException(422,'Неизвестный статус')
            if not manage and status!=old['status'] and status not in {'todo':{'in_progress'},'in_progress':{'review'},'review':{'in_progress'},'done':set()}[old['status']]:raise HTTPException(403,'Работник передаёт результат на проверку; закрывает задачу руководитель')
            comment=text(d.get('comment',''),'Комментарий',1000)
            if status=='done' and old['status']!='done' and not comment:raise HTTPException(422,'Опишите результат перед завершением задачи')
            title=text(d.get('title',old['title']),'Название',160,True);description=text(d.get('description',old['description']),'Описание',2000)
            who=assignee(c,d.get('assignee',old['assignee']),old['area']);due=deadline(d.get('due',old['due']))
            c.execute('UPDATE work_items SET title=?,description=?,assignee=?,due=?,status=?,revision=revision+1,updated_at=? WHERE id=?',(title,description,who,due,status,now(),ident))
            new=get_task(c,ident,request.state.user);record_event(c,ident,'update',request.state.user,old,new,comment)
        return {'saved':True}
    @app.post('/api/tasks/{ident}/comments')
    async def comment(request:Request,ident:int):
        d=await body(request);message=text(d.get('comment',''),'Комментарий',1000,True)
        with db() as c:
            t=get_task(c,ident,request.state.user);record_event(c,ident,'comment',request.state.user,{'area':t['area']},{'area':t['area']},message)
        return {'saved':True}
    @app.get('/api/changes')
    def changes(request:Request,start:str,end:str,area:str='all'):
        try:
            date.fromisoformat(start);date.fromisoformat(end)
            if start>end:raise ValueError()
        except ValueError:raise HTTPException(422,'Проверьте период')
        with db() as c:return explain(c,read_rows(c),request.state.user,start,end,area)
