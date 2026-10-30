"""Recovery and delivery guarantees for the same-chat Telegram bridge."""
import asyncio,json,sqlite3
from types import SimpleNamespace
import pytest
from localagent.base import Store
from localagent.app_bridge import AppBridge,AppReader,visible_answer


class TelegramStub:
    def __init__(self):self.calls=[]
    async def call(self,method,**payload):
        self.calls.append((method,payload));return {'message_id':42}


@pytest.fixture
def bridge(tmp_path):
    store=Store(tmp_path/'bridge.sqlite3');store.put('owner_chat',123)
    svc=SimpleNamespace(store=store,tg=TelegramStub(),progress=lambda *args:None)
    return AppBridge(svc)


def turn(text='done',phase='final_answer',ident='item1',task=None):
    items=[{'id':ident,'type':'agentMessage','phase':phase,'text':text}]
    if task:items.insert(0,{'type':'userMessage','content':[{'type':'text','text':f'[Telegram task: {task}]\ncheck'}]})
    return {'id':'turn1','items':items}


def attach_reader(bridge,monkeypatch,current):
    async def turns(thread,anchor=None):return current
    monkeypatch.setattr(bridge.reader,'turns',turns)

def test_heartbeat_notification_forwards_only_user_content(bridge):
    current=turn('Личная подборка: новость\n<heartbeat><automation_id>telegram</automation_id><decision>NOTIFY</decision><message>Готово</message></heartbeat>')
    bridge.finish(current,current['items'][-1])
    payload=json.loads(bridge.store.rows('SELECT payload FROM outbox')[0]['payload'])
    assert 'Личная подборка: новость' in payload['text'] and '<heartbeat>' not in payload['text']

def test_quiet_heartbeat_is_seen_once_without_telegram_output(bridge):
    current=turn('<heartbeat><automation_id>telegram</automation_id><decision>DONT_NOTIFY</decision><message>Нет новых событий</message></heartbeat>')
    bridge.finish(current,current['items'][-1]);bridge.finish(current,current['items'][-1])
    assert not bridge.store.rows('SELECT * FROM outbox')
    assert len(bridge.store.rows('SELECT * FROM bridge_seen'))==1

def test_heartbeat_with_only_notification_uses_message():
    assert visible_answer('<heartbeat><automation_id>telegram</automation_id><decision>NOTIFY</decision><message>Готова подборка</message></heartbeat>')=='Готова подборка'


def test_changed_text_with_same_id_updates_card_without_duplicates(bridge,monkeypatch):
    bridge.store.put('bridge_initialized',True)
    current=[turn('first',phase='commentary')];attach_reader(bridge,monkeypatch,current)
    asyncio.run(bridge.scan())
    current[0]['items'][0]['text']='updated text'
    bridge.store.execute('UPDATE bridge_cards SET updated=0')
    asyncio.run(bridge.scan());asyncio.run(bridge.scan())
    calls=bridge.service.tg.calls
    assert [c[0] for c in calls]==['sendMessage','editMessageText']
    assert 'updated text' in calls[-1][1]['text']


def test_throttled_change_is_retried_on_next_scan(bridge,monkeypatch):
    bridge.store.put('bridge_initialized',True)
    current=[turn('first',phase='commentary')];attach_reader(bridge,monkeypatch,current)
    asyncio.run(bridge.scan());current[0]['items'][0]['text']='second'
    asyncio.run(bridge.scan());assert len(bridge.service.tg.calls)==1
    bridge.store.execute('UPDATE bridge_cards SET updated=0')
    asyncio.run(bridge.scan());assert len(bridge.service.tg.calls)==2


def test_final_queue_and_completion_roll_back_together_on_write_failure(bridge):
    s=bridge.store;tid=s.enqueue(123,'check','tg-1');s.state(tid,'in_codex')
    s.put('bridge_queue:'+tid,{'queue_id':'q'})
    current=turn(task=tid);item=current['items'][-1]
    s.execute("CREATE TRIGGER fail_outbox BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT,'disk simulation'); END")
    with pytest.raises(sqlite3.IntegrityError):bridge.finish(current,item)
    assert not s.rows('SELECT * FROM bridge_seen') and not s.rows('SELECT * FROM outbox')
    assert s.rows('SELECT state FROM tasks')[0]['state']=='in_codex'
    s.execute('DROP TRIGGER fail_outbox')
    bridge.finish(current,item);bridge.finish(current,item)
    assert s.rows('SELECT state FROM tasks')[0]['state']=='completed'
    assert len(s.rows('SELECT * FROM outbox'))==1


def test_legacy_seen_rows_are_migrated_without_replaying_history(bridge,monkeypatch):
    s=bridge.store;s.put('bridge_initialized',True)
    s.execute('INSERT INTO bridge_seen(id,ts) VALUES(?,?)',('item1',1))
    attach_reader(bridge,monkeypatch,[turn()])
    asyncio.run(bridge.scan());asyncio.run(bridge.scan())
    assert s.rows('SELECT hash FROM bridge_seen')[0]['hash']
    assert not s.rows('SELECT * FROM outbox')


def test_first_connection_skips_old_history_but_completes_known_queued_task(bridge,monkeypatch):
    s=bridge.store;tid=s.enqueue(123,'check','tg-1');s.state(tid,'queued_in_codex')
    s.put('bridge_queue:'+tid,{'queue_id':'q'})
    new=turn(task=tid);old=turn('old secret',ident='old');old['id']='old-turn'
    attach_reader(bridge,monkeypatch,[new,old])
    asyncio.run(bridge.scan())
    rows=s.rows('SELECT payload FROM outbox')
    assert len(rows)==1 and 'old secret' not in rows[0]['payload']
    assert s.rows('SELECT state FROM tasks')[0]['state']=='completed'


def test_reader_catches_up_past_first_page_and_includes_anchor(monkeypatch):
    reader=AppReader();calls=[]
    async def start():pass
    async def request(method,params):
        calls.append(params)
        if 'cursor' not in params:return {'data':[{'id':str(n)} for n in range(10,5,-1)],'nextCursor':'older'}
        return {'data':[{'id':str(n)} for n in range(5,0,-1)],'nextCursor':'not-needed'}
    monkeypatch.setattr(reader,'start',start);monkeypatch.setattr(reader,'_request',request)
    result=asyncio.run(reader.turns('thread',anchor='3'))
    assert len(result)==10 and len(calls)==2 and calls[1]['cursor']=='older'


def test_reader_detects_repeated_cursor_instead_of_looping(monkeypatch):
    reader=AppReader()
    async def start():pass
    async def request(*args):return {'data':[{'id':'new'}],'nextCursor':'same'}
    monkeypatch.setattr(reader,'start',start);monkeypatch.setattr(reader,'_request',request)
    with pytest.raises(RuntimeError,match='repeated history cursor'):
        asyncio.run(reader.turns('thread',anchor='old'))
