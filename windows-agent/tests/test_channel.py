import asyncio,json,time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from localagent.base import Store
from localagent.service import Service
from localagent.app_bridge import AppBridge
from localagent.channel import queue_publication

class Bot:
    def __init__(self):self.calls=[]
    async def call(self,method,**payload):
        self.calls.append((method,payload));return {'message_id':900}

@pytest.fixture
def env(tmp_path):
    s=Store(tmp_path/'state.sqlite3');s.put('owner',123);s.put('owner_chat',123)
    s.put('publication_channel',{'enabled':True,'id':-10042,'username':'example','title':'Канал'})
    svc=Service(s,Bot())
    return svc,s

def preview(svc,kind='news',candidate=True,method='photo',mid=77):
    s=svc.store;payload={'caption':'Пост с источником и датой','text':'Пост с источником и датой','kind':kind,'interactive':True,'channel_candidate':candidate}
    with s.db() as c:
        ident=c.execute('INSERT INTO outbox(chat,method,payload,sent) VALUES(?,?,?,1)',(123,method,json.dumps(payload))).lastrowid
    row=s.rows('SELECT * FROM outbox WHERE id=?',(ident,))[0]
    decorated=svc.ui.decorate(row,payload);svc.ui.bind(123,decorated[0],{'message_id':mid})
    return decorated[0],decorated[1],ident

def callback(pid,user=123,mid=77):
    return {'callback_query':{'id':'click','from':{'id':user},'data':'p:publish:'+pid,
            'message':{'message_id':mid,'chat':{'id':123,'type':'private'}}}}

def test_only_public_editorial_previews_get_publish_button(env):
    svc,s=env
    for kind,candidate,expected in [('news',True,True),('meme',True,True),('idea',True,True),('fact',True,True),('mail',True,False),('reply',True,False),('news',False,False)]:
        _,keyboard,_=preview(svc,kind,candidate)
        assert any(b['callback_data'].startswith('p:publish:') for row in keyboard['inline_keyboard'] for b in row)==expected
    assert not s.rows('SELECT * FROM channel_publications')

def test_click_copies_exact_preview_once_and_survives_restart(env):
    svc,s=env;pid,_,source=preview(svc)
    asyncio.run(svc.handle(callback(pid)));asyncio.run(svc.handle(callback(pid)))
    fresh=Service(Store(s.path),Bot());asyncio.run(fresh.handle(callback(pid)))
    rows=s.rows("SELECT * FROM outbox WHERE method='copyMessage'");assert len(rows)==1
    assert rows[0]['chat']==-10042
    payload=json.loads(rows[0]['payload'])
    assert payload['from_chat_id']==123 and payload['message_id']==77 and payload['source_outbox']==source
    assert 'path' not in payload and 'text' not in payload
    assert not fresh.ui.decorate(rows[0],payload)

def test_foreign_user_and_forged_message_cannot_publish(env):
    svc,s=env;pid,_,_=preview(svc)
    asyncio.run(svc.handle(callback(pid,user=999)))
    asyncio.run(svc.handle(callback(pid,mid=999)))
    assert not s.rows("SELECT * FROM outbox WHERE method='copyMessage'")

@pytest.mark.parametrize('kind,candidate',[('mail',True),('reply',True),('news',False)])
def test_forged_publish_action_does_not_publish_private_content(env,kind,candidate):
    svc,s=env;pid,_,_=preview(svc,kind,candidate)
    asyncio.run(svc.handle(callback(pid)))
    assert not s.rows('SELECT * FROM channel_publications')

def test_parallel_repeated_clicks_enqueue_one_copy(env):
    svc,s=env;pid,_,_=preview(svc)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _:queue_publication(s,123,pid,77),range(8)))
    assert len(s.rows('SELECT * FROM channel_publications'))==1
    assert len(s.rows("SELECT * FROM outbox WHERE method='copyMessage'"))==1

def test_bridge_marks_only_automation_public_sections(env):
    svc,s=env;b=AppBridge(svc)
    b.finish({'items':[]},{'id':'a','phase':'final_answer','text':'<!-- feed-post:news -->\nНовость\n<!-- feed-post:mail -->\nЛичная почта\n<heartbeat><automation_id>telegram</automation_id><decision>NOTIFY</decision><message>Посты</message></heartbeat>'})
    rows=s.rows('SELECT payload FROM outbox ORDER BY id')
    assert [json.loads(r['payload'])['channel_candidate'] for r in rows]==[True,False]
    b.finish({'items':[]},{'id':'b','phase':'final_answer','text':'Ответ на личное поручение'})
    assert not json.loads(s.rows('SELECT payload FROM outbox ORDER BY id DESC LIMIT 1')[0]['payload']).get('channel_candidate')

def test_real_delivery_path_strips_private_keyboard_and_records_receipt(env,tmp_path,monkeypatch):
    import localagent.service as module
    monkeypatch.setattr('localagent.channel.publication_due',lambda s,p,now:now)
    svc,s=env;pid,_,_=preview(svc);queue_publication(s,123,pid,77)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    async def stop(_):(tmp_path/'STOP').write_text('test')
    monkeypatch.setattr(module.asyncio,'sleep',stop)
    asyncio.run(svc.deliver())
    copies=[p for method,p in svc.tg.calls if method=='copyMessage']
    assert len(copies)==1 and copies[0]['reply_markup']=={'inline_keyboard':[]}
    row=s.rows("SELECT * FROM outbox WHERE method='copyMessage'")[0]
    assert row['sent'] and row['sent_at'] and json.loads(row['receipt'])['message_id']==900

def test_ambiguous_channel_failure_is_not_automatically_retried(env,tmp_path,monkeypatch):
    import localagent.service as module
    monkeypatch.setattr('localagent.channel.publication_due',lambda s,p,now:now)
    svc,s=env;pid,_,_=preview(svc);queue_publication(s,123,pid,77)
    async def fail(*a,**kw):raise RuntimeError('Telegram network error')
    svc.tg.call=fail;monkeypatch.setattr(module,'ROOT',tmp_path)
    async def stop(_):(tmp_path/'STOP').write_text('test')
    monkeypatch.setattr(module.asyncio,'sleep',stop)
    asyncio.run(svc.deliver())
    row=s.rows("SELECT * FROM outbox WHERE method='copyMessage'")[0]
    assert not row['sent'] and row['next_attempt']>time.time()+86400 and row['last_error']
    assert 'автоматический повтор' in queue_publication(s,123,pid,77).lower()

def automatic(s,now,after=0):
    cfg=s.kv('publication_channel');cfg.update(mode='automatic',interval_seconds=2700,
        automatic_since=now-60,after_outbox=after)
    s.put('publication_channel',cfg)

def test_automatic_queues_only_fresh_public_previews_once(env):
    from localagent.channel import queue_automatic
    svc,s=env;now=time.time()
    _,_,old=preview(svc,mid=70)
    automatic(s,now,after=old)
    for kind,candidate,mid in [('news',True,71),('mail',True,72),('reply',False,73)]:
        _,_,ident=preview(svc,kind,candidate,mid=mid)
        s.delivered(ident,{'message_id':mid})
    queue_automatic(s,now);queue_automatic(s,now)
    copies=s.rows("SELECT * FROM outbox WHERE method='copyMessage'")
    assert len(copies)==1
    assert json.loads(copies[0]['payload'])['message_id']==71
    assert json.loads(copies[0]['payload'])['automatic']
    Service(Store(s.path),Bot())
    queue_automatic(s,now)
    assert len(s.rows('SELECT * FROM channel_publications'))==1

def test_interval_night_pause_and_expiry_are_checked_at_dispatch(env):
    from datetime import datetime,timezone,timedelta
    from localagent.channel import publication_due,HELD
    _,s=env;tz=timezone(timedelta(hours=3))
    stamp=lambda h,m=0:datetime(2026,10,27,h,m,tzinfo=tz).timestamp()
    now=stamp(21,50);automatic(s,now)
    s.put('editorial_last:-10042',{'at':stamp(21,30)})
    due=publication_due(s,{},now)
    assert datetime.fromtimestamp(due,tz).isoformat()=='2026-10-28T09:00:00+03:00'
    assert publication_due(s,{'automatic':True,'source_at':now-21601},now)==HELD
    s.put('editorial_last:-10042',{'at':stamp(12)})
    assert publication_due(s,{},stamp(12,20))==stamp(12,45)
    s.put('paused',True)
    assert publication_due(s,{},stamp(13))==stamp(13)+60
    s.put('paused',False);s.put('personal_mode','quiet')
    assert publication_due(s,{},stamp(13))==stamp(13)+60

def test_channel_pause_commands_preserve_configuration(env):
    svc,s=env
    asyncio.run(svc.ui.words(123,'/channel pause','pause'))
    assert s.kv('publication_channel')['paused'] is True
    assert s.kv('publication_channel')['id']==-10042
    asyncio.run(svc.ui.words(123,'/channel resume','resume'))
    assert s.kv('publication_channel')['paused'] is False

def test_automatic_delivery_uses_existing_receipt_without_click(env,tmp_path,monkeypatch):
    import localagent.service as module
    svc,s=env;now=time.time();automatic(s,now)
    _,_,ident=preview(svc)
    s.delivered(ident,{'message_id':77})
    monkeypatch.setattr('localagent.channel.publication_due',lambda s,p,now:now)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    async def stop(_):(tmp_path/'STOP').write_text('test')
    monkeypatch.setattr(module.asyncio,'sleep',stop)
    asyncio.run(svc.deliver())
    copies=[p for method,p in svc.tg.calls if method=='copyMessage']
    assert len(copies)==1 and copies[0]['message_id']==77 and copies[0]['chat_id']==-10042
    row=s.rows("SELECT * FROM outbox WHERE method='copyMessage'")[0]
    assert row['sent'] and row['receipt']

def test_split_media_post_is_not_automatically_published(env,tmp_path,monkeypatch):
    import localagent.app_bridge as module
    svc,s=env;media=tmp_path/'image.jpg'
    monkeypatch.setattr(module,'linked_artifacts',lambda _: [media])
    monkeypatch.setattr(module,'artifact_method',lambda _:'photo')
    monkeypatch.setattr(module,'artifact_caption',lambda *args:'Источник и дата')
    module.AppBridge(svc).finish({'items':[]},{'id':'long','text':'<!-- feed-post:news -->\n'+('Длинный текст '*100)+'\n<heartbeat><automation_id>telegram</automation_id><decision>NOTIFY</decision><message>Пост</message></heartbeat>'})
    rows=s.rows('SELECT payload FROM outbox')
    assert len(rows)==2
    assert all(not json.loads(r['payload'])['channel_candidate'] for r in rows)
