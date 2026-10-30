from __future__ import annotations
import asyncio, hashlib, json, os, secrets, signal, time, uuid
from pathlib import Path
import jsonschema
from .base import ROOT, DATA, Store, config, digest, redact, write_json
from .codex import Codex, POLICY, SCHEMA
from .telegram import Telegram
from .tools import Tools
from .hh import HH
from .formatting import STATES,stats_report,tool_report,friendly_error
from .extensions import Extensions
from .app_bridge import AppBridge
from .personal import CONTENT,prompt_for,add_reminder,reminder_request,DEFAULT_TOPICS,MSK
from .experience import Experience
from .power import Power

HELP='''**Ваш помощник на ПК**

Пишите или отправляйте голосовое по-русски. Поручения поступают в связанный чат Codex; ход работы и ответ возвращаются сюда.

**Задачи и управление**
/status — состояние ПК и очереди
/tasks — последние задачи; /history — завершенные
/progress [НОМЕР] — что делает Codex и последний этап задачи
/sync — связь Telegram с этим чатом Codex
/ping — проверка связи
/selftest — проверка команд и компонентов
/ask ТЕКСТ — отправить поручение в этот чат Codex
/goal ТЕКСТ — передать цель в этот чат Codex
/local ТЕКСТ — отдельная локальная задача без этого чата
/news · /joke · /meme · /cute — новости, шутка, мем, милая картинка
/idea · /mail · /plan — идея стартапа, важная почта, план дня
/feed [on|off|status] — подборка сейчас / управление автолентой
/topics ТЕМЫ — интересы для ленты
/channel — канал и режим публикации через кнопку под черновиком
/remind 20м ТЕКСТ — напомнить; /reminders — список
/save ТЕКСТ · /saved — сохранить идею или заметку / посмотреть
/home — панель с кнопками
/memory · /remember ФАКТ · /forget ID — посмотреть, запомнить, забыть
/mode focus|leisure|quiet|normal — режим помощника
/cancel ID — отменить локальную задачу
/retry ID — продолжить после ошибки
/logs [ID] — последние события (секреты скрываются)
/screenshot — снимок рабочего стола
/windows — список окон
/hh [поисковый запрос] — вакансии от 80000, Нижний Новгород
/hhstats — статистика импортированной истории
/every МИНУТЫ поручение — повторяющаяся задача, минимум 5 минут
/schedules — расписания; /unschedule ID — отключить
/approve ID КОД — выполнить показанное действие
/deny ID — отклонить действие
/stop — пауза приёма поручений и отмена локальных задач
/resume — снять паузу
/power — кнопки управления компьютером
/shutdown [СЕК] — выключить ПК (по умолчанию через 60 сек)
/reboot [СЕК] — перезагрузить ПК
/cancelshutdown — отменить выключение / перезагрузку
/power_test — проверить команды Windows с немедленной отменой
/service_stop — остановить только сервис до локального запуска
Файлы и изображения принимаются как данные. Для резюме отправьте файл с подписью «Это мое резюме, создай профиль и версии без выдумок».
Голос преобразуется локально моделью Whisper; первая загрузка модели требует интернета.
В /local критические операции требуют согласия на конкретный шаг. Связанный чат использует свои разрешения Codex. Уже переданное туда поручение останавливается кнопкой Stop в приложении.
При выключенном ПК или без сети бот недоступен. GUI требует разблокированного рабочего стола.'''

class Service:
    def __init__(self,store=None,tg=None):
        self.store=store or Store(); self.tg=tg or Telegram()
        self.codex=Codex(self.progress); self.tools=Tools(self.store,self.codex,self.tg); self.hh=HH(self.store)
        self.active={}; self.closing=False
        self.critical={'shell','gui','hh_apply','hh_reply','memory','bridge_queue'}
        self.extensions=Extensions()
        self.critical.update(self.extensions.handlers)
        self.schema=json.loads(json.dumps(SCHEMA))
        self.schema['properties']['kind']['enum'].extend(self.extensions.handlers)
        self.bridge=AppBridge(self)
        self.power=Power(self)
        self.ui=Experience(self)
    def owner(self): return self.store.kv('owner')
    def progress(self,tid,text,phase='working',announce=True):
        rows=self.store.rows('SELECT chat,state FROM tasks WHERE id=?',(tid,))
        if not rows or rows[0]['state'] not in ('running','queued','awaiting_approval','queued_in_codex','in_codex'):return
        previous=self.store.kv('progress:'+tid,{})
        value={'text':redact(text)[:500],'phase':phase,'at':time.time(),
            'last_action_at':previous.get('last_action_at',time.time()) if phase=='heartbeat' else time.time()}
        self.store.put('progress:'+tid,value)
        self.store.event(tid,'progress',value['text'])
        # Only milestones for standalone local jobs; persisted status remains available via /progress.
        notice_key='progress_notice:'+tid
        if announce and phase in ('develop','packaging','delivery','heartbeat') and time.time()-self.store.kv(notice_key,0)>=120:
            self.store.notify(rows[0]['chat'],f'⚙️ **Задача №{self.store.number(tid)}**\n\n{value["text"]}')
            self.store.put(notice_key,time.time())
    async def send(self,chat,text): self.store.notify(chat,text)
    def file(self,chat,path,photo=False,caption=''):
        from .app_bridge import artifact_method
        method=artifact_method(Path(path)) if photo or Path(path).suffix.lower() in ('.mp4','.m4v') else 'file'
        self.store.execute('INSERT INTO outbox(chat,method,payload) VALUES(?,?,?)',
            (chat,method,json.dumps({'path':str(path),'caption':redact(caption)},ensure_ascii=False)))
    async def stop_tasks(self):
        self.store.put('paused',True)
        self.store.execute("UPDATE tasks SET state='cancelled',updated=? WHERE state IN ('queued','running','awaiting_approval')",(time.time(),))
        for tid,task in list(self.active.items()):
            self.codex.kill(tid); task.cancel()
    async def handle(self,update):
        if await self.ui.handle(update):return
        msg=update.get('message')
        if not msg or msg.get('chat',{}).get('type')!='private' or msg.get('from',{}).get('is_bot'): return
        user=msg.get('from',{}).get('id'); chat=msg['chat']['id']
        text=msg.get('text','').strip(); owner=self.owner()
        if not owner:
            pair=self.store.kv('pairing') or {}
            supplied=text.split(maxsplit=1)[1] if text.startswith('/pair ') else ''
            valid=supplied and time.time()<pair.get('expires',0) and secrets.compare_digest(hashlib.sha256(supplied.encode()).hexdigest(),pair.get('hash',''))
            if valid:
                with self.store.db() as c:
                    c.execute('BEGIN IMMEDIATE')
                    exists=c.execute("SELECT value FROM kv WHERE key='owner'").fetchone()
                    if exists: return
                    c.execute('INSERT INTO kv VALUES(?,?)',('owner',json.dumps(user)))
                    c.execute('DELETE FROM kv WHERE key=?',('pairing',))
                self.store.put('owner_chat',chat)
                self.store.event(None,'paired',f'Owner Telegram ID {user}')
                await self.send(chat,'✅ **Аккаунт привязан**\n\nТеперь бот принимает команды только от вас.\n\n'+HELP)
                self.default_schedules(chat)
            return
        if user!=owner or chat!=self.store.kv('owner_chat'): return
        command=text.split(maxsplit=1)[0].split('@')[0] if text.startswith('/') else ''
        rest=text.split(maxsplit=1)[1] if ' ' in text else ''
        uid=update.get('update_id',msg.get('message_id'))
        tid='tg-'+str(uid)
        if command in ('/start','/help'):
            await self.send(chat,HELP)
        elif command=='/ping':
            await self.send(chat,'🏓 На связи. Сообщение получено, ответ отправлен.')
        elif command in ('/sync','/bridge'):
            health=self.store.kv('bridge_health',{})
            good=health.get('ok') and time.time()-health.get('checked_at',0)<30
            queued=self.store.rows("SELECT COUNT(*) AS n FROM tasks WHERE state='queued_in_codex'")[0]['n']
            await self.send(chat,'**Telegram ↔ Codex**\n\nЧат: Создать автономного AI-агента для ПК\n'+
                ('🟢 Ответы читаются из чата.' if good else '⏳ Проверяется чтение ответов: '+health.get('error','подключение'))+
                f'\nОжидают обработки в Codex: {queued}\n\nОбычные сообщения и /ask отправляются в этот чат. Если он занят, сообщение ждёт в очереди. Приложение Codex должно оставаться открытым.')
        elif command=='/selftest':
            self.store.enqueue(chat,'Проверка всех команд и компонентов',tid)
            self.store.state(tid,'queued',checkpoint={'direct':True,'step':{'kind':'diagnostics','summary':'Проверка бота','arguments':'{}'},'observations':[],'n':0})
            await self.send(chat,f'🔎 Проверяю команды и компоненты. Задача №{self.store.number(tid)}.')
        elif command in ('/ask','/goal','/local'):
            if self.store.kv('paused',False):await self.send(chat,'Агент на паузе. /resume');return
            prompt=text if command=='/goal' else rest
            if not rest:await self.send(chat,'Добавьте текст поручения после команды.');return
            self.store.enqueue(chat,prompt,tid)
            self.store.state(tid,'queued',checkpoint={'route':'local' if command=='/local' else 'assistant'})
            await self.send(chat,f'⏳ **Задача №{self.store.number(tid)}**\n'+('Передам в связанный чат Codex.' if command!='/local' else 'Выполню отдельной локальной задачей.'))
        elif command=='/feed' and rest.lower() in ('on','off','status','вкл','выкл'):
            if rest.lower()!='status':self.store.put('personal_feed_enabled',rest.lower() in ('on','вкл'))
            enabled=self.store.kv('personal_feed_enabled',True)
            await self.send(chat,('🟢 Личная лента включена.' if enabled else '⏸ Личная лента выключена.')+'\nРасписание: каждый час с 09:30 до 21:30 МСК. Новости со снимками из источников, когда доступны.\nТемы: '+self.store.kv('personal_topics',DEFAULT_TOPICS)+'\nРазовая подборка: /feed · Интересы: /topics ТЕМЫ')
        elif command in CONTENT:
            if self.store.kv('paused',False):await self.send(chat,'Агент на паузе. /resume');return
            self.store.enqueue(chat,prompt_for(command,rest,self.store),tid)
            self.store.state(tid,'queued',checkpoint={'route':'assistant','personal_kind':command[1:]})
            await self.send(chat,f'⏳ Задача №{self.store.number(tid)}: готовлю ответ в связанном чате Codex.')
        elif command=='/topics':
            if rest:
                if len(rest)>500:await self.send(chat,'Перечисли темы короче 500 символов.');return
                self.store.put('personal_topics',redact(rest))
            await self.send(chat,'Темы личной ленты: '+self.store.kv('personal_topics',DEFAULT_TOPICS))
        elif command=='/remind':
            try:await self.send(chat,add_reminder(self.store,chat,rest,request_id=tid))
            except ValueError as e:await self.send(chat,str(e))
        elif command=='/reminders':
            from datetime import datetime
            rows=self.store.rows("SELECT id,prompt,next FROM schedules WHERE enabled=1 AND prompt LIKE '[REMINDER] %' ORDER BY next LIMIT 20")
            await self.send(chat,'**Напоминания**\n\n'+('\n\n'.join(datetime.fromtimestamp(r['next'],MSK).strftime('%d.%m %H:%M МСК')+' · '+r['prompt'][len('[REMINDER] '):]+f'\n/unschedule {r["id"]}' for r in rows) or 'Напоминаний пока нет. Пример: /remind 20м размяться.'))
        elif command in ('/save','/saved'):
            notes=self.store.kv('personal_saved',[])
            if command=='/save':
                if not rest or len(rest)>4000:await self.send(chat,'После /save напиши заметку до 4000 символов.');return
                notes.append({'text':redact(rest),'at':time.time()});self.store.put('personal_saved',notes[-200:])
                await self.send(chat,'💡 Сохранено. Посмотреть: /saved')
            else:await self.send(chat,'**Сохранённое**\n\n'+('\n\n'.join(f'{i+1}. '+n['text'] for i,n in enumerate(notes[-10:])) or 'Пока пусто. /save ТЕКСТ'))
        elif command=='/status':
            import psutil
            counts=self.store.rows('SELECT state,COUNT(*) AS n FROM tasks GROUP BY state')
            lines=['**Состояние помощника**','', '⏸ На паузе' if self.store.kv('paused',False) else '🟢 Работает',
                f'Загрузка процессора: {psutil.cpu_percent():.0f}%',f'Занято памяти: {psutil.virtual_memory().percent:.0f}%','']
            lines += [f'{STATES.get(r["state"],r["state"])}: {r["n"]}' for r in counts]
            for row in self.store.rows("SELECT id FROM tasks WHERE state IN ('running','in_codex') ORDER BY created LIMIT 2"):
                p=self.store.kv('progress:'+row['id'],{})
                if p:lines+=['',f'№{self.store.number(row["id"])}: '+p['text']]
            await self.send(chat,'\n'.join(lines))
        elif command=='/progress':
            if rest:
                rows=self.store.rows('SELECT * FROM tasks WHERE id=?',(self.store.resolve(rest),))
            else:
                rows=self.store.rows("SELECT * FROM tasks ORDER BY CASE WHEN state IN ('running','in_codex') THEN 0 WHEN state IN ('awaiting_approval','queued_in_codex') THEN 1 ELSE 2 END,created DESC LIMIT 1")
            if not rows:await self.send(chat,'Задача не найдена. Список: /tasks');return
            task=rows[0];p=self.store.kv('progress:'+task['id'],{})
            lines=[f'**Задача №{self.store.number(task["id"])}**',STATES.get(task['state'],task['state']),'',task['prompt'][:240]]
            delivery=self.store.delivery_status(task['id'])
            if delivery:lines+=['',delivery]
            if p:
                from datetime import datetime,timedelta,timezone
                timestamp=datetime.fromtimestamp(p['at'],timezone(timedelta(hours=3))).strftime('%H:%M:%S')
                lines+=['',f'**Последний этап · {timestamp} МСК**',p['text']]
            if task['state']=='completed':lines+=['','**Результат**',task['result'][:1200]]
            elif task['state']=='failed':lines+=['',friendly_error(task['result'])]
            elif task['state'] in ('queued_in_codex','in_codex'):lines+=['','Передано в Codex. Остановка — кнопкой Stop в приложении Codex.']
            else:lines+=['',f'Остановить: `/cancel {self.store.number(task["id"])}`']
            await self.send(chat,'\n'.join(lines))
        elif command in ('/tasks','/history'):
            where="WHERE state IN ('completed','failed','cancelled','interrupted')" if command=='/history' else ''
            rows=self.store.rows(f'SELECT rowid AS number,id,state,prompt FROM tasks {where} ORDER BY created DESC LIMIT 15')
            await self.send(chat,'**Ваши задачи**\n\n'+('\n\n'.join(f'**№{r["number"]} · {STATES.get(r["state"],r["state"])}**\n{r["prompt"][:140]}'+('\n'+self.store.delivery_status(r['id']) if self.store.delivery_status(r['id']) else '') for r in rows) or 'Задач пока нет.'))
        elif command=='/stop':
            await self.stop_tasks(); await self.send(chat,'Локальные задачи остановлены, новые поручения на паузе. /resume — продолжить. Уже переданное в чат Codex выполнение останавливается кнопкой «Остановить» в приложении.')
        elif command=='/service_stop':
            await self.stop_tasks(); (ROOT/'STOP').write_text('Owner requested shutdown','utf-8')
            await self.send(chat,'Сервис останавливается. Запуск: Start-Agent.ps1 на ПК.')
            self.closing=True
        elif command=='/resume':
            self.store.put('paused',False); await self.send(chat,'Пауза снята. Отмененные задачи сами не возобновляются.')
        elif command=='/cancel':
            rest=self.store.resolve(rest)
            existing=self.store.rows('SELECT state FROM tasks WHERE id=?',(rest,))
            if existing and existing[0]['state'] in ('queued_in_codex','in_codex'):
                await self.send(chat,'Задача уже передана в чат Codex. Для немедленной остановки используйте «Остановить» в приложении. Скрывать работающую задачу как отменённую не буду.');return
            if self.store.rows('SELECT id FROM tasks WHERE id=?',(rest,)):
                self.store.state(rest,'cancelled'); self.codex.kill(rest)
                if rest in self.active: self.active[rest].cancel()
                await self.send(chat,f'⏹ Задача №{self.store.number(rest)} отменена.')
            else: await self.send(chat,'Задача не найдена.')
        elif command=='/retry':
            rest=self.store.resolve(rest)
            rows=self.store.rows('SELECT * FROM tasks WHERE id=?',(rest,))
            if rows and rows[0]['state'] in ('failed','interrupted'):
                cp=json.loads(rows[0]['checkpoint'])
                if cp.get('inflight') in self.critical:
                    await self.send(chat,'Исход внешнего действия неизвестен. Сначала проверьте его результат; повторное поручение оформите новым сообщением.')
                else:
                    self.store.state(rest,'queued'); await self.send(chat,f'Продолжу задачу №{self.store.number(rest)}.')
            else: await self.send(chat,'Повтор доступен для failed/interrupted задач.')
        elif command=='/logs':
            if rest:rest=self.store.resolve(rest)
            rows=self.store.rows('SELECT ts,task,kind,detail FROM events '+('WHERE task=? ' if rest else '')+'ORDER BY id DESC LIMIT 12',(rest,) if rest else ())
            names={'startup':'Сервис запущен','paired':'Аккаунт привязан','tool_start':'Начало действия','tool_result':'Действие завершено','error':'Ошибка','poll_error':'Ошибка связи','owner_approval':'Вы дали согласие','attachment':'Получен файл','progress':'Ход работы'}
            await self.send(chat,'**Последние события**\n\n'+('\n'.join(f'• '+(f'№{self.store.number(r["task"])} · ' if r['task'] else '')+names.get(r['kind'],r['kind'])+((': '+r['detail'][:180]) if r['kind'] in ('error','poll_error','progress') else '') for r in rows) or 'Событий нет.'))
        elif command=='/schedules':
            rows=self.store.rows('SELECT * FROM schedules')
            await self.send(chat,'**Расписания**\n\n'+('\n\n'.join(f'{"🟢" if r["enabled"] else "⏸"} {r["id"]}\n'+({'[HH_DAILY]':'Ежедневная статистика hh.ru, 19:00 МСК','[HH_SEARCH]':'Проверка новых вакансий каждые 6 часов'}.get(r['prompt'],r['prompt'])) for r in rows) or 'Расписаний нет.'))
        elif command=='/unschedule':
            self.store.execute('UPDATE schedules SET enabled=0 WHERE id=?',(rest,)); await self.send(chat,'Расписание отключено: '+rest)
        elif command=='/every':
            try:
                minutes,prompt=rest.split(maxsplit=1); interval=float(minutes)*60
                if interval<300 or interval>365*86400: raise ValueError()
                sid=secrets.token_hex(3)
                self.store.execute('INSERT INTO schedules VALUES(?,?,?,?,?,1)',(sid,chat,prompt,interval,time.time()+interval))
                await self.send(chat,f'Расписание {sid}: каждые {minutes} минут. Отключение /unschedule {sid}')
            except ValueError: await self.send(chat,'Формат: /every 60 проверить новые вакансии. Минимум 5 минут.')
        elif command in ('/approve','/deny'):
            parts=rest.split(); ident=self.store.resolve(parts[0]) if parts else ''
            rows=self.store.rows("SELECT * FROM tasks WHERE id=? AND state='awaiting_approval'",(ident,))
            if not rows: await self.send(chat,'Ожидающий запрос не найден.'); return
            cp=json.loads(rows[0]['checkpoint']); auth=cp.get('approval',{})
            if command=='/deny':
                self.store.state(ident,'cancelled','Owner denied action'); await self.send(chat,'Действие отклонено.'); return
            if self.store.kv('paused',False):
                await self.send(chat,'Сначала снимите аварийную паузу: /resume.'); return
            if len(parts)!=2 or time.time()>auth.get('expires',0) or not secrets.compare_digest(parts[1],auth.get('code','')) or digest(cp.get('step'))!=auth.get('digest'):
                await self.send(chat,'Код неверен, истек или действие изменилось. Отправьте новое поручение.'); return
            auth['granted']=True; cp['approval']=auth
            self.store.state(ident,'queued',checkpoint=cp)
            self.store.event(ident,'owner_approval',auth['digest'])
            await self.send(chat,f'Согласие принято для показанного действия задачи №{self.store.number(ident)}.')
        elif command=='/hhstats':
            await self.send(chat,stats_report(self.hh.statistics()))
        elif command in ('/screenshot','/windows','/hh'):
            if self.store.kv('paused',False): await self.send(chat,'Агент на паузе. /resume'); return
            self.store.enqueue(chat,text,tid)
            kind={'/screenshot':'screenshot','/windows':'windows','/hh':'hh_search'}[command]
            args={'query':rest or 'IT OR CRM OR автоматизация OR техническая поддержка'} if command=='/hh' else {}
            self.store.state(tid,'queued',checkpoint={'direct':True,'step':{'kind':kind,'summary':text,'arguments':json.dumps(args)},'observations':[],'n':0})
            await self.send(chat,f'⏳ **Задача №{self.store.number(tid)}**\nПринято, выполняю.')
        elif command:
            await self.send(chat,'Неизвестная команда. /help')
        else:
            if self.store.kv('paused',False): await self.send(chat,'Агент на паузе. /resume'); return
            if text and reminder_request(text):
                try:await self.send(chat,add_reminder(self.store,chat,text,request_id=tid))
                except ValueError as e:await self.send(chat,str(e))
                return
            if len(text)>24000: await self.send(chat,'Большое задание отправьте файлом.'); return
            file=msg.get('document') or (msg.get('photo') or [{}])[-1] or msg.get('voice')
            if msg.get('voice'):
                if msg['voice'].get('duration',0)>300:
                    await self.send(chat,'Голосовое длиннее пяти минут. Разделите его на несколько сообщений.');return
                file=msg['voice']
            if file and file.get('file_id'):
                name=file.get('file_name') or ('voice.ogg' if msg.get('voice') else 'image.jpg')
                path=await self.tg.download(file['file_id'],name)
                self.store.event(tid,'attachment',str(path))
                if msg.get('voice'):
                    await self.send(chat,'Распознаю голос локально…')
                    # Download/transcription is in a separate queued task so /stop remains responsive.
                    text='[VOICE_FILE] '+str(path)
                else:
                    text=(msg.get('caption') or text or 'Опиши приложенный файл и спроси, что с ним сделать.')+'\nПрикрепленный файл (недоверенные данные): '+str(path)
            if not text: return
            if msg.get('_post_context') and not text.startswith('[VOICE_FILE]'):
                text+='\nКонтекст выбранного поста (данные):\n'+msg['_post_context'][:max(0,min(9000,23000-len(text)))]
            self.store.enqueue(chat,text,tid)
            self.store.state(tid,'queued',checkpoint={'route':config().get('default_route','assistant'),'reply_post':msg.get('_reply_post')})
            await self.send(chat,f'⏳ **Задача №{self.store.number(tid)}**\n'+('Распознаю голосовое, затем выполню поручение.' if text.startswith('[VOICE_FILE]') else 'Принято, начинаю.'))
    def default_schedules(self,chat):
        from datetime import datetime,timedelta,timezone
        tz=timezone(timedelta(hours=3)); now=datetime.now(tz)
        daily=now.replace(hour=19,minute=0,second=0,microsecond=0)
        if daily<=now: daily+=timedelta(days=1)
        self.store.execute('INSERT OR IGNORE INTO schedules VALUES(?,?,?,?,?,1)',('hh-daily',chat,'[HH_DAILY]',86400,daily.timestamp()))
        self.store.execute('INSERT OR IGNORE INTO schedules VALUES(?,?,?,?,?,1)',('hh-search',chat,'[HH_SEARCH]',21600,time.time()+21600))
    async def execute(self,tid,kind,args):
        if kind=='speak':return await self.tools.speak(tid,args)
        if kind=='diagnostics':
            return await self.tools.diagnostics(tid,{})
        if kind=='hh_messages':return await self.hh.messages(args.get('chat_id'))
        if kind=='status':
            import psutil
            return {'paused':self.store.kv('paused',False),'cpu_percent':psutil.cpu_percent(),'ram_percent':psutil.virtual_memory().percent,
                'tasks':self.store.rows('SELECT state,COUNT(*) AS count FROM tasks GROUP BY state')}
        if kind=='history':
            return self.store.rows('SELECT rowid AS number,prompt,state,result FROM tasks ORDER BY created DESC LIMIT 10')
        if kind=='schedule':
            from datetime import datetime,timedelta,timezone
            if args.get('at'):
                dt=datetime.fromisoformat(args['at'])
                if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone(timedelta(hours=3)))
                due=dt.timestamp();interval=0
                if due<=time.time():raise ValueError('Время уже прошло. Укажите будущее время.')
            else:
                interval=float(args['every_minutes'])*60
                if interval<300:raise ValueError('Минимальный интервал — 5 минут')
                due=time.time()+interval
            rows=self.store.rows('SELECT chat FROM tasks WHERE id=?',(tid,))
            sid=secrets.token_hex(3)
            self.store.execute('INSERT INTO schedules VALUES(?,?,?,?,?,1)',(sid,rows[0]['chat'],redact(args['prompt']),interval,due))
            return {'scheduled':sid,'next_moscow':datetime.fromtimestamp(due,timezone(timedelta(hours=3))).isoformat(),
                'cancel_command':'/unschedule '+sid}
        if kind in self.extensions.handlers:
            return await self.extensions.execute(kind,tid,args,{'store':self.store,'root':ROOT})
        if kind=='hh_resume':
            from .resume import import_resume
            return await import_resume(self.store,self.codex,tid,args['path'])
        if kind=='hh_search': return await self.hh.search(args.get('query') or 'IT OR CRM OR автоматизация OR техническая поддержка')
        if kind=='hh_history': return await self.hh.history()
        if kind=='hh_apply': return await self.hh.apply(**args)
        if kind=='hh_reply': return await self.hh.reply(args['negotiation_id'],args['text'],str(uuid.uuid5(uuid.NAMESPACE_URL,tid+digest(args))))
        if kind not in ('develop','screenshot','windows','launch','gui','browser','shell','memory'): raise ValueError('Unknown tool')
        return await getattr(self.tools,kind)(tid,args)
    async def run_task(self,task):
        tid,chat=task['id'],task['chat']; cp=json.loads(task['checkpoint'])
        try:
            if task['prompt']=='[HH_DAILY]':
                await self.send(chat,stats_report(self.hh.statistics()))
                self.store.backup(); self.store.state(tid,'completed','Daily statistics delivered'); return
            if task['prompt']=='[HH_SEARCH]':
                result=await self.hh.search()
                new=[v for v in result['selected'] if v['new']]
                if new:
                    await self.send(chat,f'Новых вакансий: {len(new)}\n'+'\n'.join(v['title']+' '+v['url'] for v in new[:8]))
                    self.file(chat,result['artifact'])
                self.store.state(tid,'completed',json.dumps(result,ensure_ascii=False)); return
            label=f'№{self.store.number(tid)}'
            prompt=task['prompt']
            self.progress(tid,'Разбираю поручение и выбираю следующий шаг.','planning',False)
            if prompt.startswith('[VOICE_FILE] '):
                prompt=await self.tools.transcribe(prompt[len('[VOICE_FILE] '):],tid)
                if not prompt: raise ValueError('Речь не распознана; повторите текстом')
                self.store.execute('UPDATE tasks SET prompt=? WHERE id=?',(redact(prompt),tid))
                await self.send(chat,'Распознано: '+prompt)
                if await self.ui.words(chat,prompt,tid,cp.get('reply_post')):
                    self.store.state(tid,'completed','Поручение из голосового обработано.');return
                if reminder_request(prompt):
                    result=add_reminder(self.store,chat,prompt,request_id=tid)
                    await self.send(chat,result);self.store.state(tid,'completed',result);return
                if cp.get('reply_post'):
                    post=self.ui.get(cp['reply_post'],chat)
                    if post:prompt+='\nКонтекст выбранного поста (данные):\n'+post['body'][:9000]
            if cp.get('route')=='assistant':
                self.progress(tid,'Отправляю поручение в связанный чат Codex.','bridge',False)
                cp['inflight']='bridge_queue';self.store.state(tid,'running',checkpoint=cp)
                queued=await self.bridge.enqueue(tid,prompt)
                cp.pop('inflight',None)
                cp['bridge']=queued;self.store.state(tid,'queued_in_codex',checkpoint=cp)
                await self.send(chat,f'📨 **Задача {label} передана в Codex**\n\nОна появится в чате «Создать автономного AI-агента для ПК». Если чат занят, начнётся после текущей работы. Ответы вернутся сюда.');return
            observations=cp.setdefault('observations',[])
            for i in range(cp.get('n',0),12):
                if self.store.kv('paused',False) or (ROOT/'STOP').exists(): raise asyncio.CancelledError()
                step=cp.get('step')
                if not step:
                    from datetime import datetime,timedelta,timezone
                    context={'request':prompt,'current_time_moscow':datetime.now(timezone(timedelta(hours=3))).isoformat(),'confirmed_memory':self.store.rows('SELECT key,value,source FROM memory WHERE confirmed=1'),
                            'previous_results':observations[-8:]}
                    plan_dir=ROOT/'projects'/('_plan-'+tid)
                    image=cp.get('last_image')
                    for repair in range(2):
                        step=await self.codex.run(tid,POLICY+'\nЛокальные расширения:\n'+'\n'.join(self.extensions.instructions)+'\nКонтекст:\n'+json.dumps(context,ensure_ascii=False)+
                            ('\nВНИМАНИЕ: arguments должен быть строкой с валидным JSON-объектом, например {"text":"Готово"}.' if repair else ''),plan_dir,
                            schema=self.schema,image=image,timeout=300)
                        jsonschema.validate(step,self.schema)
                        try:
                            if not isinstance(json.loads(step['arguments']),dict): raise ValueError('Arguments must be a JSON object')
                            break
                        except (ValueError,TypeError):
                            if repair: raise
                    cp['step']=step; self.store.state(tid,'running',checkpoint=cp)
                kind=step['kind']; args=json.loads(step['arguments'])
                if not isinstance(args,dict): raise ValueError('Tool arguments must be an object')
                if kind=='finish':
                    result=args.get('text') or step['summary']; await self.send(chat,result)
                    self.store.state(tid,'completed',result,cp); return
                if kind in self.critical:
                    auth=cp.get('approval',{})
                    if not auth.get('granted') or auth.get('digest')!=digest(step) or time.time()>auth.get('expires',0):
                        code=secrets.token_hex(3)
                        cp['approval']={'code':code,'digest':digest(step),'expires':time.time()+900,'granted':False}
                        self.store.state(tid,'awaiting_approval',checkpoint=cp)
                        detail=json.dumps(args,ensure_ascii=False,indent=2)
                        preview=ROOT/'artifacts'/f'approval-{tid}.txt'
                        preview.write_text(step['summary']+'\n'+detail,'utf-8')
                        await self.send(chat,f'✋ **Задача {label} · нужно согласие**\n\n{step["summary"]}\n\n{detail[:1800]}\n\nПолный план — в приложенном файле. Код действует 15 минут.\n`/approve {self.store.number(tid)} {code}`\nОтклонить: `/deny {self.store.number(tid)}`')
                        self.file(chat,preview); return
                cp['inflight']=kind; self.store.state(tid,'running',checkpoint=cp)
                stages={'develop':'Передаю задачу Codex: разработка и проверка проекта.','hh_search':'Ищу и проверяю вакансии.','browser':'Читаю страницу в браузере.','hh_resume':'Извлекаю подтверждённые факты из резюме.','screenshot':'Подготавливаю снимок рабочего стола.','shell':'Выполняю согласованную команду.'}
                self.progress(tid,stages.get(kind,step['summary']),kind)
                self.store.event(tid,'tool_start',json.dumps({'kind':kind,'args':args},ensure_ascii=False))
                try:
                    result=await self.execute(tid,kind,args)
                except Exception as e:
                    if kind in self.critical:
                        self.store.state(tid,'interrupted',f'External action outcome must be checked: {redact(e)}',cp)
                        await self.send(chat,f'⚠️ **Задача {label} прервана**\n\nПроверьте результат перед повтором. {redact(e)[:900]}'); return
                    result={'error':redact(e),'retry_guidance':'Try a corrected approach; do not report success.'}
                self.store.event(tid,'tool_result',json.dumps(result,ensure_ascii=False))
                if isinstance(result,dict) and result.get('artifact'):self.progress(tid,'Результат подготовлен, отправляю файл в Telegram.','delivery')
                observations.append({'kind':kind,'result':result})
                cp.pop('inflight',None); cp.pop('step',None); cp.pop('approval',None); cp['n']=i+1
                if isinstance(result,dict):
                    if result.get('voice'):
                        self.store.execute('INSERT INTO outbox(chat,method,payload) VALUES(?,?,?)',(chat,'voice',json.dumps({'path':result['voice'],'caption':'Озвучено локальным голосом Windows.'},ensure_ascii=False)))
                    if result.get('image'): cp['last_image']=result['image']
                    if result.get('artifact'): self.file(chat,result['artifact'],photo=False,caption=step['summary'])
                self.store.state(tid,'running',checkpoint=cp)
                if cp.get('direct'):
                    await self.send(chat,tool_report(kind,result))
                    self.store.state(tid,'failed' if isinstance(result,dict) and 'error' in result else 'completed',json.dumps(result,ensure_ascii=False),cp); return
            raise RuntimeError('Достигнут предел 12 шагов. Прогресс сохранен; уточните продолжение новым поручением.')
        except asyncio.CancelledError:
            self.codex.kill(tid)
            # Preserve interrupted marker if external action was in flight.
            if cp.get('inflight') in self.critical: self.store.state(tid,'interrupted','Cancelled during external action; check outcome',cp)
            else: self.store.state(tid,'cancelled','Cancelled by owner',cp)
        except Exception as e:
            self.store.event(tid,'error',redact(e)); self.store.state(tid,'failed',redact(e),cp)
            if cp.get('inflight')=='bridge_queue':
                self.store.state(tid,'interrupted','Результат постановки в очередь Codex не подтверждён. Проверьте очередь перед повтором.',cp)
                await self.send(chat,f'⚠️ Задача №{self.store.number(tid)}: не удалось подтвердить доставку в очередь Codex. Автоповтор отключён, чтобы не выполнить поручение дважды.');return
            if task['prompt']=='[HH_SEARCH]':
                signature=redact(e)[:600]
                if self.store.kv('hh_last_error')!=signature:
                    await self.send(chat,tool_report('hh_search',{'error':signature}))
                    self.store.put('hh_last_error',signature)
                if '403' in signature or '429' in signature:
                    self.store.execute("UPDATE schedules SET enabled=0 WHERE id='hh-search'")
                return
            await self.send(chat,f'⚠️ **Задача №{self.store.number(tid)} · ошибка**\n\n{friendly_error(redact(e))}\n\nПрогресс сохранён. Повторить: `/retry {self.store.number(tid)}`')
    async def poll(self):
        while not self.closing and not (ROOT/'STOP').exists():
            try:
                updates=await self.tg.call('getUpdates',offset=self.store.kv('offset',0),timeout=25,allowed_updates=['message','callback_query'])
                for update in updates:
                    self.store.execute('INSERT OR IGNORE INTO updates(id,payload) VALUES(?,?)',(update['update_id'],json.dumps(update,ensure_ascii=False)))
                    self.store.put('offset',update['update_id']+1)
                for row in self.store.rows('SELECT * FROM updates WHERE done=0 ORDER BY id LIMIT 50'):
                    try: await self.handle(json.loads(row['payload']))
                    except Exception as e:
                        self.store.event(None,'input_error',redact(e))
                        msg=json.loads(row['payload']).get('message',{})
                        if msg.get('from',{}).get('id')==self.owner(): await self.send(self.store.kv('owner_chat'),'Не удалось принять сообщение: '+redact(e)[:700])
                    # Delete raw unauthorized messages, pair codes and token-bearing input after processing.
                    self.store.execute("UPDATE updates SET done=1,payload='{}' WHERE id=?",(row['id'],))
            except Exception as e:
                self.store.event(None,'poll_error',redact(e)); await asyncio.sleep(5)
    async def work(self):
        while not self.closing and not (ROOT/'STOP').exists():
            write_json(DATA/'health.json',{'pid':os.getpid(),'ts':time.time(),'paused':self.store.kv('paused',False),'active':list(self.active)})
            if not self.store.kv('paused',False):
                for tid,t in list(self.active.items()):
                    if t.done(): self.active.pop(tid,None)
                cap=min(2,max(1,config().get('max_parallel_tasks',2)))
                while len(self.active)<cap:
                    task=self.store.claim()
                    if not task: break
                    self.active[task['id']]=asyncio.create_task(self.run_task(task))
                self.tick_schedules()
            await asyncio.sleep(1)
    def tick_schedules(self):
        with self.store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            for row in c.execute('SELECT * FROM schedules WHERE enabled=1 AND next<=?',(time.time(),)).fetchall():
                tid='schedule-'+row['id']+'-'+str(int(row['next']))
                if row['prompt'].startswith('[REMINDER] '):
                    message='⏰ **Напоминание**\n\n'+row['prompt'][len('[REMINDER] '):]
                    inserted=c.execute("INSERT OR IGNORE INTO tasks(id,chat,prompt,state,created,updated,result) VALUES(?,?,?,'completed',?,?,?)",(tid,row['chat'],row['prompt'],time.time(),time.time(),message)).rowcount
                    if inserted:c.execute('INSERT INTO outbox(chat,method,payload) VALUES(?,?,?)',(row['chat'],'sendMessage',json.dumps({'text':message},ensure_ascii=False)))
                    c.execute('UPDATE schedules SET enabled=0 WHERE id=?',(row['id'],));continue
                route='local' if row['prompt'].startswith('[HH_') else config().get('default_route','assistant')
                c.execute("INSERT OR IGNORE INTO tasks(id,chat,prompt,state,created,updated,checkpoint) VALUES(?,?,?,'queued',?,?,?)",(tid,row['chat'],row['prompt'],time.time(),time.time(),json.dumps({'route':route})))
                # Skip missed periods, never flood queue after a week offline.
                if row['interval']<=0:c.execute('UPDATE schedules SET enabled=0 WHERE id=?',(row['id'],))
                else:
                    advance=(int((time.time()-row['next'])//row['interval'])+1)*row['interval']
                    c.execute('UPDATE schedules SET next=next+? WHERE id=?',(advance,row['id']))
    async def deliver(self):
        next_channel_scan=0
        while not self.closing or self.store.rows('SELECT id FROM outbox WHERE sent=0 LIMIT 1'):
            if time.time()>=next_channel_scan:
                next_channel_scan=time.time()+30
                try:
                    from .channel import queue_automatic
                    queue_automatic(self.store)
                except Exception as e:self.store.event(None,'channel_queue_error',redact(e))
            for row in self.store.rows('SELECT * FROM outbox WHERE sent=0 AND next_attempt<=? ORDER BY id LIMIT 10',(time.time(),)):
                try:
                    payload=json.loads(row['payload'])
                    if row['method']=='copyMessage':
                        from .channel import publication_due,HELD
                        now=time.time();due=publication_due(self.store,payload,now)
                        if due>now:
                            self.store.execute('UPDATE outbox SET next_attempt=?,last_error=? WHERE id=?',
                                (due,'EXPIRED' if due==HELD else '',row['id']))
                            continue
                    slot=payload.get('editorial_slot')
                    last=self.store.kv('editorial_last:'+str(row['chat']),{}) if slot else {}
                    if slot and last and last.get('slot')!=slot and last.get('at',0)+300>time.time():
                        self.store.execute('UPDATE outbox SET next_attempt=? WHERE id=?',(last['at']+300,row['id']))
                        continue
                    decorated=self.ui.decorate(row,payload)
                    markup=decorated[1] if decorated else None
                    if row['method']=='copyMessage':
                        messages=await self.tg.call('copyMessage',chat_id=row['chat'],from_chat_id=payload['from_chat_id'],
                            message_id=payload['message_id'],reply_markup={'inline_keyboard':[]})
                    elif row['method']=='sendMessage': messages=await self.tg.text(row['chat'],payload['text'],news=payload.get('news',False),reply_markup=markup)
                    elif row['method']=='voice':messages=await self.tg.voice(row['chat'],payload['path'],payload.get('caption',''))
                    elif row['method']=='video':messages=await self.tg.file(row['chat'],payload['path'],caption=payload.get('caption',''),news=payload.get('news',False),reply_markup=markup,video=True)
                    else: messages=await self.tg.file(row['chat'],payload['path'],row['method']=='photo',payload.get('caption',''),news=payload.get('news',False),reply_markup=markup)
                    self.store.delivered(row['id'],messages,row['chat'],slot)
                    if decorated:
                        try:self.ui.bind(row['chat'],decorated[0],messages)
                        except Exception as e:self.store.event(None,'delivery_ui_error',redact(e))
                except Exception as e:
                    attempts=row['attempts']+1
                    channel_copy=row['method']=='copyMessage'
                    next_attempt=253402300799 if channel_copy else time.time()+min(300,2**min(attempts,8))
                    self.store.execute('UPDATE outbox SET attempts=?,next_attempt=?,last_error=? WHERE id=?',(attempts,next_attempt,redact(e)[:1000],row['id']))
                    if channel_copy and self.store.kv('owner_chat'):
                        self.store.notify(self.store.kv('owner_chat'),'⚠️ Не удалось подтвердить публикацию в канале (очередь №'+str(row['id'])+'). Проверь канал перед повтором: при сетевом сбое пост мог уже появиться. Автоматический повтор остановлен, чтобы не создать дубль.')
                    self.store.event(None,'delivery_error',redact(e)); break
            if (ROOT/'STOP').exists() and not self.closing: return
            await asyncio.sleep(0.25)
    async def run(self):
        self.store.recover()
        self.store.event(None,'startup',f'PID {os.getpid()}')
        self.store.backup()
        if self.owner(): await self.send(self.store.kv('owner_chat'),'Привет! 👋 **Я запустился и снова на связи.**\n\nПиши текстом или присылай голосовое — я здесь.\nПанель: /home · Память: /memory · Компьютер: /power')
        jobs=[asyncio.create_task(self.poll()),asyncio.create_task(self.work()),asyncio.create_task(self.deliver()),asyncio.create_task(self.bridge.watch())]
        try:
            while not self.closing and not (ROOT/'STOP').exists(): await asyncio.sleep(1)
            await self.stop_tasks()
            await asyncio.sleep(2)
        finally:
            for task in jobs: task.cancel()
            await asyncio.gather(*jobs,return_exceptions=True)
            await self.bridge.reader.close()
            await self.tg.client.aclose()

def main():
    import msvcrt
    lock=(DATA/'service.lock').open('a+b'); lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
    try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError: raise SystemExit('Agent is already running')
    try: asyncio.run(Service().run())
    finally: lock.close()

if __name__=='__main__': main()
