import asyncio,json,time
import pytest
from localagent.base import Store
from localagent.service import Service
from localagent.experience import profile,remember
from localagent.personal import context

class Bot:
    def __init__(self):self.calls=[]
    async def call(self,method,**payload):
        self.calls.append((method,payload))
        return {'message_id':100+len(self.calls)} if method=='sendMessage' else True

@pytest.fixture
def env(tmp_path,monkeypatch):
    import localagent.service as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    s=Store(tmp_path/'memory.sqlite3');s.put('owner',123);s.put('owner_chat',123)
    svc=Service(s,Bot());svc.ui.post('post1',123,'Идея: компактный виджет для мебельщиков.','idea');svc.ui.bind(123,'post1',{'message_id':77})
    return svc,s

def msg(text,uid=1,reply=None,user=123):
    m={'from':{'id':user},'chat':{'id':user,'type':'private'},'text':text}
    if reply:m['reply_to_message']={'message_id':reply}
    return {'update_id':uid,'message':m}

def cb(action='save',qid='q1',user=123,mid=77,pid='post1'):
    return {'callback_query':{'id':qid,'from':{'id':user},'data':f'p:{action}:{pid}',
        'message':{'message_id':mid,'chat':{'id':123,'type':'private'}}}}

def test_buttons_bind_to_delivered_message_and_ack_callback(env):
    svc,s=env;asyncio.run(svc.handle(cb()))
    assert s.kv('personal_saved')[0]['text'].startswith('Идея')
    assert svc.tg.calls[0][0]=='answerCallbackQuery'

def test_forged_callback_cannot_target_a_different_message(env):
    svc,s=env;asyncio.run(svc.handle(cb(mid=999)))
    assert not s.kv('personal_saved')

def test_unauthorized_callback_never_reads_or_changes_profile(env):
    svc,s=env;asyncio.run(svc.handle(cb(user=999)))
    assert not svc.tg.calls and not s.kv('personal_saved')

def test_save_and_ratings_are_idempotent_and_persist(env):
    svc,s=env
    for action in ('save','save','like','like','dislike'):asyncio.run(svc.handle(cb(action)))
    assert len(s.kv('personal_saved'))==1 and len(s.kv('personal_feedback'))==1
    fresh=Service(Store(s.path),Bot())
    assert profile(fresh.store)['taste_examples'][0]['rating']==-1
    assert not profile(s)['confirmed_facts']

def test_reply_save_uses_correct_persisted_post_not_last_post(env):
    svc,s=env;svc.ui.post('post2',123,'Другая тема','news')
    fresh=Service(Store(s.path),Bot());asyncio.run(fresh.handle(msg('сохрани',reply=77)))
    assert s.kv('personal_saved')[0]['post']=='post1'

def test_reply_message_carries_exact_post_context(env):
    svc,s=env;asyncio.run(svc.handle(msg('Какая первая проверка?',reply=77)))
    assert 'компактный виджет' in s.rows('SELECT prompt FROM tasks')[0]['prompt']

def test_more_callback_cannot_requeue_an_already_started_job(env):
    svc,s=env;asyncio.run(svc.handle(cb('more')))
    row=s.rows('SELECT * FROM tasks')[0];s.state(row['id'],'in_codex')
    asyncio.run(svc.handle(cb('more')))
    assert len(s.rows('SELECT * FROM tasks'))==1 and s.rows('SELECT state FROM tasks')[0]['state']=='in_codex'

def test_reminder_picker_buttons_are_bound_and_one_off(env):
    svc,s=env;asyncio.run(svc.handle(cb('later')))
    sent=[p for method,p in svc.tg.calls if method=='sendMessage'][0]
    binding=s.rows('SELECT message FROM post_messages WHERE message<>77')[0]['message']
    assert all(len(b['callback_data'].encode())<=64 for b in sent['reply_markup']['inline_keyboard'][0])
    asyncio.run(svc.handle(cb('hour',qid='later-hour',mid=binding)))
    asyncio.run(svc.handle(cb('hour',qid='later-hour',mid=binding)))
    rows=s.rows('SELECT * FROM schedules');assert len(rows)==1 and 'виджет' in rows[0]['prompt']
    assert 3500<rows[0]['next']-time.time()<3700

def test_short_natural_reminder_uses_replied_post(env):
    svc,s=env;asyncio.run(svc.handle(msg('напомни через 20 минут',reply=77)))
    row=s.rows('SELECT * FROM schedules')[0]
    assert 'виджет' in row['prompt'] and 1190<row['next']-time.time()<1210

def test_explicit_memory_survives_restart_and_can_be_forgotten(env):
    svc,s=env;asyncio.run(svc.handle(msg('Запомни: мне удобны короткие ответы')))
    key=s.rows('SELECT key FROM memory')[0]['key']
    fresh=Service(Store(s.path),Bot());assert 'короткие ответы' in fresh.ui.memory_text()
    asyncio.run(fresh.handle(msg('/forget '+key,uid=2)))
    assert not s.rows('SELECT * FROM memory')

def test_ordinary_content_is_not_automatically_saved_as_fact(env):
    svc,s=env;asyncio.run(svc.handle(msg('Сосед сказал что я миллионер')))
    assert not s.rows('SELECT * FROM memory')

@pytest.mark.parametrize('secret',['password=hidden','токен: hidden','1234567890:'+'A'*35])
def test_secrets_are_not_committed_to_memory(env,secret):
    svc,s=env
    with pytest.raises(ValueError):remember(s,secret)
    assert not s.rows('SELECT * FROM memory')

def test_profile_context_is_bounded_without_deleting_memory(env):
    svc,s=env
    for i in range(20):remember(s,str(i)+' '+('факт '*200))
    assert len(json.dumps(profile(s),ensure_ascii=False))<=4800
    assert len(s.rows('SELECT * FROM memory'))==20

def test_quiet_mode_mutes_feed_but_keeps_reminders(env):
    svc,s=env;asyncio.run(svc.handle(msg('/remind 1ч встреча')))
    asyncio.run(svc.handle(msg('/mode quiet',uid=2)))
    assert not context(s)['enabled'] and len(context(s)['reminders'])==1
    asyncio.run(svc.handle(msg('/mode leisure',uid=3)));assert context(s)['enabled']

def test_home_is_one_editable_pinned_message(env):
    svc,s=env;asyncio.run(svc.handle(msg('/home')));mid=s.kv('home_message')
    asyncio.run(svc.handle(msg('/home',uid=2)))
    assert s.kv('home_message')==mid and s.kv('home_pinned')
    assert [m for m,_ in svc.tg.calls].count('sendMessage')==1
    assert 'editMessageText' in [m for m,_ in svc.tg.calls]

def test_speak_button_dispatches_local_worker_not_model(env):
    svc,s=env;asyncio.run(svc.handle(cb('speak')))
    cp=json.loads(s.rows('SELECT checkpoint FROM tasks')[0]['checkpoint'])
    assert cp['direct'] and cp['step']['kind']=='speak'

def test_mail_draft_button_requests_text_only_without_sending(env):
    svc,s=env;asyncio.run(svc.handle(cb('draft')))
    prompt=s.rows('SELECT prompt FROM tasks')[0]['prompt']
    assert 'Не отправляй' in prompt and 'Выбранный пост' in prompt
