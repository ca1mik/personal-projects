"""Explicit owner power commands; fixed executable/arguments, durable deduplication."""
from __future__ import annotations
import asyncio,hashlib,json,os,re,time
from pathlib import Path
from .base import redact

class Power:
    def __init__(self,service):
        self.svc=service;self.store=service.store;self.lock=asyncio.Lock()

    async def run(self,args):
        exe=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/shutdown.exe'
        proc=await asyncio.create_subprocess_exec(str(exe),*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,creationflags=0x08000000)
        try:out,err=await asyncio.wait_for(proc.communicate(),20)
        except asyncio.TimeoutError:
            proc.kill();await proc.wait();raise RuntimeError('Windows не вернула результат команды; проверь /power и /cancelshutdown.')
        return {'code':proc.returncode,'detail':redact((err or out).decode('utf-8','replace'))[:600]}

    async def send(self,chat,text):await self.svc.send(chat,text)

    async def probe(self):
        results=[]
        for flag in ('/s','/r'):
            start=await self.run([flag,'/t','600','/c','Telegram owner: test, cancelling immediately'])
            item={'action':flag,'schedule':start['code']};results.append(item)
            if start['code']!=0:
                raise RuntimeError('Windows отклонила тестовую команду: '+str(start['code'])+'. Чужое ожидающее выключение не отменяю.')
            abort=await self.run(['/a']);item['abort']=abort['code']
            if abort['code']!=0:raise RuntimeError('Не удалось отменить тест! Срочно выполни /cancelshutdown. Код '+str(abort['code']))
        return results

    async def panel(self,chat):
        pending=self.store.kv('pc_power_pending',{})
        active=pending and pending.get('due',0)>time.time()
        text='**Управление компьютером**\n\n'+(f'Запланировано: {pending["action"]}, осталось примерно {max(0,int(pending["due"]-time.time()))} сек.\n' if active else '')
        text+='Выключение и перезагрузка — через 60 секунд, отмена доступна до срабатывания. Несохранённые данные могут потеряться. После выключения бот недоступен; включение ПК через этого бота не настроено.'
        keys={'inline_keyboard':[[{'text':'⏻ Выключить · 60 с','callback_data':'power:shutdown'},{'text':'↻ Перезагрузить · 60 с','callback_data':'power:reboot'}],[{'text':'Отменить выключение','callback_data':'power:cancel'}]]}
        from .formatting import telegram_html
        await self.svc.tg.call('sendMessage',chat_id=chat,text=telegram_html(text),parse_mode='HTML',reply_markup=keys)

    async def handle(self,chat,text,uid):
        normalized=text.strip().lower().strip(' .!')
        aliases={'выключи компьютер':'/shutdown','выключи пк':'/shutdown','выключить компьютер':'/shutdown',
                 'перезагрузи компьютер':'/reboot','перезагрузи пк':'/reboot','перезагрузка компьютера':'/reboot',
                 'отмени выключение':'/cancelshutdown','отмени перезагрузку':'/cancelshutdown'}
        normalized=aliases.get(normalized,normalized)
        if normalized=='/power':await self.panel(chat);return True
        parts=normalized.split();command=parts[0].split('@')[0] if parts else ''
        if command not in ('/shutdown','/reboot','/restart','/cancelshutdown','/power_test'):return False
        seconds=60
        if command in ('/shutdown','/reboot','/restart') and len(parts)>1:
            if len(parts)!=2 or not re.fullmatch(r'\d{1,5}',parts[1]) or not 30<=int(parts[1])<=86400:
                await self.send(chat,'Укажи задержку от 30 до 86400 секунд. Например: /shutdown 60');return True
            seconds=int(parts[1])
        elif len(parts)!=1:
            await self.send(chat,'Эта команда не принимает аргументы. /power');return True
        key='power_request:'+hashlib.sha256(str(uid).encode()).hexdigest()[:24]
        async with self.lock:
            if self.store.kv(key):await self.send(chat,'Эта команда уже обработана. /power');return True
            self.store.put(key,{'command':command,'at':time.time(),'stage':'started'})
            try:
                if command=='/power_test':
                    # Finish cancelling even if the polling task is stopped during the test.
                    probe=asyncio.create_task(self.probe())
                    try:results=await asyncio.shield(probe)
                    except asyncio.CancelledError:
                        await probe;raise
                    self.store.put('pc_power_test',{'at':time.time(),'results':results})
                    await self.send(chat,'✅ Windows приняла команды выключения и перезагрузки. Обе немедленно отменены; компьютер продолжает работать. Полное выключение и повторную загрузку этот тест не проверяет.')
                elif command=='/cancelshutdown':
                    result=await self.run(['/a'])
                    if result['code'] in (0,1116):
                        self.store.put('pc_power_pending',None)
                        await self.send(chat,'✅ Выключение / перезагрузка отменены.' if result['code']==0 else 'Ожидающего выключения или перезагрузки нет.')
                    else:raise RuntimeError('Windows не отменила действие: код '+str(result['code'])+'. '+result['detail'])
                else:
                    action='выключение' if command=='/shutdown' else 'перезагрузка'
                    result=await self.run(['/s' if command=='/shutdown' else '/r','/t',str(seconds),'/c','Telegram owner: '+('shutdown' if command=='/shutdown' else 'restart')])
                    if result['code']!=0:raise RuntimeError('Windows отклонила команду: код '+str(result['code'])+'. '+result['detail'])
                    self.store.put('pc_power_pending',{'action':action,'due':time.time()+seconds})
                    await self.send(chat,f'⏻ Запланировано {action} компьютера через {seconds} сек.\n\nОтменить: /cancelshutdown\nНесохранённые данные могут потеряться. После выключения бот недоступен.')
                self.store.put(key,{'command':command,'at':time.time(),'stage':'done'})
                self.store.event(None,'pc_power',command)
            except Exception as e:
                self.store.put(key,{'command':command,'at':time.time(),'stage':'error'})
                self.store.event(None,'pc_power_error',redact(e))
                await self.send(chat,'Не получилось: '+redact(e))
        return True
