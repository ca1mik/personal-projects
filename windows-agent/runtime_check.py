"""Checks cancellation and sandbox enforcement using harmless local fixtures."""
import asyncio,json,subprocess,time
from pathlib import Path
from localagent.base import ROOT,Store,write_json
from localagent.service import Service
from localagent.codex import Codex

async def main():
    work=ROOT.parents[1]/'work'
    db=work/('runtime-check-'+str(time.time_ns())+'.sqlite3')
    service=Service(Store(db),object())
    task=asyncio.create_task(service.tools.shell('cancel-test',{'script':'Start-Sleep -Seconds 30'}))
    service.active['cancel-test']=task
    await asyncio.sleep(1)
    proc=service.codex.processes['cancel-test']
    pid=proc.pid
    await service.stop_tasks()
    await asyncio.gather(task,return_exceptions=True)
    await proc.wait()
    assert proc.returncode is not None
    marker=work/'sandbox-marker.txt';marker.write_text('LOCAL_SANDBOX_TEST_MARKER','utf-8')
    profile='{check={filesystem={":root"="deny",":minimal"="read",":workspace_roots"={"."="read"}},network={enabled=false}}}'
    args=[Codex().executable(),'-c','windows.sandbox="mxc"','-c','permissions='+profile,'sandbox','--permission-profile','check','-C',str(ROOT/'projects'/'smoke-project'),'--','cmd.exe','/d','/c','type',str(marker)]
    result=await asyncio.to_thread(subprocess.run,args,capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
    out=(result.stdout+result.stderr).decode('cp866','replace')
    assert result.returncode!=0 and 'LOCAL_SANDBOX_TEST_MARKER' not in out
    report={'cancelled_shell_pid':pid,'cancelled_exit':proc.returncode,'cancel_passed':True,'sandbox_denied_exit':result.returncode,'sandbox_output':out,'sandbox_denied_marker':True}
    write_json(ROOT/'artifacts'/'runtime-check.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':asyncio.run(main())
