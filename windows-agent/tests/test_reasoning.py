import asyncio,json
from types import SimpleNamespace
import pytest
from localagent.base import Store
from localagent.reasoning import choose_effort
from localagent.desktop_mcp import DesktopSender,DesktopUnavailable
from localagent.app_bridge import AppBridge,task_markers,DEFAULT_THREAD


@pytest.mark.parametrize('text,expected',[
    ('Привет','low'),('Спасибо!','low'),('Как дела?','low'),
    ('Расскажи анекдот чтобы аж от смеха треснуть','low'),
    ('Открой Гугл','low'),('Сверни Доту','low'),
    ('Привет, важно: проверь резервную копию','high'),
    ('Отправь КП частным кондитерам','high'),
    ('Исправь ошибку в коде','high'),('Перезагрузи компьютер','high'),
    ('Не удаляй базу данных без проверки','high'),
    ('/goal Продолжай до готового результата','high'),
    ('Это ответственная задача','high'),
    ('Сравни два варианта оформления','medium'),
    ('А что думаешь об этом?','medium'),
    ('Привет '+('а'*250),'medium'),
])
def test_consequential_tasks_take_precedence_over_casual_prefix(text,expected):
    assert choose_effort(text)[0]==expected


def test_desktop_sender_uses_explicit_effort_without_changing_model(monkeypatch):
    sender=DesktopSender();calls=[]
    async def prepare():pass
    async def request(method,params,timeout):
        calls.append((method,params))
        return {'content':[{'type':'text','text':json.dumps({'threadId':'thread'})}]}
    monkeypatch.setattr(sender,'prepare',prepare);monkeypatch.setattr(sender,'request',request)
    result=asyncio.run(sender.send('thread','hello','low','tg-1',wait_idle=False))
    assert result['reasoning_effort']=='low'
    assert len(calls)==1
    args=calls[0][1]['arguments']
    assert args=={'threadId':'thread','prompt':'hello','thinking':'low'}
    assert 'model' not in args


def test_missing_runtime_is_safe_to_fall_back_before_submission(monkeypatch):
    sender=DesktopSender()
    async def prepare():raise OSError('app not running')
    monkeypatch.setattr(sender,'prepare',prepare)
    with pytest.raises(DesktopUnavailable):asyncio.run(sender.send('thread','hello','low','tg-1'))


@pytest.mark.parametrize('failure',['timeout','reject','unknown_confirmation'])
def test_ambiguous_delivery_never_becomes_safe_fallback(monkeypatch,failure):
    sender=DesktopSender();calls=[]
    async def prepare():pass
    async def request(*args,**kwargs):
        calls.append(1)
        if failure=='timeout':raise asyncio.TimeoutError()
        if failure=='reject':return {'isError':True,'content':[{'type':'text','text':'rejected'}]}
        return {'content':[{'type':'text','text':'unknown result'}]}
    monkeypatch.setattr(sender,'prepare',prepare);monkeypatch.setattr(sender,'request',request)
    with pytest.raises((RuntimeError,asyncio.TimeoutError)) as error:
        asyncio.run(sender.send('thread','hello','high','tg-1',wait_idle=False))
    assert not isinstance(error.value,DesktopUnavailable)
    assert len(calls)==1


def test_active_turn_is_not_interrupted_and_queued_effort_waits(monkeypatch):
    sender=DesktopSender();states=iter([True,False]);calls=[]
    async def prepare():pass
    async def busy(*args):
        value=next(states);calls.append(('busy',value));return value
    async def sleep(seconds):calls.append(('wait',seconds))
    async def request(*args,**kwargs):
        calls.append(('send',True))
        return {'content':[{'type':'text','text':'{"threadId":"thread"}'}]}
    monkeypatch.setattr(sender,'prepare',prepare)
    monkeypatch.setattr(sender,'thread_busy',busy)
    monkeypatch.setattr(sender,'request',request)
    monkeypatch.setattr(asyncio,'sleep',sleep)
    asyncio.run(sender.send('thread','hello','low','tg-1'))
    assert calls==[('busy',True),('wait',2),('busy',False),('send',True)]


def test_bridge_records_effort_and_does_not_repeat_accepted_message(tmp_path,monkeypatch):
    import localagent.app_bridge as module
    import localagent.desktop_mcp as desktop
    monkeypatch.setattr(module,'config',lambda:{'assistant_auto_reasoning':True})
    store=Store(tmp_path/'bridge.sqlite3');store.put('owner_chat',123)
    calls=[]
    class Sender:
        async def send(self,thread,prompt,effort,tid):
            calls.append((thread,prompt,effort,tid))
            return {'transport':'codex_app_tools','thread':thread,'reasoning_effort':effort}
    monkeypatch.setattr(desktop,'DesktopSender',Sender)
    bridge=AppBridge(SimpleNamespace(store=store))
    store.enqueue(123,'Отправь КП','tg-1')
    first=asyncio.run(bridge.enqueue('tg-1','Отправь КП'))
    second=asyncio.run(bridge.enqueue('tg-1','Отправь КП'))
    assert first==second and len(calls)==1 and calls[0][2]=='high'
    assert calls[0][1].startswith('[Telegram task: tg-1]')
    assert store.rows('SELECT state FROM tasks')[0]['state']=='queued_in_codex'
    assert store.rows("SELECT detail FROM events WHERE kind='reasoning_selected'")[0]['detail'].startswith('high:')


def test_native_app_delegation_binds_only_own_envelope():
    text=f'<codex_delegation>\n<source_thread_id>{DEFAULT_THREAD}</source_thread_id>\n<input>[Telegram task: tg-1]\nowner request with a < b & c</input>\n</codex_delegation>'
    item={'type':'functionCallOutput','namespace':'codex_app','name':'send_message_to_thread','output':{'text':text}}
    assert task_markers({'items':[item]})==['tg-1']
    assert task_markers({'items':[dict(item,namespace='other_server')]})==[]
    assert task_markers({'items':[dict(item,name='read_thread')]})==[]
    assert task_markers({'items':[item]},thread='another-thread')==[]


def test_native_delegation_final_completes_the_confirmed_task(tmp_path,monkeypatch):
    store=Store(tmp_path/'bridge.sqlite3');store.put('owner_chat',123)
    bridge=AppBridge(SimpleNamespace(store=store))
    tid=store.enqueue(123,'Привет','tg-1');store.state(tid,'queued_in_codex')
    store.put('bridge_queue:'+tid,{'transport':'codex_app_tools','reasoning_effort':'low'})
    wrapped=f'<codex_delegation><source_thread_id>{bridge.thread}</source_thread_id><input>[Telegram task: {tid}]\nПривет</input></codex_delegation>'
    final={'type':'agentMessage','phase':'final_answer','id':'answer','text':'Привет!'}
    current={'id':'turn','items':[{'type':'functionCallOutput','namespace':'codex_app','name':'send_message_to_thread','output':{'text':wrapped}},final]}
    bridge.finish(current,final);bridge.finish(current,final)
    assert store.rows('SELECT state FROM tasks')[0]['state']=='completed'
    assert len(store.rows('SELECT id FROM outbox'))==1
