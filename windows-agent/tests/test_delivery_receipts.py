import asyncio,json,time
from types import SimpleNamespace
from localagent.base import Store
from localagent.app_bridge import AppBridge
from localagent.service import Service


def test_bridge_delivery_survives_restart_and_retries(tmp_path):
    db=tmp_path/'state.sqlite3';s=Store(db)
    s.put('owner_chat',123);s.enqueue(123,'send result','tg-test')
    s.put('bridge_queue:tg-test',True)
    bridge=AppBridge(SimpleNamespace(store=s));bridge.thread='thread'
    item={'id':'answer','type':'agentMessage','phase':'final_answer','text':'Готово'}
    turn={'items':[{'type':'userMessage','content':[{'type':'text','text':'[Telegram task: tg-test]'}]},item]}
    bridge.finish(turn,item)
    row=s.rows('SELECT * FROM outbox')[0]
    assert '0/1' in s.delivery_status('tg-test')
    s.execute('UPDATE outbox SET attempts=1 WHERE id=?',(row['id'],))
    s=Store(db)
    assert 'повтор после ошибки' in s.delivery_status('tg-test')
    s.delivered(row['id'],[{'message_id':777}])
    s=Store(db)
    assert s.delivery_status('tg-test')=='Доставлено в Telegram: 1/1'
    receipt=s.rows('SELECT * FROM outbox')[0]
    assert receipt['sent_at'] and json.loads(receipt['receipt'])==[{'message_id':777}]
    bridge.finish(turn,item)
    assert len(s.rows('SELECT * FROM outbox'))==1


def test_local_mp4_is_native_video(tmp_path):
    s=Store(tmp_path/'state.sqlite3');svc=Service(s,object())
    clip=tmp_path/'clip.mp4';clip.write_bytes(b'\x00\x00\x00\x18ftypisom')
    svc.file(123,clip,caption='Подпись')
    assert s.rows('SELECT method FROM outbox')[0]['method']=='video'


def test_rating_failure_does_not_resend_acknowledged_video(tmp_path,monkeypatch):
    import localagent.service as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    s=Store(tmp_path/'state.sqlite3');sent=[]
    class Telegram:
        async def file(self,*args,**kwargs):
            sent.append(kwargs);return {'message_id':42}
    svc=Service(s,Telegram())
    svc.ui=SimpleNamespace(decorate=lambda *a:('post',{}),bind=lambda *a:(_ for _ in ()).throw(RuntimeError('rating failure')))
    s.execute('INSERT INTO outbox(chat,method,payload) VALUES(?,?,?)',(123,'video',json.dumps({'path':'clip.mp4'})))
    async def stop_after_pass(_):
        assert s.rows('SELECT sent FROM outbox')[0]['sent']==1
        (tmp_path/'STOP').write_text('test')
    monkeypatch.setattr(module.asyncio,'sleep',stop_after_pass)
    asyncio.run(svc.deliver())
    assert len(sent)==1 and sent[0]['video']
    row=s.rows('SELECT * FROM outbox')[0]
    assert row['attempts']==0 and json.loads(row['receipt'])['message_id']==42
    assert s.rows("SELECT * FROM events WHERE kind='delivery_ui_error'")
