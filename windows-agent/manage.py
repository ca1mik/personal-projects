from __future__ import annotations
import argparse, asyncio, csv, getpass, hashlib, json, os, secrets, sys, time, webbrowser
from pathlib import Path
from localagent.base import ROOT, DATA, Store, set_secret, get_secret, write_json, config

async def bot_info():
    from localagent.telegram import Telegram
    tg=Telegram()
    try:
        info=await tg.call('getMe')
        print(json.dumps({'id':info['id'],'username':info.get('username'),'name':info.get('first_name')},ensure_ascii=False))
        hook=await tg.call('getWebhookInfo')
        print('Webhook configured:',bool(hook.get('url')))
        return info
    finally: await tg.client.aclose()

def pairing():
    store=Store()
    if store.kv('owner'):
        print('Already paired to Telegram ID',store.kv('owner')); return
    code=secrets.token_urlsafe(12)
    store.put('pairing',{'hash':hashlib.sha256(code.encode()).hexdigest(),'expires':time.time()+3600})
    print('/pair '+code)
    print('Send this command in a PRIVATE conversation with your bot within 60 minutes. Do not share it.')

async def hh_login():
    from urllib.parse import urlencode,urlparse,parse_qs
    import httpx
    cid=get_secret('hh_client_id') or input('HH application client_id: ').strip()
    csecret=get_secret('hh_client_secret') or getpass.getpass('HH client_secret (hidden): ')
    redirect=config().get('hh_redirect_uri','http://127.0.0.1:8767/callback')
    state=secrets.token_urlsafe(24)
    from http.server import HTTPServer,BaseHTTPRequestHandler
    result={}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a): pass
        def do_GET(self):
            query=parse_qs(urlparse(self.path).query)
            if query.get('state')!=[state] or not query.get('code'):
                self.send_response(400); self.end_headers(); self.wfile.write(b'Invalid OAuth state'); return
            result['code']=query['code'][0]
            self.send_response(200);self.end_headers();self.wfile.write(b'Authorization received. Return to the local terminal.')
    server=HTTPServer(('127.0.0.1',8767),Handler); server.timeout=300
    url='https://hh.ru/oauth/authorize?'+urlencode({'response_type':'code','client_id':cid,'redirect_uri':redirect,'state':state})
    print('Opening official hh.ru authorization. Redirect URI must match your registered application:',redirect)
    webbrowser.open(url)
    try: await asyncio.to_thread(server.handle_request)
    finally: server.server_close()
    if not result.get('code'): raise RuntimeError('OAuth timed out')
    async with httpx.AsyncClient(timeout=30) as client:
        r=await client.post('https://api.hh.ru/token',data={'grant_type':'authorization_code','client_id':cid,'client_secret':csecret,'code':result['code'],'redirect_uri':redirect})
    if r.status_code!=200: raise RuntimeError('HH token exchange failed: HTTP '+str(r.status_code))
    obj=r.json()
    set_secret('hh_client_id',cid);set_secret('hh_client_secret',csecret)
    set_secret('hh_access',obj['access_token'])
    if obj.get('refresh_token'): set_secret('hh_refresh',obj['refresh_token'])
    Store().put('hh_token_expires',time.time()+obj.get('expires_in',0))
    Store().execute("UPDATE schedules SET enabled=1,next=? WHERE id='hh-search'",(time.time()+60,))
    print('HH credentials saved with Windows DPAPI.')

async def hh_search(query):
    from localagent.hh import HH
    obj=await HH(Store()).search(query)
    print(json.dumps(obj,ensure_ascii=False,indent=2))

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['secret','pair','bot-info','status','backup','hh-login','hh-search','hh-import','stop','resume'])
    parser.add_argument('value',nargs='?'); parser.add_argument('--stdin',action='store_true')
    args=parser.parse_args(); store=Store()
    if args.command=='secret':
        if not args.value: parser.error('Specify secret name, e.g. telegram')
        value=sys.stdin.read().strip() if args.stdin else getpass.getpass('Secret (hidden): ')
        if not value: raise ValueError('Empty secret')
        set_secret(args.value,value); print('Secret stored with Windows DPAPI.')
    elif args.command=='pair': pairing()
    elif args.command=='bot-info': asyncio.run(bot_info())
    elif args.command=='status':
        print(json.dumps({'health':__import__('localagent.base',fromlist=['read_json']).read_json(DATA/'health.json'),
            'owner':store.kv('owner'),'paused':store.kv('paused',False),
            'tasks':store.rows('SELECT id,state,updated FROM tasks ORDER BY created DESC LIMIT 15')},ensure_ascii=False,indent=2))
    elif args.command=='backup': print(store.backup())
    elif args.command=='hh-login': asyncio.run(hh_login())
    elif args.command=='hh-search': asyncio.run(hh_search(args.value or 'IT OR CRM OR автоматизация OR техническая поддержка'))
    elif args.command=='hh-import':
        from localagent.hh import HH
        p=Path(args.value)
        if p.suffix.lower()=='.csv':
            with p.open(encoding='utf-8-sig',newline='') as f: data=list(csv.DictReader(f))
        else:
            data=json.loads(p.read_text('utf-8-sig')); data=data.get('items',[]) if isinstance(data,dict) else data
        h=HH(store); h.import_history(data);print(json.dumps(h.statistics(),ensure_ascii=False,indent=2))
    elif args.command=='stop': (ROOT/'STOP').write_text('Local emergency stop','utf-8');store.put('paused',True); print('Emergency stop requested.')
    elif args.command=='resume': store.put('paused',False);print('Pause cleared. Run Start-Agent.ps1 to start a stopped service.')

if __name__=='__main__':
    try: main()
    except Exception as e:
        from localagent.base import redact
        print(redact(e),file=sys.stderr);sys.exit(1)
