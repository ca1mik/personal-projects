"""Owner-approved channel publishing of the exact delivered preview message."""
from __future__ import annotations
import json,re,time
from datetime import datetime,timedelta,timezone

PUBLIC_KINDS={'news','meme','idea','fact'}
MOSCOW=timezone(timedelta(hours=3))
HELD=253402300799

def publication_due(store,payload,now=None):
    """Recheck at dispatch: no night posts, catch-up bursts or stale automatic posts."""
    now=time.time() if now is None else now
    cfg=store.kv('publication_channel',{})
    if payload.get('automatic') and now-payload.get('source_at',now)>21600:return HELD
    if not cfg.get('enabled') or cfg.get('paused') or store.kv('paused',False) or store.kv('personal_mode')=='quiet':return now+60
    interval=max(1800,min(3600,cfg.get('interval_seconds',2700))) if cfg.get('mode')=='automatic' else 300
    last=store.kv('editorial_last:'+str(cfg.get('id')),{}).get('at',0)
    due=max(now,last+interval)
    local=datetime.fromtimestamp(due,MOSCOW)
    if local.hour<9:local=local.replace(hour=9,minute=0,second=0,microsecond=0)
    elif local.hour>=22:local=(local+timedelta(days=1)).replace(hour=9,minute=0,second=0,microsecond=0)
    else:return due
    return max(due,local.timestamp())

def queue_automatic(store,now=None):
    now=time.time() if now is None else now
    cfg=store.kv('publication_channel',{})
    if not cfg.get('enabled') or cfg.get('mode')!='automatic' or cfg.get('paused'):return
    if store.kv('paused',False) or store.kv('personal_mode')=='quiet':return
    rows=store.rows('SELECT o.* FROM outbox o LEFT JOIN channel_publications p ON p.source=o.id '
        'WHERE o.chat=? AND o.id>? AND o.sent=1 AND o.sent_at>=? AND p.source IS NULL ORDER BY o.id',
        (store.kv('owner_chat'),cfg.get('after_outbox',0),max(cfg.get('automatic_since',now),now-21600)))
    for row in rows:
        payload=json.loads(row['payload'])
        if not eligible(row,payload):continue
        receipt=json.loads(row['receipt'] or 'null')
        messages=receipt if isinstance(receipt,list) else [receipt]
        if len(messages)!=1 or not messages[0] or not messages[0].get('message_id'):continue
        queue_publication(store,row['chat'],'out-'+str(row['id']),messages[0]['message_id'],automatic=True)

def eligible(row,payload):
    return (payload.get('channel_candidate') is True
            and payload.get('kind') in PUBLIC_KINDS
            and row['method'] in ('sendMessage','photo','video')
            and len(payload.get('text') or payload.get('caption') or '')<=3000)

def status(store):
    cfg=store.kv('publication_channel',{})
    if not cfg.get('enabled'):return 'Канал для публикаций не подключён.'
    mode=('Автопубликация примерно раз в '+str(cfg.get('interval_seconds',2700)//60)+' минут, 09:00–22:00 МСК. '
          'Нужен свежий подготовленный пост; без материала слот пропускается.' if cfg.get('mode')=='automatic'
          else 'Черновики в личку → кнопка «Опубликовать».')
    return ('📣 Канал: '+cfg['title']+' (@'+cfg['username']+')\nРежим: '+mode+'\n'
            +('Публикации приостановлены.\n' if cfg.get('paused') else '')+
            'В канал доступны только посты подборки: новости, мемы, идеи и факты.\n'
            'Почта и ответы на личные поручения остаются в личке.\n/channel pause — пауза, /channel resume — продолжить.')

def queue_publication(store,chat,pid,message_id,automatic=False):
    cfg=store.kv('publication_channel',{})
    if chat!=store.kv('owner_chat'):return 'Публикация доступна только владельцу.'
    if not cfg.get('enabled'):return 'Канал для публикаций не подключён.'
    target=cfg.get('id')
    if type(target) is not int or target>=0:return 'Не задан проверенный канал.'
    match=re.fullmatch(r'out-(\d+)',pid)
    if not match:return 'Этот пост недоступен для публикации.'
    source=int(match.group(1))
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        bound=c.execute('SELECT post FROM post_messages WHERE chat=? AND message=?',(chat,message_id)).fetchone()
        row=c.execute('SELECT * FROM outbox WHERE id=? AND chat=?',(source,chat)).fetchone()
        if not bound or bound['post']!=pid or not row or not row['sent'] or not eligible(row,json.loads(row['payload'])):
            return 'Публиковать можно только доставленный пост подборки с его собственной кнопки.'
        previous=c.execute('SELECT o.sent,o.receipt,o.last_error FROM channel_publications p JOIN outbox o ON o.id=p.outbox WHERE p.source=?',(source,)).fetchone()
        if previous:
            if previous['sent']:return 'Этот пост уже опубликован.'
            if previous['last_error']=='EXPIRED':return 'Этот пост устарел и снят с автопубликации.'
            if previous['last_error']:return 'Публикация не подтверждена. Проверь канал: автоматический повтор остановлен, чтобы не создать дубль.'
            return 'Этот пост уже в очереди канала.'
        # copyMessage reuses the exact Telegram preview, not a potentially changed local file.
        payload={'from_chat_id':chat,'message_id':message_id,'channel_publication':True,
                 'source_outbox':source,'kind':json.loads(row['payload'])['kind'],
                 'editorial_slot':'channel:'+str(source)}
        if automatic:payload.update(automatic=True,source_at=row['sent_at'])
        outbox=c.execute('INSERT INTO outbox(chat,method,payload) VALUES(?,?,?)',
                         (target,'copyMessage',json.dumps(payload,ensure_ascii=False))).lastrowid
        c.execute('INSERT INTO channel_publications(source,channel,outbox,created) VALUES(?,?,?,?)',
                  (source,target,outbox,time.time()))
    return '📣 Пост поставлен в очередь канала «'+cfg['title']+'». Публикация по расписанию канала.'
