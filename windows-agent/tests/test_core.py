import asyncio, hashlib, json, time, zipfile
from pathlib import Path
import pytest
from localagent.base import Store, digest, inside, redact, protect
from localagent.service import Service
from localagent.hh import HH
from localagent.tools import archive_project

class FakeTelegram:
    pass

@pytest.fixture
def store(tmp_path): return Store(tmp_path/'test.sqlite3')

def message(text,user=123,update_id=1):
    return {'update_id':update_id,'message':{'from':{'id':user},'chat':{'id':user,'type':'private'},'text':text}}

def service(store): return Service(store,FakeTelegram())

def test_dpapi_roundtrip():
    encrypted=protect(b'local-test-not-a-secret')
    assert b'local-test' not in encrypted
    assert protect(encrypted,True)==b'local-test-not-a-secret'

def test_redact():
    sample='1234567890:'+('A'*35)
    assert sample not in redact(sample)
    assert 'sk-abc123' not in redact('sk-abc123')

def test_path_traversal(tmp_path):
    with pytest.raises(ValueError): inside(tmp_path,'../escape')

def test_idempotent_queue_and_claim(store):
    store.enqueue(123,'one','same'); store.enqueue(123,'one','same')
    assert len(store.rows('SELECT * FROM tasks'))==1
    assert store.claim()['id']=='same'
    assert store.claim() is None

def test_recovery_no_replay_external_action(store):
    for name,kind in [('safe','develop'),('unsafe','shell')]:
        store.enqueue(123,'test',name); store.state(name,'running',checkpoint={'inflight':kind})
    store.recover()
    states={r['id']:r['state'] for r in store.rows('SELECT id,state FROM tasks')}
    assert states=={'safe':'queued','unsafe':'interrupted'}

def test_pairing_requires_secret_and_private_owner(store):
    svc=service(store)
    store.put('pairing',{'hash':hashlib.sha256(b'known-random-code').hexdigest(),'expires':time.time()+60})
    asyncio.run(svc.handle(message('/pair wrong',999)))
    assert not store.kv('owner')
    asyncio.run(svc.handle(message('/pair known-random-code')))
    assert store.kv('owner')==123
    assert not store.kv('pairing')
    asyncio.run(svc.handle(message('delete everything',999,2)))
    assert not store.rows('SELECT * FROM tasks')

def test_approval_bound_to_exact_plan_and_owner(store):
    svc=service(store); store.put('owner',123);store.put('owner_chat',123)
    step={'kind':'shell','summary':'example','arguments':'{"script":"echo hello"}'}
    store.enqueue(123,'test','a')
    cp={'step':step,'approval':{'code':'ABC','digest':digest(step),'expires':time.time()+60}}
    store.state('a','awaiting_approval',checkpoint=cp)
    asyncio.run(svc.handle(message('/approve a ABC',999)))
    assert store.rows('SELECT state FROM tasks')[0]['state']=='awaiting_approval'
    cp['step']['arguments']='{"script":"different"}'
    store.state('a','awaiting_approval',checkpoint=cp)
    asyncio.run(svc.handle(message('/approve a ABC')))
    assert store.rows('SELECT state FROM tasks')[0]['state']=='awaiting_approval'

def test_expired_approval_cannot_run(store):
    svc=service(store);store.put('owner',123);store.put('owner_chat',123)
    step={'kind':'shell','summary':'example','arguments':'{}'}
    store.enqueue(123,'test','a');store.state('a','awaiting_approval',checkpoint={'step':step,'approval':{'code':'X','digest':digest(step),'expires':0}})
    asyncio.run(svc.handle(message('/approve a X')))
    assert store.rows('SELECT state FROM tasks')[0]['state']=='awaiting_approval'

def test_stop_cancels_waiting_and_queued(store):
    svc=service(store);store.put('owner',123);store.put('owner_chat',123)
    store.enqueue(123,'test','one');store.enqueue(123,'test','two');store.state('two','awaiting_approval')
    asyncio.run(svc.handle(message('/stop')))
    assert store.kv('paused') is True
    assert {r['state'] for r in store.rows('SELECT * FROM tasks')}=={'cancelled'}

def test_schedule_skips_missed_periods_without_flood(store):
    svc=service(store)
    store.execute('INSERT INTO schedules VALUES(?,?,?,?,?,1)',('test',123,'test',300,time.time()-5000))
    svc.tick_schedules();svc.tick_schedules()
    assert len(store.rows('SELECT * FROM tasks'))==1
    assert store.rows('SELECT next FROM schedules')[0]['next']>time.time()

def test_archive_excludes_credentials_and_venv(tmp_path):
    project=tmp_path/'p';project.mkdir();(project/'app.py').write_text('print(1)')
    (project/'.env').write_text('SECRET=x');(project/'key.dpapi').write_bytes(b'secret')
    (project/'.venv').mkdir();(project/'.venv'/'secret').write_text('secret')
    output=tmp_path/'project.zip';archive_project(project,output)
    with zipfile.ZipFile(output) as z: assert z.namelist()==['app.py']

def test_salary_floor_different_from_upper_bound():
    assert HH.assess({'salary':{'from':50000,'to':100000,'currency':'RUR'}})['salary_check']=='possible_not_guaranteed'
    assert HH.assess({'salary':{'from':80000,'currency':'RUR'}})['salary_check']=='meets_floor'
    assert HH.assess({'salary':{'from':40000,'to':60000,'currency':'RUR'}})['salary_check']=='below_floor'
    assert HH.assess({'salary':{'from':100000,'currency':'USD'}})['salary_check']=='unknown'

def test_remote_and_unknown_format():
    assert HH.assess({'work_format':[{'id':'REMOTE'}]})['remote_only']
    assert not HH.assess({})['office_confirmed']

def test_history_import_deduplicates_and_does_not_invent_causes(store):
    hh=HH(store)
    hh.import_history([{'vacancy_id':'1','status':'discard','resume_id':'v1'},{'vacancy_id':'1','status':'discard','resume_id':'v1'}])
    stats=hh.statistics()
    assert stats['total']==1 and stats['rejection_rate']==1
    assert 'не установлены' in stats['causes']

def test_protected_step_not_executed_without_approval(store):
    svc=service(store)
    tid=store.enqueue(123,'test','protected')
    store.state(tid,'running',checkpoint={'n':0,'observations':[],'step':{'kind':'shell','summary':'test','arguments':'{"script":"echo test"}'}})
    task=store.rows('SELECT * FROM tasks WHERE id=?',(tid,))[0]
    calls=[]
    async def forbidden(*args): calls.append(args)
    svc.execute=forbidden
    asyncio.run(svc.run_task(task))
    assert not calls
    assert store.rows('SELECT state FROM tasks')[0]['state']=='awaiting_approval'

def test_unknown_views_remain_unknown(store):
    h=HH(store);h.import_history([{'vacancy_id':'x','status':'discard'}])
    assert h.statistics()['explicit_view_rate'] is None

def test_long_telegram_message_keeps_all_text_and_valid_html():
    import html,re,xml.etree.ElementTree as ET
    from localagent.telegram import Telegram
    tg=Telegram('1234567890:'+('A'*35));parts=[]
    async def capture(method,**payload):
        assert len(payload['text'])<4096
        ET.fromstring('<root>'+payload['text']+'</root>')
        parts.append(payload['text'])
    tg.call=capture
    original=('Привет <>& '*700)+'конец'
    async def run():
        await tg.text(123,original)
        await tg.client.aclose()
    asyncio.run(run())
    assert ''.join(html.unescape(re.sub('<[^>]+>','',p)) for p in parts)==original

def test_resume_rejects_invented_experience():
    from localagent.resume import evidence_profile
    source='Python. Учебный проект: Telegram-бот.'
    assert evidence_profile(source,[{'category':'skills','quote':'Python.'}])[0]['quote']=='Python.'
    with pytest.raises(ValueError):evidence_profile(source,[{'category':'experience','quote':'5 лет коммерческого опыта'}])

def test_one_time_schedule_does_not_repeat(store):
    svc=service(store)
    store.execute('INSERT INTO schedules VALUES(?,?,?,?,?,1)',('once',123,'test',0,time.time()-1))
    svc.tick_schedules();svc.tick_schedules()
    assert len(store.rows('SELECT * FROM tasks'))==1
    assert store.rows('SELECT enabled FROM schedules')[0]['enabled']==0

def test_screenshot_refuses_visible_secret_window(store):
    tools=service(store).tools
    async def windows(*args):return [{'title':'BotFather — Telegram'}]
    tools.windows=windows
    with pytest.raises(ValueError,match='BotFather'):asyncio.run(tools.screenshot('privacy',{}))

def test_gui_refuses_missing_or_changed_target():
    from localagent.gui_policy import require_target
    with pytest.raises(ValueError):require_target(None,123)
    with pytest.raises(ValueError):require_target(123,456)
    require_target(123,123)

def test_virtual_screen_includes_secondary_monitor():
    from localagent.gui_policy import in_virtual_screen
    assert in_virtual_screen((-1920,0,6000,1440),-1800,800)
    assert in_virtual_screen((-1920,0,6000,1440),3500,800)
    assert not in_virtual_screen((-1920,0,6000,1440),4080,800)
