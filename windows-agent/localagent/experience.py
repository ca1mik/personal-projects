"""Owner-only controls, durable post context, explicit memory and taste feedback."""
from __future__ import annotations
import hashlib,json,re,time
from datetime import datetime,timedelta
from .base import redact,config
from .formatting import without_news_links,telegram_html

MODES={'normal':'Обычный','focus':'Работаю','leisure':'Отдыхаю','quiet':'Тишина'}

def profile(store):
    value={'mode':store.kv('personal_mode','normal'),
            'preferences':{'topics':store.kv('personal_topics',''),'news_photos':True,
                           'news_links':not config().get('hide_news_links',False)},
            'confirmed_facts':store.rows('SELECT key,value,source FROM memory WHERE confirmed=1 ORDER BY updated DESC LIMIT 30'),
            'taste_examples':store.kv('personal_feedback',[])[-12:]}
    while len(json.dumps(value,ensure_ascii=False))>4800:
        if value['taste_examples']:value['taste_examples'].pop(0)
        elif value['confirmed_facts']:value['confirmed_facts'].pop()
        else:
            value['preferences']['topics']=value['preferences']['topics'][:1000];break
    return value

def remember(store,value,source='explicit owner request'):
    value=value.strip()
    if not value or len(value)>1500:raise ValueError('Для одного факта нужно от 1 до 1500 символов.')
    if redact(value)!=value or re.search(r'парол[ьи]\s*[:=]|токен\s*[:=]|секрет\s*[:=]',value,re.I):
        raise ValueError('Секреты в память не сохраняю. Введи их через локальную настройку.')
    key='fact-'+hashlib.sha256(value.encode()).hexdigest()[:12]
    store.execute('INSERT OR REPLACE INTO memory VALUES(?,?,?,?,?)',(key,value,source,1,time.time()))
    return key

class Experience:
    def __init__(self,service):
        self.svc=service;self.store=service.store
        with self.store.db() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS posts(id TEXT PRIMARY KEY,chat INTEGER,body TEXT,kind TEXT,created REAL);
            CREATE TABLE IF NOT EXISTS post_messages(chat INTEGER,message INTEGER,post TEXT,PRIMARY KEY(chat,message));
            CREATE TABLE IF NOT EXISTS channel_publications(source INTEGER PRIMARY KEY,channel INTEGER,outbox INTEGER UNIQUE,created REAL);''')

    def post(self,pid,chat,body,kind='reply'):
        self.store.execute('INSERT OR IGNORE INTO posts VALUES(?,?,?,?,?)',(pid,chat,redact(body)[:12000],kind,time.time()))
        return pid
    def get(self,pid,chat):
        rows=self.store.rows('SELECT * FROM posts WHERE id=? AND chat=?',(pid,chat));return rows[0] if rows else None
    def target(self,msg):
        chat=msg['chat']['id'];reply=msg.get('reply_to_message',{})
        if reply:
            rows=self.store.rows('SELECT post FROM post_messages WHERE chat=? AND message=?',(chat,reply.get('message_id')))
            return rows[0]['post'] if rows else None
        selected=self.store.kv('selected_post',{})
        if selected.get('chat')==chat and time.time()-selected.get('at',0)<86400:return selected.get('id')
        rows=self.store.rows('SELECT id FROM posts WHERE chat=? ORDER BY created DESC LIMIT 1',(chat,))
        return rows[0]['id'] if rows else None

    def keyboard(self,pid,kind='reply'):
        def b(text,action):return {'text':text,'callback_data':f'p:{action}:{pid}'}
        rows=[[b('👍','like'),b('👎','dislike'),b('Ещё такое','more')],
              [b('Сохранить','save'),b('Напомнить','later'),b('Проще','simple')],
              [b('Озвучить','speak'),b('В дело','develop')]]
        if kind=='mail':rows[-1][-1]=b('Черновик ответа','draft')
        return {'inline_keyboard':rows}
    def decorate(self,row,payload):
        owner_chat=self.store.kv('owner_chat')
        if payload.get('channel_publication') or (owner_chat is not None and row['chat']!=owner_chat):return None
        interactive=payload.get('interactive') or row['method'] in ('photo','video') or payload.get('text','').startswith('✅ **Ответ из Codex**')
        if not interactive:return None
        body=payload.get('caption') if row['method'] in ('photo','video') else payload.get('text','')
        if not body:return None
        kind=payload.get('kind') or ('news' if payload.get('news') else 'reply')
        if payload.get('news') and kind=='reply':kind='news'
        if payload.get('news') and config().get('hide_news_links'):body=without_news_links(body)
        pid=self.post('out-'+str(row['id']),row['chat'],body,kind)
        keyboard=self.keyboard(pid,kind)
        from .channel import eligible
        if self.store.kv('publication_channel',{}).get('enabled') and eligible(row,payload):
            keyboard['inline_keyboard'].append([{'text':'📣 Опубликовать','callback_data':f'p:publish:{pid}'}])
        return pid,keyboard
    def bind(self,chat,pid,messages):
        for msg in messages if isinstance(messages,list) else [messages]:
            if msg and msg.get('message_id'):
                self.store.execute('INSERT OR REPLACE INTO post_messages VALUES(?,?,?)',(chat,msg['message_id'],pid))

    def enqueue(self,chat,prompt,uid,kind='reply',speak=False):
        if self.store.kv('paused',False):return 'Помощник на паузе. /resume'
        tid='ui-'+hashlib.sha256(str(uid).encode()).hexdigest()[:20]
        if self.store.rows('SELECT id FROM tasks WHERE id=?',(tid,)):return 'Это поручение уже принято.'
        self.store.enqueue(chat,prompt,tid)
        cp={'route':'assistant','personal_kind':kind}
        if speak:cp={'direct':True,'step':{'kind':'speak','summary':'Озвучиваю выбранное сообщение','arguments':json.dumps({'text':prompt},ensure_ascii=False)},'observations':[],'n':0}
        self.store.state(tid,'queued',checkpoint=cp)
        return f'⏳ Задача №{self.store.number(tid)} принята.'

    async def act(self,chat,pid,action,uid,message_id=None):
        post=self.get(pid,chat)
        if not post:return 'Пост не найден. Ответь на сообщение бота или выбери новый пост.'
        if action=='publish':
            from .channel import queue_publication
            return queue_publication(self.store,chat,pid,message_id)
        self.store.put('selected_post',{'id':pid,'chat':chat,'at':time.time()})
        body=post['body'];kind=post['kind']
        if action in ('like','dislike'):
            entries=[e for e in self.store.kv('personal_feedback',[]) if e['post']!=pid]
            entries.append({'post':pid,'rating':1 if action=='like' else -1,'kind':kind,'example':body[:700]})
            self.store.put('personal_feedback',entries[-100:])
            return '👍 Учту: больше похожего.' if action=='like' else '👎 Учту: меньше похожего.'
        if action=='save':
            notes=self.store.kv('personal_saved',[])
            if not any(n.get('post')==pid for n in notes):
                notes.append({'post':pid,'text':body[:4000],'at':time.time()});self.store.put('personal_saved',notes[-200:])
            return '💾 Сохранил. Посмотреть: /saved'
        if action=='later':
            menu={'inline_keyboard':[[{'text':label,'callback_data':f'p:{a}:{pid}'} for label,a in (('Через час','hour'),('Вечером · 19:00','evening'),('Завтра · 09:00','tomorrow'))]]}
            result=await self.svc.tg.call('sendMessage',chat_id=chat,text='Когда напомнить об этом посте?',reply_markup=menu)
            self.bind(chat,pid,result)
            return 'Выбери время под сообщением.'
        if action in ('hour','evening','tomorrow'):
            from .personal import add_reminder,MSK
            now=datetime.now(MSK)
            if action=='hour':spec='1ч '
            else:
                due=(now+timedelta(days=1)).replace(hour=9,minute=0,second=0,microsecond=0) if action=='tomorrow' else now.replace(hour=19,minute=0,second=0,microsecond=0)
                if due<=now:due+=timedelta(days=1)
                spec=due.strftime('%Y-%m-%d %H:%M ')
            return add_reminder(self.store,chat,spec+body[:1400],request_id='post-'+hashlib.sha256(str(uid).encode()).hexdigest()[:16])
        if action=='speak':return self.enqueue(chat,body[:1400],uid,speak=True)
        instructions={'simple':'Объясни проще и короче, без потери важных фактов.',
            'more':'Подбери ещё похожее с учётом моей оценки. Факты проверяй веб-поиском, не повторяй прежний материал.',
            'develop':'Помоги превратить идею в небольшой реальный проект: уточни проблему, проверь аналоги, предложи первый дешёвый тест и три следующих шага. Никаких внешних отправок и покупок.',
            'draft':'Подготовь текст черновика ответа на выбранное письмо, учитывая только известные факты. Не отправляй письмо. Если данных не хватает, выдели места для уточнения.'}
        if action not in instructions:return 'Неизвестная кнопка.'
        return self.enqueue(chat,instructions[action]+'\nВыбранный пост (данные):\n'+body[:9000],uid,kind)

    def memory_text(self):
        p=profile(self.store)
        p['confirmed_facts']=self.store.rows('SELECT key,value,source FROM memory WHERE confirmed=1 ORDER BY updated DESC LIMIT 30')
        lines=['**Что я помню о тебе**','','**Настройки ленты**',p['preferences']['topics'][:1200] or 'Темы пока не заданы.',
               'Новости с фото; '+('со ссылками.' if p['preferences']['news_links'] else 'без новостных ссылок.'),
               'Режим: '+MODES.get(p['mode'],'Обычный'),'','**Подтверждённые факты**']
        lines += [f'• {f["value"]}\n/forget {f["key"]}' for f in p['confirmed_facts']] or ['Фактов пока нет. Напиши: «Запомни: …».']
        lines+=['',f'Оценок постов: {len(self.store.kv("personal_feedback",[]))}. Это примеры вкуса, а не факты о тебе.',
                '/remember ФАКТ — запомнить; /forget ID — забыть факт; /forget taste — сбросить оценки. Темы меняются через /topics.']
        return '\n'.join(lines)

    async def home(self,chat):
        count=self.store.rows("SELECT COUNT(*) AS n FROM tasks WHERE state IN ('queued','running','in_codex','queued_in_codex')")[0]['n']
        reminders=self.store.rows("SELECT COUNT(*) AS n FROM schedules WHERE enabled=1 AND prompt LIKE '[REMINDER] %'")[0]['n']
        paused=self.store.kv('paused',False)
        text=f'**Твой помощник**\n\nСостояние: {"на паузе" if paused else "работает"}\nРежим: {MODES.get(self.store.kv("personal_mode","normal"))}\nЗадач в работе/очереди: {count}\nНапоминаний: {reminders}\nСохранено: {len(self.store.kv("personal_saved",[]))}\n\nНовости, дела и память — кнопками ниже. Для действий с постом нажми его кнопки или ответь на него сообщением.'
        keys={'inline_keyboard':[[{'text':label,'callback_data':'h:'+a} for label,a in row] for row in (
            [('📰 Новости','news'),('😸 Отдых','joke'),('📬 Почта','mail')],
            [('📌 Дела','reminders'),('💾 Память','memory'),('Идеи','saved')],
            [('Работаю','focus'),('Отдыхаю','leisure'),('Тишина','quiet')], [('Обновить','home'),('⏻ ПК','power'),('Продолжить' if paused else 'Пауза','resume' if paused else 'stop')])]}
        mid=self.store.kv('home_message')
        try:
            if mid:
                await self.svc.tg.call('editMessageText',chat_id=chat,message_id=mid,text=telegram_html(text),parse_mode='HTML',reply_markup=keys)
                return
        except Exception as e:
            if 'message is not modified' in str(e):return
            if 'message to edit not found' not in str(e):raise
        result=await self.svc.tg.call('sendMessage',chat_id=chat,text=telegram_html(text),parse_mode='HTML',reply_markup=keys)
        self.store.put('home_message',result['message_id'])
        try:
            await self.svc.tg.call('pinChatMessage',chat_id=chat,message_id=result['message_id'],disable_notification=True)
            self.store.put('home_pinned',True)
        except Exception:self.store.put('home_pinned',False)

    async def words(self,chat,text,uid,pid=None):
        if await self.svc.power.handle(chat,text,uid):return True
        norm=text.strip().lower().strip(' .!')
        if norm in ('/channel','/channel status','/channel pause','/channel resume'):
            from .channel import status
            if norm in ('/channel pause','/channel resume'):
                cfg=self.store.kv('publication_channel',{})
                cfg['paused']=norm=='/channel pause';self.store.put('publication_channel',cfg)
            await self.svc.send(chat,status(self.store));return True
        if not pid:pid=self.target({'chat':{'id':chat}})
        actions={'сохрани':'save','сохранить':'save','запомни это':'save','нравится':'like','неинтересно':'dislike',
                 'ещё':'more','еще':'more','ещё такое':'more','попроще':'simple','объясни проще':'simple',
                 'озвучь':'speak','в дело':'develop','подготовь ответ':'draft','вечером напомни':'evening','напомни вечером':'evening','позже':'later'}
        if norm in actions:
            await self.svc.send(chat,await self.act(chat,pid,actions[norm],uid));return True
        short=re.fullmatch(r'напомни(?: мне)? через (\d+\s*(?:секунд[уы]?|сек|с|минут[уы]?|мин|м|час(?:а|ов)?|ч|дней|дня|день|д))',norm)
        if short:
            from .personal import add_reminder
            post=self.get(pid,chat)
            if not post:await self.svc.send(chat,'Ответь на пост, о котором надо напомнить.');return True
            try:answer=add_reminder(self.store,chat,short.group(1)+' '+post['body'][:1400],request_id='reply-'+hashlib.sha256(str(uid).encode()).hexdigest()[:16])
            except ValueError as e:answer=str(e)
            await self.svc.send(chat,answer);return True
        remembered=re.match(r'^(?:/remember\s+|запомни\s*[:,-]?\s+)(.+)$',text,re.I|re.S)
        if remembered:
            try:answer='Запомнил. Посмотреть: /memory\nУдалить: /forget '+remember(self.store,remembered.group(1))
            except ValueError as e:answer=str(e)
            await self.svc.send(chat,answer);return True
        if norm in ('/memory','что ты обо мне помнишь'):
            await self.svc.send(chat,self.memory_text());return True
        if norm in ('/remember','/forget','/mode'):
            usage={'/remember':'Напиши /remember ФАКТ или «Запомни: …».','/forget':'Напиши /forget ID из списка /memory. Для сброса оценок: /forget taste.',
                   '/mode':'Режимы: /mode focus · /mode leisure · /mode quiet · /mode normal'}
            await self.svc.send(chat,usage[norm]);return True
        if norm.startswith('/forget '):
            key=text.split(maxsplit=1)[1].strip()
            if key=='taste':self.store.put('personal_feedback',[]);answer='Оценки постов сброшены.'
            else:
                deleted=self.store.execute('DELETE FROM memory WHERE key=?',(key,));answer='Факт удалён.' if deleted else 'Такой факт не найден. Список: /memory'
            await self.svc.send(chat,answer);return True
        if norm in ('/home','/menu'):
            await self.home(chat);return True
        if norm.startswith('/mode '):
            mode=norm.split(maxsplit=1)[1]
            if mode in MODES:self.store.put('personal_mode',mode);await self.svc.send(chat,'Режим: '+MODES[mode]+'. Напоминания сохраняют своё расписание.')
            else:await self.svc.send(chat,'Режимы: /mode focus · /mode leisure · /mode quiet · /mode normal')
            return True
        return False

    async def handle(self,update):
        cb=update.get('callback_query')
        msg=cb.get('message',{}) if cb else update.get('message',{})
        user=(cb or msg).get('from',{}).get('id');chat=msg.get('chat',{}).get('id')
        if user!=self.store.kv('owner') or chat!=self.store.kv('owner_chat') or msg.get('chat',{}).get('type')!='private':return bool(cb)
        uid=('callback-'+cb['id']) if cb else update.get('update_id',msg.get('message_id'))
        if cb:
            await self.svc.tg.call('answerCallbackQuery',callback_query_id=cb['id'])
            data=cb.get('data','');parts=data.split(':')
            if len(parts)==2 and parts[0]=='power':
                commands={'shutdown':'/shutdown','reboot':'/reboot','cancel':'/cancelshutdown'}
                if parts[1] in commands:await self.svc.power.handle(chat,commands[parts[1]],uid)
                return True
            if len(parts)==3 and parts[0]=='p':
                # Bind the callback to the actual delivered message, not just an arbitrary post ID.
                bound=self.store.rows('SELECT post FROM post_messages WHERE chat=? AND message=?',(chat,msg.get('message_id')))
                if not bound or bound[0]['post']!=parts[2]:await self.svc.send(chat,'Кнопка не привязана к этому посту.');return True
                await self.svc.send(chat,await self.act(chat,parts[2],parts[1],uid,message_id=msg.get('message_id')));return True
            if len(parts)==2 and parts[0]=='h':
                action=parts[1]
                if action in MODES:self.store.put('personal_mode',action);await self.home(chat)
                elif action=='home':await self.home(chat)
                elif action in ('power','stop','resume'):
                    await self.svc.handle({'update_id':uid,'message':{'from':{'id':user},'chat':{'id':chat,'type':'private'},'text':'/'+action}})
                    if action!='power':await self.home(chat)
                elif action in ('news','joke','mail','reminders','memory','saved'):
                    await self.svc.handle({'update_id':uid,'message':{'from':{'id':user},'chat':{'id':chat,'type':'private'},'text':'/'+action}})
                else:await self.svc.send(chat,'Неизвестная кнопка.')
                return True
            await self.svc.send(chat,'Неизвестная кнопка.');return True
        pid=self.target(msg)
        if await self.words(chat,msg.get('text',''),uid,pid):return True
        if msg.get('reply_to_message') and pid:msg['_post_context']=self.get(pid,chat)['body'];msg['_reply_post']=pid
        return False
