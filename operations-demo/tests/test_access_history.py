from fastapi.testclient import TestClient
from app import create_app
from test_acceptance import demo,client,row,edit,report

def test_no_anonymous_access_and_csrf(demo):
    _,path,_=demo;anonymous=TestClient(create_app(path))
    assert anonymous.get('/api/state').status_code==401
    assert anonymous.get('/api/export?start=2026-10-05&end=2026-10-14').status_code==401
    login=anonymous.post('/api/login',json={'username':'admin','password':'demo-admin-2026'})
    assert login.status_code==200 and 'HttpOnly' in login.headers['set-cookie']
    assert anonymous.post('/api/logout').status_code==403
    anonymous.headers['x-csrf-token']=login.json()['csrf']
    assert anonymous.post('/api/logout',headers={'origin':'https://other.test'}).status_code==403
    assert anonymous.post('/api/logout').status_code==200
    assert anonymous.get('/api/state').status_code==401

def test_operator_isolation_and_readonly_director(demo):
    admin,path,_=demo;worker=client(create_app(path),'production');director=client(create_app(path),'director')
    assert {r['area'] for r in worker.get('/api/state').json()['rows']}=={'production'}
    assert set(report(worker)['totals'])=={'production'}
    csv=worker.get('/api/export?start=2026-10-05&end=2026-10-14').text
    assert 'Мария Лебедева' not in csv and 'W-001' not in csv
    d=row(admin,'D-001')
    assert worker.put(f'/api/records/docs/{d["id"]}',json={'values':d['values'],'revision':1}).status_code==403
    p=row(admin,'P-001')
    assert director.put(f'/api/records/production/{p["id"]}',json={'values':p['values'],'revision':p['revision']}).status_code==403
    assert director.post('/api/users',json={}).status_code==403
    assert worker.get('/api/users').status_code==403
    assert worker.get('/api/history?area=docs').status_code==403
    assert worker.post('/api/preview/docs?start=2026-10-05&end=2026-10-14',json={'values':d['values']}).status_code==403
    assert len(director.get('/api/state').json()['rows'])==23

def test_access_changes_apply_immediately_and_password_resets_sessions(demo):
    admin,path,_=demo
    created=admin.post('/api/users',json={'username':'newworker','name':'Новый сотрудник','role':'production','password':'initial-pass-2026','active':True})
    assert created.status_code==200;ident=created.json()['id']
    worker=TestClient(create_app(path));login=worker.post('/api/login',json={'username':'newworker','password':'initial-pass-2026'})
    assert login.status_code==200;worker.headers['x-csrf-token']=login.json()['csrf']
    change={'name':'Новый сотрудник','role':'docs','password':'','active':True}
    assert admin.put('/api/users/'+str(ident),json=change).status_code==200
    assert {r['area'] for r in worker.get('/api/state').json()['rows']}=={'docs'}
    change['active']=False;assert admin.put('/api/users/'+str(ident),json=change).status_code==200
    assert worker.get('/api/state').status_code==401
    change.update(active=True,password='changed-pass-2026');assert admin.put('/api/users/'+str(ident),json=change).status_code==200
    assert worker.post('/api/login',json={'username':'newworker','password':'initial-pass-2026'}).status_code==401
    assert worker.post('/api/login',json={'username':'newworker','password':'changed-pass-2026'}).status_code==200
    users=admin.get('/api/users').json();assert 'password_hash' not in str(users)
    adminid=next(u['id'] for u in users['users'] if u['username']=='admin')
    assert admin.put('/api/users/'+str(adminid),json={'name':'Админ','role':'director','password':'','active':True}).status_code==409
    history=admin.get('/api/history').text
    assert 'initial-pass-2026' not in history and 'changed-pass-2026' not in history

def test_preview_history_and_reversible_delete(demo):
    c,path,_=demo;p=row(c,'P-003');v={**p['values'],'fact_qty':'120'}
    pre=c.post('/api/preview/production?start=2026-10-05&end=2026-10-14',json={'id':p['id'],'values':v})
    assert pre.status_code==200 and not pre.json()['issues']
    assert pre.json()['batches'][0]['gap']==10
    assert row(c,'P-003')['values']['fact_qty']=='1200'
    edit(c,p,fact_qty='120')
    history=c.get('/api/history',params={'record':p['id']}).json()['items']
    assert history[0]['actor']=='admin'
    assert {'field':'fact_qty','before':'1200','after':'120'} in history[0]['changes']
    fresh=row(c,'P-003');assert c.delete(f'/api/records/production/{p["id"]}?revision={fresh["revision"]}').status_code==200
    deleted=c.get('/api/history',params={'record':p['id']}).json()['items'][0]
    assert deleted['deleted']
    assert c.post(f'/api/records/production/{p["id"]}/restore',json={'revision':deleted['revision']}).status_code==200
    assert row(client(create_app(path)),'P-003')['values']['fact_qty']=='120'
    assert c.post(f'/api/records/production/{p["id"]}/restore',json={'revision':deleted['revision']}).status_code==409
    point=next(d for d in report(c)['daily'] if d['date']=='2026-10-07')
    assert point['production']==120 and point['production_plan']==100

def test_login_throttle_is_persisted(tmp_path):
    c=TestClient(create_app(tmp_path/'access.sqlite3'))
    for _ in range(10):assert c.post('/api/login',json={'username':'admin','password':'wrong'}).status_code==401
    assert c.post('/api/login',json={'username':'admin','password':'wrong'}).status_code==429
