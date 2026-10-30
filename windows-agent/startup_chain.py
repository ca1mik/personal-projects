"""Interactive-logon startup: Happ TUN readiness -> Codex desktop and bot supervisor."""
from __future__ import annotations
import argparse,json,os,subprocess,time,sys
from pathlib import Path
import httpx,psutil
from localagent.base import ROOT,DATA,config,write_json,redact

PS=str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe')

def vpn_active(snapshot):
    for adapter in snapshot.get('adapters',[]):
        routes=set(adapter.get('routes',[]))
        if adapter.get('up') and ('0.0.0.0/0' in routes or {'0.0.0.0/1','128.0.0.0/1'}<=routes):return True
    return False

def tunnel_snapshot():
    script="""$a=@(Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue | Where-Object {$_.InterfaceDescription -eq 'Happ Tunnel'} | ForEach-Object { @{up=($_.Status -eq 'Up');routes=@(Get-NetRoute -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty DestinationPrefix)} }); @{adapters=$a}|ConvertTo-Json -Depth 4 -Compress"""
    r=subprocess.run([PS,'-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode:raise RuntimeError('Cannot read Happ adapter state')
    return json.loads(r.stdout.decode('utf-8-sig','replace'))

def readiness():
    snapshot=tunnel_snapshot();active=vpn_active(snapshot);sites={}
    if active:
        with httpx.Client(timeout=12,follow_redirects=True,trust_env=False) as c:
            for name,url in (('telegram','https://api.telegram.org/'),('codex','https://chatgpt.com/')):
                try:
                    r=c.get(url);sites[name]=200<=r.status_code<500 and r.status_code not in (407,408,429)
                except httpx.HTTPError:sites[name]=False
    return {'vpn_active':active,'https_reachable':sites,'ready':active and all(sites.get(k) for k in ('telegram','codex'))}

def running_file(path):
    target=str(Path(path).resolve()).lower()
    for p in psutil.process_iter(['exe','cmdline']):
        try:
            if any(str(arg).lower()==target for arg in (p.info['cmdline'] or [])):return True
            if (p.info['exe'] or '').lower()==target:return True
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    return False

def desktop_executable(settings):
    # WindowsApps cannot always be enumerated by a limited scheduled task.
    # Ask the current user's package registration for the exact installed path.
    script="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-AppxPackage -Name OpenAI.Codex | Select-Object -ExpandProperty InstallLocation"
    try:
        result=subprocess.run([PS,'-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode==0:
            for location in result.stdout.decode('utf-8-sig','replace').splitlines():
                candidate=Path(location.strip())/'app/ChatGPT.exe'
                if candidate.is_file():return candidate
    except (OSError,subprocess.TimeoutExpired):pass
    configured=Path(settings['codex_exe'])
    if configured.is_file():return configured
    # Package upgrades change the versioned WindowsApps folder.
    try:candidates=sorted(Path(os.environ['ProgramFiles']).glob('WindowsApps/OpenAI.Codex_*/app/ChatGPT.exe'),key=lambda p:p.stat().st_mtime,reverse=True)
    except OSError:candidates=[]
    if not candidates:raise RuntimeError('Codex desktop executable was not found after an update')
    return candidates[0]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.check:
        result=readiness();print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['ready'] else 2
    import msvcrt
    lock=(DATA/'startup-chain.lock').open('a+b');lock.write(b'0');lock.flush();lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:return 0
    settings=config().get('startup_chain',{});began=time.time();child=None;last_connect=0;codex_error=None;check={}
    def state(stage,**extra):write_json(DATA/'startup-health.json',{'stage':stage,'ts':time.time(),'pid':os.getpid(),**extra})
    try:
        if settings.get('enabled'):
            happ=Path(settings['happ_exe'])
            if not happ.is_file():raise RuntimeError('Configured Happ executable was not found')
            if not running_file(happ):subprocess.Popen([str(happ),'--autostart'],creationflags=subprocess.CREATE_NO_WINDOW)
            while not(ROOT/'STOP').exists():
                try:check=readiness()
                except Exception as e:check={'ready':False,'vpn_active':False,'error':redact(e)[:200]}
                state('waiting_for_vpn',checks=check)
                if check['ready']:break
                if not check.get('vpn_active') and time.time()-last_connect>=30:
                    subprocess.Popen([str(happ),'happ://connect'],creationflags=subprocess.CREATE_NO_WINDOW);last_connect=time.time()
                if time.time()-began>settings.get('wait_seconds',600):raise TimeoutError('Happ tunnel or HTTPS readiness did not become available; apps not launched')
                for _ in range(8):
                    if (ROOT/'STOP').exists():return 0
                    time.sleep(1)
            if (ROOT/'STOP').exists():return 0
            try:
                codex=desktop_executable(settings)
                if not running_file(codex):subprocess.Popen([str(codex)],creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e:
                codex_error=redact(e)
                state('codex_unavailable',error=codex_error,checks=check)
                from localagent.base import Store
                store=Store();store.notify(store.kv('owner_chat'),'⚠️ Не удалось автоматически запустить Codex. Бот остаётся доступен для команд; открой Codex на ПК. Причина: '+codex_error[:300])
        if not running_file(ROOT/'supervisor.py'):
            child=subprocess.Popen([str(ROOT/'.venv/Scripts/pythonw.exe'),str(ROOT/'supervisor.py')],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
        state('degraded' if codex_error else 'ready',codex_requested=bool(settings.get('enabled')),supervisor_started=bool(child),checks=check,codex_error=codex_error)
        while not(ROOT/'STOP').exists():
            if child and child.poll() is not None:return child.returncode or 1
            time.sleep(1)
        if child:
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        state('stopped');return 0
    except Exception as e:
        state('failed',error=redact(e));return 2
    finally:lock.close()

if __name__=='__main__':sys.exit(main())
