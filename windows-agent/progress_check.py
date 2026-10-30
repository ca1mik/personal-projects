"""Real Codex JSONL -> persisted progress -> Telegram delivery check."""
import asyncio,json,time
from localagent.base import ROOT,Store,write_json
from localagent.service import Service

async def main():
    svc=Service();store=svc.store
    tid=store.enqueue(store.kv('owner_chat'),'Внутренняя проверка отображения хода работы Codex.','integration-progress-'+str(int(time.time())))
    store.state(tid,'running')
    svc.progress(tid,'Проверяю отображение действий Codex в реальном времени.','checking')
    project=ROOT/'projects'/tid
    try:
        result=await svc.codex.run(tid,'This is an observability acceptance check. Use no subagents. Create a UTF-8 file progress_fixture.txt with the text PROGRESS_FIXTURE_OK. Use a shell command to run Python that reads that file, asserts exact contents and prints PROGRESS_CHECK_OK. Actually execute the command; report its actual result in one Russian sentence. Do not access other files or external services.',project,write=True,timeout=300)
        events=store.rows("SELECT detail FROM events WHERE task=? AND kind='progress'",(tid,))
        assert len(events)>=3,'No observable progress events were captured'
        assert (project/'progress_fixture.txt').read_text('utf-8').strip()=='PROGRESS_FIXTURE_OK'
        store.state(tid,'completed',result)
        store.notify(store.kv('owner_chat'),'✅ **Проверка хода работы завершена**\n\nСобытия Codex получены во время работы и сохранены. Теперь доступны `/progress` и `/progress '+str(store.number(tid))+'`.')
        write_json(ROOT/'artifacts'/'progress-check.json',{'task':tid,'number':store.number(tid),'events':events,'result':result,'passed':True})
        print(json.dumps({'number':store.number(tid),'events':len(events),'result':result,'passed':True},ensure_ascii=False,indent=2))
    except Exception as e:
        store.state(tid,'failed',str(e));raise
    finally:await svc.tg.client.aclose()

if __name__=='__main__':asyncio.run(main())
