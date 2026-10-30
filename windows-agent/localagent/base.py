from __future__ import annotations
import ctypes, hashlib, json, os, re, secrets, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
for folder in ('data', 'logs', 'projects', 'artifacts', 'inbox', 'backups','resumes','extensions'):
    (ROOT / folder).mkdir(exist_ok=True)

def read_json(path, default=None):
    return json.loads(Path(path).read_text('utf-8')) if Path(path).exists() else default

def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf-8')
    tmp.replace(path)

def config():
    return read_json(ROOT / 'config.json', {})

def redact(value):
    value = str(value)
    value = re.sub(r'\b\d{7,12}:[A-Za-z0-9_-]{30,}', '[TELEGRAM_TOKEN]', value)
    value = re.sub(r'(?i)(Bearer\s+|(?:api[_-]?key|password|access_token|refresh_token)["\s:=]+)[^\s",}]+', r'\1[REDACTED]', value)
    value = re.sub(r'\bsk-[A-Za-z0-9_-]+', '[API_KEY]', value)
    return value

def protect(raw: bytes, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_uint32), ('data', ctypes.POINTER(ctypes.c_byte))]
    buf = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    target = Blob()
    fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)

def set_secret(name, value):
    if not re.fullmatch(r'[a-z_]+', name):
        raise ValueError('Invalid secret name')
    (DATA / (name + '.dpapi')).write_bytes(protect(value.encode()))

def get_secret(name):
    path = DATA / (name + '.dpapi')
    return protect(path.read_bytes(), True).decode() if path.exists() else None

def inside(root, path):
    root = Path(root).resolve()
    result = (root / path).resolve()
    if not result.is_relative_to(root):
        raise ValueError('Path escapes allowed directory')
    return result

class Store:
    def __init__(self, path=None):
        self.path = path or DATA / 'agent.sqlite3'
        with self.db() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,chat INTEGER,prompt TEXT,state TEXT,
              created REAL,updated REAL,checkpoint TEXT DEFAULT '{}',result TEXT DEFAULT '',attempt INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,ts REAL,task TEXT,kind TEXT,detail TEXT);
            CREATE TABLE IF NOT EXISTS updates(id INTEGER PRIMARY KEY,payload TEXT,done INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS memory(key TEXT PRIMARY KEY,value TEXT,source TEXT,confirmed INTEGER,updated REAL);
            CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY,chat INTEGER,prompt TEXT,interval REAL,next REAL,enabled INTEGER);
            CREATE TABLE IF NOT EXISTS vacancies(id TEXT PRIMARY KEY,fingerprint TEXT,payload TEXT,first_seen REAL,last_seen REAL);
            CREATE TABLE IF NOT EXISTS resumes(id TEXT PRIMARY KEY,path TEXT,profile TEXT,created REAL);
            CREATE TABLE IF NOT EXISTS applications(vacancy TEXT PRIMARY KEY,resume TEXT,state TEXT,payload TEXT,updated REAL);
            CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY,chat INTEGER,method TEXT,payload TEXT,sent INTEGER DEFAULT 0);
            ''')
            columns={r[1] for r in c.execute('PRAGMA table_info(outbox)')}
            if 'attempts' not in columns:c.execute('ALTER TABLE outbox ADD COLUMN attempts INTEGER DEFAULT 0')
            if 'next_attempt' not in columns:c.execute('ALTER TABLE outbox ADD COLUMN next_attempt REAL DEFAULT 0')
            if 'sent_at' not in columns:c.execute('ALTER TABLE outbox ADD COLUMN sent_at REAL')
            if 'receipt' not in columns:c.execute('ALTER TABLE outbox ADD COLUMN receipt TEXT')
            if 'last_error' not in columns:c.execute("ALTER TABLE outbox ADD COLUMN last_error TEXT DEFAULT ''")
            c.execute('CREATE TABLE IF NOT EXISTS task_outbox(task TEXT,outbox INTEGER,PRIMARY KEY(task,outbox))')
    def delivery_status(self, tid):
        rows=self.rows('SELECT o.sent,o.attempts FROM outbox o JOIN task_outbox t ON t.outbox=o.id WHERE t.task=?',(tid,))
        if not rows:return ''
        sent=sum(bool(r['sent']) for r in rows)
        if sent==len(rows):return f'Доставлено в Telegram: {sent}/{len(rows)}'
        retry=any(r['attempts'] and not r['sent'] for r in rows)
        return f'Доставка в Telegram: {sent}/{len(rows)} · '+('повтор после ошибки' if retry else 'в очереди')
    def delivered(self, ident, messages, chat=None, slot=None):
        """Record Telegram acknowledgement before optional rating/UI bookkeeping."""
        now=time.time()
        with self.db() as c:
            c.execute("UPDATE outbox SET sent=1,sent_at=?,receipt=?,last_error='' WHERE id=?",
                      (now,json.dumps(messages,ensure_ascii=False),ident))
            if slot:
                c.execute('INSERT OR REPLACE INTO kv VALUES(?,?)',
                          ('editorial_last:'+str(chat),json.dumps({'slot':slot,'at':now})))
    def db(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        return c
    def rows(self, sql, args=()):
        with self.db() as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]
    def execute(self, sql, args=()):
        with self.db() as c:
            return c.execute(sql, args).rowcount
    def kv(self, key, default=None):
        r = self.rows('SELECT value FROM kv WHERE key=?', (key,))
        return json.loads(r[0]['value']) if r else default
    def put(self, key, value):
        self.execute('INSERT OR REPLACE INTO kv VALUES(?,?)', (key,json.dumps(value,ensure_ascii=False)))
    def event(self, task, kind, detail):
        self.execute('INSERT INTO events(ts,task,kind,detail) VALUES(?,?,?,?)', (time.time(),task,kind,redact(detail)[:16000]))
    def enqueue(self, chat, prompt, task_id=None):
        tid = task_id or secrets.token_hex(4)
        self.execute("INSERT OR IGNORE INTO tasks(id,chat,prompt,state,created,updated) VALUES(?,?,?,'queued',?,?)",
                     (tid,chat,redact(prompt),time.time(),time.time()))
        return tid
    def state(self, tid, state, result=None, checkpoint=None):
        self.execute('UPDATE tasks SET state=?,updated=? WHERE id=?', (state,time.time(),tid))
        if result is not None:
            self.execute('UPDATE tasks SET result=? WHERE id=?', (redact(result),tid))
        if checkpoint is not None:
            self.execute('UPDATE tasks SET checkpoint=? WHERE id=?', (json.dumps(checkpoint,ensure_ascii=False),tid))
    def claim(self):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            r = c.execute("SELECT * FROM tasks WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if r:
                c.execute("UPDATE tasks SET state='running',updated=?,attempt=attempt+1 WHERE id=?", (time.time(),r['id']))
                return dict(r)
    def number(self,tid):
        rows=self.rows('SELECT rowid AS n FROM tasks WHERE id=?',(tid,))
        return rows[0]['n'] if rows else tid
    def resolve(self,number):
        value=str(number).lstrip('№#')
        if value.isdigit():
            rows=self.rows('SELECT id FROM tasks WHERE rowid=?',(int(value),))
            return rows[0]['id'] if rows else value
        return value
    def recover(self):
        # Only read-only steps / isolated development can replay automatically. External side effects need inspection.
        for r in self.rows("SELECT * FROM tasks WHERE state='running'"):
            cp = json.loads(r['checkpoint'])
            unsafe = cp.get('inflight') in ('shell','gui','hh_apply','hh_reply','bridge_queue')
            self.state(r['id'], 'interrupted' if unsafe else 'queued', 'Recovered after restart; inspect external side effects' if unsafe else None)
    def notify(self, chat, message):
        if chat:
            self.execute('INSERT INTO outbox(chat,method,payload) VALUES(?,?,?)', (chat,'sendMessage',json.dumps({'text':redact(message)[:50000]},ensure_ascii=False)))
    def backup(self):
        dest = ROOT / 'backups' / (time.strftime('%Y%m%d-%H%M%S') + '.sqlite3')
        with self.db() as src, sqlite3.connect(dest) as dst:
            src.backup(dst)
        for old in sorted((ROOT/'backups').glob('*.sqlite3'))[:-7]:
            old.unlink()
        import shutil
        stamp=dest.stem
        if (ROOT/'config.json').exists():shutil.copy2(ROOT/'config.json',ROOT/'backups'/(stamp+'-config.json'))
        for old in sorted((ROOT/'backups').glob('*-config.json'))[:-7]:old.unlink()
        return str(dest)

def digest(plan):
    return hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
