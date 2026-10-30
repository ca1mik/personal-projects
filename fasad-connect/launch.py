from pathlib import Path
import argparse,json,os,secrets,socket,subprocess,sys,time,urllib.request,webbrowser

ROOT=Path(__file__).resolve().parent


def config(demo,port):
    folder=Path(os.environ.get('FASAD_RUNTIME_ROOT',str(ROOT/'runtime')))/('demo' if demo else 'pilot')
    folder.mkdir(parents=True,exist_ok=True)
    configfile=folder/'config.json'
    if not configfile.exists():
        configfile.write_text(json.dumps({'jwt_secret':secrets.token_urlsafe(40),'channel_secret':secrets.token_urlsafe(40),'intake_secret':secrets.token_urlsafe(40)},indent=2),encoding='utf-8')
    settings=json.loads(configfile.read_text(encoding='utf-8'))
    env=os.environ.copy()
    env.update(PYTHONPATH=str(ROOT/'backend')+os.pathsep+str(ROOT),PYTHONIOENCODING='utf-8',
        DATABASE_URL='sqlite:///'+(folder/'fasad.sqlite').as_posix(),JWT_SECRET_KEY=settings['jwt_secret'],CHANNEL_SECRET_KEY=settings['channel_secret'],PUBLIC_INTAKE_SECRET=settings['intake_secret'],
        ENVIRONMENT='production',DEBUG='false',LICENSE_LOCK_ENABLED='false',BACKUP_MIRROR_PATH='',LOCAL_STORAGE_PATH=str(folder/'files'),
        FASAD_CONNECT_DATA=str(folder),FASAD_CONNECT_DEMO='1' if demo else '0',FASAD_BACKEND_PORT=str(port+5000),FASAD_FRONTEND_PORT=str(port+1),
        API_URL=f'http://127.0.0.1:{port+5000}/api/v1',NEXT_PUBLIC_API_URL='/api/v1',BACKEND_ORIGIN=f'http://127.0.0.1:{port+5000}',
        PORT=str(port+1),HOSTNAME='127.0.0.1',CORS_ORIGINS=f'http://127.0.0.1:{port},http://localhost:{port}',NO_PROXY='127.0.0.1,localhost')
    return folder,env


def ready(url):
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url,timeout=2) as r:return r.status==200
    except Exception:return False


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--demo',action='store_true');parser.add_argument('--port',type=int,default=3137);parser.add_argument('--stop',action='store_true');parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args();folder,env=config(args.demo,args.port)
    if args.stop:
        (folder/'stop.request').write_text('stop',encoding='utf-8');print('Запрошена остановка.');return
    locks=[]
    for port in (args.port,args.port+1,args.port+5000):
        sock=socket.socket()
        try:sock.bind(('127.0.0.1',port))
        except OSError:
            print(f'Порт {port} занят. Проверьте уже запущенную копию.');return 1
        locks.append(sock)
    for sock in locks:sock.close()
    stop=folder/'stop.request'
    if stop.exists():stop.unlink()
    logs=folder/'logs';logs.mkdir(exist_ok=True)
    print('Фасад Connect · '+('Демонстрация' if args.demo else 'Рабочее пространство'),flush=True)
    subprocess.run([sys.executable,'-m','connect.bootstrap'],cwd=ROOT,env=env,check=True)
    children=[];streams=[]
    def spawn(name,cmd):
        stream=(logs/(name+'.log')).open('ab');streams.append(stream)
        p=subprocess.Popen(cmd,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        children.append(p)
    try:
        spawn('backend',[sys.executable,'-m','uvicorn','connect.app:app','--host','127.0.0.1','--port',str(args.port+5000),'--no-access-log'])
        spawn('frontend',[str(ROOT/'node/node.exe'),str(ROOT/'frontend/server.js')])
        for _ in range(60):
            if ready(f'http://127.0.0.1:{args.port+5000}/health'):break
            if any(p.poll() is not None for p in children):raise RuntimeError('Сервис не запустился. Подробности в runtime/logs.')
            time.sleep(.5)
        else:raise RuntimeError('Сервер не ответил. Проверьте runtime/logs.')
        spawn('gateway',[sys.executable,'-m','uvicorn','connect.gateway:app','--host','127.0.0.1','--port',str(args.port),'--no-access-log'])
        url=f'http://127.0.0.1:{args.port}/connect'
        for _ in range(40):
            if ready(url):break
            time.sleep(.25)
        print('Открыть: '+url,flush=True)
        (folder/'session.json').write_text(json.dumps({'url':url,'port':args.port,'mode':'demo' if args.demo else 'pilot'}),encoding='utf-8')
        if not args.no_browser:webbrowser.open(url)
        while not stop.exists():
            if any(p.poll() is not None for p in children):raise RuntimeError('Один из сервисов остановился. Проверьте runtime/logs.')
            time.sleep(1)
    finally:
        for p in reversed(children):
            if p.poll() is None:p.terminate()
        for p in children:
            try:p.wait(timeout=8)
            except subprocess.TimeoutExpired:p.kill()
        for stream in streams:stream.close()
        if stop.exists():stop.unlink()
    return 0


if __name__=='__main__':raise SystemExit(main())
