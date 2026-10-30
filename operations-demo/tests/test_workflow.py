from test_acceptance import demo,client,row,edit,report
from app import create_app

def create(c,record='P-003'):
    r=row(c,record);candidates=c.get('/api/tasks/assignees?area=production').json()['users']
    who=next(u['id'] for u in candidates if u['username']=='production')
    result=c.post('/api/tasks',json={'area':'production','source_type':'record','source_key':str(r['id']),
        'title':'Проверить факт '+record,'description':'Сверить с первичным документом','assignee':who,'due':'2026-10-30'})
    assert result.status_code==200
    return result.json()['id']

def test_task_lifecycle_permissions_source_and_restart(demo):
    admin,path,_=demo;director=client(create_app(path),'director');worker=client(create_app(path),'production');other=client(create_app(path),'docs')
    ident=create(director)
    assert worker.post('/api/tasks',json={}).status_code==403
    assert other.get('/api/tasks/'+str(ident)).status_code==403
    assert other.get('/api/tasks').json()['items']==[]
    before=report(admin);task=worker.get('/api/tasks/'+str(ident)).json()['task']
    assert task['source']['issues'] and task['assignee_username']=='production'
    assert worker.put('/api/tasks/'+str(ident),json={'revision':task['revision'],'status':'done','comment':'Проверено'}).status_code==403
    assert worker.put('/api/tasks/'+str(ident),json={'revision':task['revision'],'status':'in_progress'}).status_code==200
    assert worker.put('/api/tasks/'+str(ident),json={'revision':task['revision'],'status':'review'}).status_code==409
    assert worker.post('/api/tasks/'+str(ident)+'/comments',json={'comment':'Проверяю исходные данные'}).status_code==200
    t=worker.get('/api/tasks/'+str(ident)).json()['task']
    assert worker.put('/api/tasks/'+str(ident),json={'revision':t['revision'],'assignee':1}).status_code==403
    edit(worker,row(worker,'P-003'),fact_qty='120')
    assert worker.put('/api/tasks/'+str(ident),json={'revision':t['revision'],'status':'review','comment':'Исправил факт на 120'}).status_code==200
    t=director.get('/api/tasks/'+str(ident)).json()['task']
    assert t['source']['issues']==[]
    assert director.put('/api/tasks/'+str(ident),json={'revision':t['revision'],'status':'done'}).status_code==422
    assert director.put('/api/tasks/'+str(ident),json={'revision':t['revision'],'status':'done','comment':'Сверка проверена, дефицит 10 виден на панели'}).status_code==200
    restarted=client(create_app(path));result=restarted.get('/api/tasks/'+str(ident)).json()
    assert result['task']['status']=='done' and len(result['events'])==5
    assert {'director','production'}=={e['actor'] for e in result['events']}
    after=report(admin);assert before['totals']['docs']==after['totals']['docs']
    assert after['totals']['production']['known_fact']==410

def test_task_status_does_not_repair_data_and_invalid_requests(demo):
    c,path,_=demo;ident=create(c);initial=report(c);t=c.get('/api/tasks/'+str(ident)).json()['task']
    assert c.put('/api/tasks/'+str(ident),json={'revision':t['revision'],'status':[]}).status_code==422
    assert c.put('/api/tasks/'+str(ident),json={'revision':t['revision'],'status':'done','comment':'Закрыта проверка, исправление данных остаётся отдельным действием'}).status_code==200
    assert report(c)==initial
    assert c.get('/api/tasks/'+str(ident)).json()['task']['source']['issues']
    users=c.get('/api/users').json()['users'];docs=next(u['id'] for u in users if u['username']=='docs')
    bad={'area':'production','source_type':'record','source_key':str(row(c,'P-003')['id']),'title':'Проверка','assignee':docs,'due':'2026-10-30'}
    assert c.post('/api/tasks',json=bad).status_code==422
    bad['area']=[];assert c.post('/api/tasks',json=bad).status_code==422
    assert c.post('/api/tasks/'+str(ident)+'/comments',json={'comment':''}).status_code==422

def test_change_explanation_recomputes_linked_metrics_and_ignores_tasks(demo):
    c,path,_=demo
    edit(c,row(c,'P-003'),fact_qty='120')
    create(c)
    result=c.get('/api/changes?start=2026-10-05&end=2026-10-14&area=all');assert result.status_code==200
    e=result.json()['items'][0];assert e['record_id']=='P-003' and e['actor']=='admin'
    m=next(x for x in e['metrics'] if x['metric']=='known_fact');assert (m['before'],m['after'],m['delta'])==(290,410,120)
    b=next(x for x in e['batches'] if x['batch']=='LOT-03');assert b['before'] is None and b['after']==10
    assert all(m['area']!='docs' for m in e['metrics'])
    edit(c,row(c,'D-001'),fact_docs='5')
    worker=client(create_app(path),'production')
    scoped=worker.get('/api/changes?start=2026-10-05&end=2026-10-14&area=all').json()
    assert all(e['area']=='production' for e in scoped['items'])
    assert worker.get('/api/changes?start=2026-10-05&end=2026-10-14&area=docs').status_code==403

def test_duplicate_removal_can_increase_verified_fact(demo):
    c,_,_=demo;duplicates=[r for r in c.get('/api/state').json()['rows'] if r['values']['record_id']=='P-005'];r=duplicates[-1]
    assert c.delete(f'/api/records/production/{r["id"]}?revision={r["revision"]}').status_code==200
    e=c.get('/api/changes?start=2026-10-05&end=2026-10-14&area=production').json()['items'][0]
    assert e['action']=='delete'
    fact=next(m for m in e['metrics'] if m['metric']=='known_fact');assert fact['delta']==80
    assert next(m for m in e['metrics'] if m['metric']=='problem_rows')['delta']==-2
    assert c.get('/api/changes?start=invalid&end=invalid').status_code==422
