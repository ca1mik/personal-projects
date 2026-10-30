import asyncio,json,time
from localagent.progress import ProgressEvents
from localagent.service import Service
from localagent.base import Store

def test_progress_never_forwards_reasoning_commands_or_stdout():
    output=[];clock=[0]
    progress=ProgressEvents(lambda *a:output.append(a),clock=lambda:clock[0])
    secret='1234567890:'+('S'*35)
    progress.event({'type':'item.completed','item':{'type':'reasoning','text':'private '+secret}})
    assert not output
    progress.event({'type':'item.started','item':{'id':'one','type':'command_execution','command':'python -m unittest discover '+secret}})
    progress.event({'type':'item.completed','item':{'id':'one','type':'command_execution','command':'python -m unittest discover','exit_code':0,'aggregated_output':'Ran 0 tests '+secret}})
    texts=' '.join(x[0] for x in output)
    assert secret not in texts and 'private' not in texts
    assert 'тестирования' in texts and 'тестов прошли' not in texts

def test_notifications_throttled_but_latest_stage_preserved():
    output=[];clock=[0]
    progress=ProgressEvents(lambda *a:output.append(a),clock=lambda:clock[0])
    progress.event({'type':'thread.started'})
    clock[0]=1
    progress.event({'type':'item.completed','item':{'id':'files','type':'file_change','changes':[{'path':'a.py'}]}})
    assert output[0][2] is True and output[1][2] is False
    assert output[1][1]=='writing'
    clock[0]=21
    progress.event({'type':'item.completed','item':{'id':'more','type':'file_change','changes':[{'path':'a.py'},{'path':'b.py'}]}})
    assert output[-1][2] is True and '2' in output[-1][0]

def test_progress_command_is_owner_only_and_uses_short_task_number(tmp_path):
    store=Store(tmp_path/'p.sqlite3');store.put('owner',123);store.put('owner_chat',123)
    svc=Service(store,object());tid=store.enqueue(123,'Разработка проекта','internal-id-9876');store.state(tid,'running')
    svc.progress(tid,'Запускаю команду тестирования.','testing',False)
    def msg(user):return {'update_id':1,'message':{'from':{'id':user},'chat':{'id':user,'type':'private'},'text':'/progress 1'}}
    asyncio.run(svc.handle(msg(999)))
    assert not store.rows('SELECT * FROM outbox')
    asyncio.run(svc.handle(msg(123)))
    text=json.loads(store.rows('SELECT payload FROM outbox')[0]['payload'])['text']
    assert '№1' in text and 'тестирования' in text and tid not in text

def test_heartbeat_does_not_claim_new_work_or_completion(tmp_path):
    store=Store(tmp_path/'p.sqlite3');svc=Service(store,object())
    tid=store.enqueue(123,'test','x');store.state(tid,'running')
    svc.progress(tid,'Команда работает','executing',False)
    first=store.kv('progress:'+tid)['last_action_at']
    svc.progress(tid,'Процесс работает, новых событий нет.','heartbeat',False)
    assert store.kv('progress:'+tid)['last_action_at']==first
    assert store.rows('SELECT state FROM tasks')[0]['state']=='running'
