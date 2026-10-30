import asyncio,json,time
from datetime import datetime,timedelta
import pytest
from localagent.base import Store
from localagent.service import Service
from localagent.personal import MSK,CONTENT,parse_reminder,add_reminder,context
from localagent.app_bridge import artifact_method,artifact_caption

NOW=datetime(2026,10,24,12,0,tzinfo=MSK)

@pytest.mark.parametrize('text,seconds',[
 ('20м размяться',1200),('через 2 часа позвонить',7200),('напомни мне через 30 секунд проверить',30),
 ('завтра в 10:00 позвонить',22*3600),('сегодня 18:30 встреча',23400),
 ('11:00 зарядка',23*3600),('2026-10-25 14:00 встреча',26*3600)])
def test_reminder_time_and_body(text,seconds):
    due,body=parse_reminder(text,NOW)
    assert (due-NOW).total_seconds()==seconds and body

@pytest.mark.parametrize('text',['0м ничего','400д слишком долго','сегодня 10:00 прошло','25:00 ошибка','непонятно','завтра 10:00','2026-13-32 10:00 ошибка'])
def test_invalid_reminder_does_not_guess(text):
    with pytest.raises(ValueError):parse_reminder(text,NOW)

@pytest.fixture
def env(tmp_path,monkeypatch):
    import localagent.service as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    s=Store(tmp_path/'test.sqlite3');s.put('owner',123);s.put('owner_chat',123)
    return Service(s,object()),s

def message(text,user=123):return {'update_id':800,'message':{'from':{'id':user},'chat':{'id':user,'type':'private'},'text':text}}

@pytest.mark.parametrize('command',list(CONTENT))
def test_content_commands_go_to_bound_chat(env,command):
    svc,s=env;s.put('personal_topics','космос и роботы')
    asyncio.run(svc.handle(message(command)))
    row=s.rows('SELECT * FROM tasks')[0]
    assert json.loads(row['checkpoint'])['route']=='assistant' and 'космос и роботы' in row['prompt']

def test_reminder_is_direct_idempotent_and_fires_once(env):
    svc,s=env
    asyncio.run(svc.handle(message('/remind 20м проверить')))
    asyncio.run(svc.handle(message('/remind 20м проверить')))
    assert len(s.rows('SELECT * FROM schedules'))==1 and not s.rows('SELECT * FROM tasks')
    s.execute('UPDATE schedules SET next=?',(time.time()-1,))
    svc.tick_schedules();svc.tick_schedules()
    notifications=[json.loads(r['payload'])['text'] for r in s.rows('SELECT payload FROM outbox')]
    assert sum('**Напоминание**' in t for t in notifications)==1
    assert s.rows('SELECT enabled FROM schedules')[0]['enabled']==0
    assert s.rows('SELECT state FROM tasks')[0]['state']=='completed'

def test_voice_reminder_bypasses_model(env,monkeypatch):
    svc,s=env;tid=s.enqueue(123,'[VOICE_FILE] fake.ogg','voice-test')
    s.state(tid,'running',checkpoint={'route':'assistant'})
    async def transcribe(*args):return 'Напомни через 20 минут размяться'
    monkeypatch.setattr(svc.tools,'transcribe',transcribe)
    asyncio.run(svc.run_task(s.rows('SELECT * FROM tasks')[0]))
    assert len(s.rows('SELECT * FROM schedules'))==1 and s.rows('SELECT state FROM tasks')[0]['state']=='completed'

def test_feed_settings_saved_notes_and_cancel_reminder(env):
    svc,s=env
    for command in ('/feed off','/topics Роботы, книги','/save Идея для проверки','/remind 1ч встреча'):
        asyncio.run(svc.handle(message(command)))
    state=context(s)
    assert not state['enabled'] and state['topics']=='Роботы, книги' and len(state['saved'])==1
    sid=s.rows('SELECT id FROM schedules')[0]['id']
    asyncio.run(svc.handle(message('/unschedule '+sid)))
    assert not context(s)['reminders']
    asyncio.run(svc.handle(message('/feed on')));assert context(s)['enabled']

def test_read_commands_do_not_create_model_jobs(env):
    svc,s=env
    for command in ('/feed status','/topics','/reminders','/saved'):
        asyncio.run(svc.handle(message(command)))
    assert not s.rows('SELECT * FROM tasks') and len(s.rows('SELECT * FROM outbox'))==4

def test_outsider_cannot_use_personal_commands(env):
    svc,s=env
    for command in (*CONTENT,'/remind 1ч секрет','/topics чужое','/save чужое','/feed off'):
        asyncio.run(svc.handle(message(command,user=999)))
    assert not s.rows('SELECT * FROM tasks') and not s.rows('SELECT * FROM schedules') and not s.rows('SELECT * FROM outbox')
    assert s.kv('personal_saved') is None

def test_picture_is_photo_and_invalid_image_is_document(tmp_path):
    from PIL import Image
    valid=tmp_path/'cute.png';Image.new('RGB',(128,128)).save(valid)
    invalid=tmp_path/'broken.png';invalid.write_text('not an image')
    assert artifact_method(valid)=='photo' and artifact_method(invalid)=='file'

def test_news_caption_stays_with_its_photo_and_redacts_secrets(tmp_path):
    first=tmp_path/'first.jpg';second=tmp_path/'second.jpg'
    text=f'![NASA, 23.10, карта]({first})\n![ESA, архивный кадр, password=hidden]({second})'
    assert artifact_caption(text,first)=='NASA, 23.10, карта'
    caption=artifact_caption(text,second)
    assert 'ESA' in caption and 'hidden' not in caption and 'NASA' not in caption
