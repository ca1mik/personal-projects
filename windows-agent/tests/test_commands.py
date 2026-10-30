"""Every advertised Telegram command: isolated handler and state-transition checks."""
import asyncio,hashlib,json,time
from pathlib import Path
import pytest
from localagent.base import Store,digest
from localagent.service import Service
from localagent.app_bridge import public_messages,task_markers,AppBridge

def message(text,user=123):return {'update_id':700,'message':{'from':{'id':user},'chat':{'id':user,'type':'private'},'text':text}}

@pytest.fixture
def env(tmp_path,monkeypatch):
    import localagent.service as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    store=Store(tmp_path/'test.sqlite3');store.put('owner',123);store.put('owner_chat',123)
    return Service(store,object()),store

@pytest.mark.parametrize('command,expected',[
    ('/start','Ваш помощник'),('/help','Ваш помощник'),('/ping','На связи'),
    ('/sync','Telegram ↔ Codex'),('/bridge','Telegram ↔ Codex'),
    ('/status','Состояние помощника'),('/tasks','Ваши задачи'),('/history','Ваши задачи'),
    ('/logs','Последние события'),('/schedules','Расписания'),('/hhstats','Отклики'),
    ('/progress','не найдена'),('/does_not_exist','Неизвестная команда')])
def test_read_commands(env,command,expected):
    svc,store=env;asyncio.run(svc.handle(message(command)))
    text='\n'.join(json.loads(r['payload'])['text'] for r in store.rows('SELECT payload FROM outbox'))
    assert expected.lower() in text.lower()
    assert not store.rows('SELECT * FROM tasks')

@pytest.mark.parametrize('command,kind',[('/screenshot','screenshot'),('/windows','windows'),('/hh CRM','hh_search'),('/selftest','diagnostics')])
def test_local_commands_dispatch_exact_tool(env,command,kind):
    svc,store=env;asyncio.run(svc.handle(message(command)))
    task=store.rows('SELECT * FROM tasks')[0]
    assert task['state']=='queued' and json.loads(task['checkpoint'])['step']['kind']==kind

@pytest.mark.parametrize('command,route',[('/ask Проверь бота','assistant'),('/goal Доделай бота','assistant'),('/local Создай проект','local'),('Исправь работающего бота','assistant')])
def test_routing_to_same_chat_instead_of_demo_projects(env,command,route):
    svc,store=env;asyncio.run(svc.handle(message(command)))
    task=store.rows('SELECT * FROM tasks')[0]
    assert json.loads(task['checkpoint'])['route']==route
    if command.startswith('/goal'):assert task['prompt'].startswith('/goal')

@pytest.mark.parametrize('command',['/every 60 Проверить новости','/every 0 нельзя','/every broken'])
def test_schedule_validation(env,command):
    svc,store=env;asyncio.run(svc.handle(message(command)))
    rows=store.rows('SELECT * FROM schedules')
    assert bool(rows)==command.startswith('/every 60')
    if rows:
        asyncio.run(svc.handle(message('/unschedule '+rows[0]['id'])))
        assert store.rows('SELECT enabled FROM schedules')[0]['enabled']==0

def test_cancel_retry_stop_resume_and_shutdown(env,tmp_path):
    svc,store=env
    tid=store.enqueue(123,'test','one')
    asyncio.run(svc.handle(message('/cancel 1')));assert store.rows('SELECT state FROM tasks')[0]['state']=='cancelled'
    store.state(tid,'failed',checkpoint={})
    asyncio.run(svc.handle(message('/retry 1')));assert store.rows('SELECT state FROM tasks')[0]['state']=='queued'
    asyncio.run(svc.handle(message('/stop')));assert store.kv('paused') and store.rows('SELECT state FROM tasks')[0]['state']=='cancelled'
    asyncio.run(svc.handle(message('/resume')));assert not store.kv('paused')
    asyncio.run(svc.handle(message('/service_stop')));assert svc.closing and (tmp_path/'STOP').exists()

def test_approve_and_deny_exact_plan(env):
    svc,store=env
    step={'kind':'shell','summary':'harmless check','arguments':'{"script":"Write-Output OK"}'}
    tid=store.enqueue(123,'test','one')
    cp={'step':step,'approval':{'code':'ABCD','expires':time.time()+60,'digest':digest(step)}}
    store.state(tid,'awaiting_approval',checkpoint=cp)
    asyncio.run(svc.handle(message('/approve 1 ABCD')))
    task=store.rows('SELECT * FROM tasks')[0]
    assert task['state']=='queued' and json.loads(task['checkpoint'])['approval']['granted']
    store.state(tid,'awaiting_approval',checkpoint=cp)
    asyncio.run(svc.handle(message('/deny 1')));assert store.rows('SELECT state FROM tasks')[0]['state']=='cancelled'

def test_bridge_tasks_are_not_falsely_marked_cancelled(env):
    svc,store=env;tid=store.enqueue(123,'test','one');store.state(tid,'in_codex')
    asyncio.run(svc.handle(message('/cancel 1')))
    assert store.rows('SELECT state FROM tasks')[0]['state']=='in_codex'

def test_bridge_only_reads_public_agent_messages_and_exact_envelopes():
    turn={'items':[{'type':'reasoning','text':'private'},
        {'type':'agentMessage','phase':'analysis','text':'private'},
        {'type':'agentMessage','phase':'commentary','text':'public'},
        {'type':'agentMessage','phase':'final_answer','text':'answer'},
        {'type':'commandExecution','command':'secret'},
        {'type':'userMessage','content':[{'type':'text','text':'[Telegram task: tg-700]\nhello'}]}]}
    assert [i['text'] for i in public_messages(turn)]==['public','answer']
    assert task_markers(turn)==['tg-700']

def test_progress_spam_suppressed_across_multiple_codex_runs(env):
    svc,store=env;tid=store.enqueue(123,'test','one');store.state(tid,'running')
    for _ in range(20):
        svc.progress(tid,'command error','command_error',True)
        svc.progress(tid,'changed file','writing',True)
    svc.progress(tid,'develop','develop',True)
    svc.progress(tid,'packaging','packaging',True)
    assert len(store.rows('SELECT * FROM outbox'))==1

def test_all_command_families_reject_outsider(env):
    svc,store=env
    for command in ('/status','/selftest','/ask x','/goal x','/screenshot','/stop','/shutdown','/approve 1 x'):
        asyncio.run(svc.handle(message(command,999)))
    assert not store.rows('SELECT * FROM tasks') and not store.rows('SELECT * FROM outbox') and not svc.closing

def test_ambiguous_bridge_dispatch_is_not_replayed_after_crash(env):
    svc,store=env;tid=store.enqueue(123,'test','one')
    store.state(tid,'running',checkpoint={'route':'assistant','inflight':'bridge_queue'})
    store.recover()
    assert store.rows('SELECT state FROM tasks')[0]['state']=='interrupted'
    asyncio.run(svc.handle(message('/retry 1')))
    assert store.rows('SELECT state FROM tasks')[0]['state']=='interrupted'


def test_assistant_job_queues_in_chat_without_local_planner(env,monkeypatch):
    svc,store=env;asyncio.run(svc.handle(message('/ask Проверь связь')))
    tid=store.rows('SELECT id FROM tasks')[0]['id'];calls=[]
    async def enqueue(task_id,prompt):
        calls.append((task_id,prompt));return {'queue_id':'test-queue','thread':svc.bridge.thread}
    monkeypatch.setattr(svc.bridge,'enqueue',enqueue)
    asyncio.run(svc.run_task(store.rows('SELECT * FROM tasks')[0]))
    row=store.rows('SELECT * FROM tasks')[0];cp=json.loads(row['checkpoint'])
    assert calls==[(tid,'Проверь связь')]
    assert row['state']=='queued_in_codex' and cp['bridge']['queue_id']=='test-queue' and 'inflight' not in cp


def test_bridge_queue_failure_stays_interrupted_without_automatic_retry(env,monkeypatch):
    svc,store=env;asyncio.run(svc.handle(message('/ask Проверь связь')))
    async def enqueue(*args):raise RuntimeError('Lost queue acknowledgement')
    monkeypatch.setattr(svc.bridge,'enqueue',enqueue)
    asyncio.run(svc.run_task(store.rows('SELECT * FROM tasks')[0]))
    row=store.rows('SELECT * FROM tasks')[0]
    assert row['state']=='interrupted' and json.loads(row['checkpoint'])['inflight']=='bridge_queue'


def test_bridge_final_completes_exact_task_and_delivers_once(env,monkeypatch):
    svc,store=env;tid=store.enqueue(123,'check','tg-700')
    store.state(tid,'queued_in_codex');store.put('bridge_queue:'+tid,{'queue_id':'test'})
    store.put('bridge_initialized',True)
    turn={'id':'test-turn','items':[
        {'type':'userMessage','content':[{'type':'text','text':'[Telegram task: tg-700]\ncheck'}]},
        {'id':'final-test','type':'agentMessage','phase':'final_answer','text':'TG_LINK_OK'}]}
    async def turns(thread,anchor=None):return [turn]
    monkeypatch.setattr(svc.bridge.reader,'turns',turns)
    async def scan_twice():await svc.bridge.scan();await svc.bridge.scan()
    asyncio.run(scan_twice())
    row=store.rows('SELECT * FROM tasks')[0]
    assert row['state']=='completed' and row['result']=='TG_LINK_OK'
    assert len(store.rows('SELECT * FROM outbox'))==1
