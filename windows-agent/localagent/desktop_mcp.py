"""Client for the installed official Codex app-tools MCP, using its public tool API."""
from __future__ import annotations
import asyncio, json, os, subprocess, time
from pathlib import Path


class DesktopUnavailable(RuntimeError):
    """Raised only before a message tool call can have been submitted."""


def desktop_runtime():
    home = Path(os.environ['USERPROFILE'])
    servers = list((home/'.codex/plugins/cache/openai-bundled/codex-app-tools').glob('*/server.mjs'))
    nodes = [Path(os.environ[k]) for k in ('CODEX_MCP_NODE_PATH','CODEX_BROWSER_USE_NODE_PATH') if os.environ.get(k)]
    local = Path(os.environ.get('LOCALAPPDATA', str(home/'AppData/Local')))
    nodes += sorted((local/'OpenAI/Codex/runtimes/cua_node').glob('*/bin/node.exe'), key=lambda p:p.stat().st_mtime, reverse=True)
    nodes.append(home/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    nodes = [p for p in nodes if p.is_file()]
    try:
        names = [name for name in os.listdir('\\\\.\\pipe') if name.startswith('codex-app-tools-')]
    except OSError as e:
        raise DesktopUnavailable('Не удалось обнаружить канал приложения Codex') from e
    pipes = ['\\\\.\\pipe\\'+name for name in names]
    preferred = os.environ.get('CODEX_APP_TOOLS_PIPE_PATH')
    if preferred in pipes:
        pipe = preferred
    elif len(pipes) == 1:
        pipe = pipes[0]
    else:
        raise DesktopUnavailable('Канал приложения Codex отсутствует или неоднозначен')
    if not servers or not nodes:
        raise DesktopUnavailable('Не найден установленный MCP приложения Codex или Node')
    return nodes[0], max(servers, key=lambda p:p.stat().st_mtime), pipe


class DesktopSender:
    def __init__(self):
        self.proc = None
        self.sequence = 0

    async def request(self, method, params, timeout=20):
        self.sequence += 1
        ident = self.sequence
        self.proc.stdin.write((json.dumps({'jsonrpc':'2.0','id':ident,'method':method,'params':params}, ensure_ascii=False)+'\n').encode('utf-8'))
        await self.proc.stdin.drain()
        async def response():
            while True:
                raw = await self.proc.stdout.readline()
                if not raw:
                    raise RuntimeError('Codex app-tools MCP disconnected')
                obj = json.loads(raw)
                if obj.get('id') != ident:
                    continue
                if 'error' in obj:
                    raise RuntimeError('Codex app-tools MCP: '+str(obj['error'].get('message','error')))
                return obj['result']
        return await asyncio.wait_for(response(), timeout)

    async def prepare(self):
        node, server, pipe = desktop_runtime()
        env = {k:v for k,v in os.environ.items() if not(k.startswith('CODEX_') or k in ('OPENAI_API_KEY','TELEGRAM_BOT_TOKEN','HH_ACCESS_TOKEN'))}
        env.update(CODEX_APP_TOOLS_PIPE_PATH=pipe, CODEX_APP_TOOLS_DEFERRED='0')
        self.proc = await asyncio.create_subprocess_exec(str(node),str(server),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,
            env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),limit=10*1024*1024)
        await self.request('initialize',{'protocolVersion':'2025-06-18','clientInfo':{'name':'personal-telegram-reasoning','version':'1.0.0'},'capabilities':{}})
        self.proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        await self.proc.stdin.drain()
        inventory = await self.request('tools/list',{})
        tool = next((t for t in inventory.get('tools',[]) if t.get('name')=='send_message_to_thread'),None)
        efforts = (tool or {}).get('inputSchema',{}).get('properties',{}).get('thinking',{}).get('enum',[])
        if not all(e in efforts for e in ('low','medium','high')):
            raise DesktopUnavailable('MCP приложения не поддерживает выбор глубины рассуждений')

    async def thread_busy(self, thread, task_id):
        result = await self.request('tools/call',{
            'name':'read_thread',
            'arguments':{'threadId':thread,'turnLimit':1,'includeOutputs':False,'maxOutputCharsPerItem':100},
            '_meta':{'codexThreadId':thread,'codexCallId':'telegram-idle-'+task_id},
        })
        if result.get('isError'):
            raise DesktopUnavailable('Не удалось проверить, свободен ли чат Codex')
        for item in result.get('content',[]):
            if item.get('type')!='text':continue
            try:data=json.loads(item.get('text','{}'))
            except ValueError:continue
            if data.get('thread',{}).get('id')!=thread:continue
            # Unlike a separate read-only app-server, the native app sees live turns.
            return (data['thread'].get('status',{}).get('type')=='active'
                    or any(t.get('status')=='inProgress' for t in data.get('turns',[])))
        raise DesktopUnavailable('Приложение не подтвердило состояние чата Codex')

    async def send(self, thread, prompt, effort, task_id, *, wait_idle=True):
        if effort not in ('low','medium','high'):
            raise ValueError('Unsupported Telegram reasoning effort')
        began = time.monotonic()
        try:
            try:
                await self.prepare()
                if wait_idle:
                    while await self.thread_busy(thread,task_id):
                        await asyncio.sleep(2)
            except (OSError, RuntimeError, asyncio.TimeoutError, ValueError) as e:
                raise DesktopUnavailable(str(e)) from e
            # After this call begins, never fall back/retry: delivery may be ambiguous.
            result = await self.request('tools/call',{
                'name':'send_message_to_thread',
                'arguments':{'threadId':thread,'prompt':prompt,'thinking':effort},
                '_meta':{'codexThreadId':thread,'codexCallId':'telegram-reasoning-'+task_id},
            },timeout=30)
            if result.get('isError'):
                raise RuntimeError('Приложение Codex отклонило передачу сообщения: '+str(result.get('content',[]))[:1000])
            confirmed = False
            for item in result.get('content',[]):
                if item.get('type') != 'text':
                    continue
                try:
                    confirmed = confirmed or json.loads(item.get('text','{}')).get('threadId') == thread
                except (ValueError, AttributeError):
                    pass
            if not confirmed:
                raise RuntimeError('Приложение не подтвердило адресата; автоматический повтор запрещён')
            return {'transport':'codex_app_tools','thread':thread,'reasoning_effort':effort,
                    'queued_at':time.time(),'dispatch_seconds':round(time.monotonic()-began,3)}
        finally:
            await self.close()

    async def close(self):
        if self.proc and self.proc.returncode is None:
            self.proc.stdin.close()
            try:
                await asyncio.wait_for(self.proc.wait(),3)
            except asyncio.TimeoutError:
                self.proc.kill()
                await self.proc.wait()
        self.proc = None
