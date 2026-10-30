from __future__ import annotations
import json, msvcrt, os, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)

def main():
    lock=(DATA/'supervisor.lock').open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError: return
    child=None; attempts=0
    try:
        (DATA/'supervisor.json').write_text(json.dumps({'pid':os.getpid(),'started':time.time()}),'utf-8')
        while not (ROOT/'STOP').exists():
            began=time.time()
            logfile=ROOT/'logs'/'service.log'
            if logfile.exists() and logfile.stat().st_size>10*1024*1024:
                logfile.replace(logfile.with_suffix('.previous.log'))
            env={k:v for k,v in os.environ.items() if not (k.startswith('CODEX_') or k in ('OPENAI_API_KEY','TELEGRAM_BOT_TOKEN','HH_ACCESS_TOKEN'))}
            env['PYTHONUTF8']='1'
            with (ROOT/'logs'/'service.log').open('ab') as log:
                child=subprocess.Popen([str(ROOT/'.venv'/'Scripts'/'python.exe'),'-X','utf8','-m','localagent.service'],cwd=ROOT,env=env,
                    stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
                (DATA/'child.json').write_text(json.dumps({'pid':child.pid,'started':time.time()}),'utf-8')
                while child.poll() is None:
                    if (ROOT/'STOP').exists():
                        # Let service cancel task trees and flush messages before force termination.
                        try: child.wait(timeout=12)
                        except subprocess.TimeoutExpired:
                            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                        return
                    health=DATA/'health.json'
                    if time.time()-began>120 and health.exists() and time.time()-health.stat().st_mtime>120:
                        subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                        break
                    time.sleep(2)
            attempts=0 if time.time()-began>120 else attempts+1
            # Back off to 60 seconds; keep retrying unless stopped by the owner.
            for _ in range(min(60,2**min(attempts,6))):
                if (ROOT/'STOP').exists(): return
                time.sleep(1)
    finally:
        lock.close()

if __name__=='__main__': main()
