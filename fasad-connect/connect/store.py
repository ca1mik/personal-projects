from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.path = directory / 'connect.sqlite'
        key = directory / 'connect.key'
        try:
            with key.open('xb') as f:
                f.write(Fernet.generate_key())
        except FileExistsError:
            pass
        self.cipher = Fernet(key.read_bytes())
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS links (
                scope TEXT NOT NULL, order_id TEXT NOT NULL, deal_id INTEGER,
                state TEXT NOT NULL DEFAULT 'new', error TEXT, updated_at TEXT,
                PRIMARY KEY(scope,order_id), UNIQUE(scope,deal_id));
            CREATE TABLE IF NOT EXISTS publications (
                scope TEXT NOT NULL, order_id TEXT NOT NULL, digest TEXT NOT NULL,
                state TEXT NOT NULL, comment_id INTEGER, updated_at TEXT,
                PRIMARY KEY(scope,order_id,digest));
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT NOT NULL,
                order_id TEXT, kind TEXT NOT NULL, message TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS demo_deals (id INTEGER PRIMARY KEY AUTOINCREMENT, fields TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS demo_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, deal_id INTEGER NOT NULL, fields TEXT NOT NULL);
            ''')
        if not self.get('instance_id'):
            self.set('instance_id', str(uuid.uuid4()))

    @contextmanager
    def db(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=30)
            db.row_factory = sqlite3.Row
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def get(self, key, default=None):
        with self.db() as db:
            row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.db() as db:
            db.execute('INSERT INTO meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key,json.dumps(value,ensure_ascii=False)))

    def config(self):
        return self.get('config', {'mode':'demo','company':'Мебельная мастерская','public_url':'','stage_map':{},'status_field':''})

    def webhook(self):
        encrypted = self.get('webhook')
        return self.cipher.decrypt(encrypted.encode()).decode() if encrypted else ''

    def save_webhook(self, webhook):
        self.set('webhook', self.cipher.encrypt(webhook.encode()).decode())

    def event(self, order_id, kind, message):
        with self.db() as db:
            db.execute('INSERT INTO events(time,order_id,kind,message) VALUES (?,?,?,?)',(now(),str(order_id) if order_id else None,kind,message))

    def link(self, scope, order_id):
        with self.db() as db:
            row=db.execute('SELECT * FROM links WHERE scope=? AND order_id=?',(scope,str(order_id))).fetchone()
            return dict(row) if row else None

    def save_link(self, scope, order_id, **values):
        allowed={'deal_id','state','error'}
        if not set(values) <= allowed:
            raise ValueError('Unknown link field')
        with self.db() as db:
            db.execute('INSERT OR IGNORE INTO links(scope,order_id,state,updated_at) VALUES (?,?,?,?)',(scope,str(order_id),'new',now()))
            names=list(values)+['updated_at']
            db.execute('UPDATE links SET '+','.join(n+'=?' for n in names)+' WHERE scope=? AND order_id=?',[*values.values(),now(),scope,str(order_id)])

    def publication(self, scope, order_id, digest):
        with self.db() as db:
            row=db.execute('SELECT * FROM publications WHERE scope=? AND order_id=? AND digest=?',(scope,str(order_id),digest)).fetchone()
            return dict(row) if row else None

    def save_publication(self, scope, order_id, digest, state, comment_id=None):
        with self.db() as db:
            db.execute('INSERT INTO publications VALUES (?,?,?,?,?,?) ON CONFLICT(scope,order_id,digest) DO UPDATE SET state=excluded.state, comment_id=excluded.comment_id, updated_at=excluded.updated_at', (scope,str(order_id),digest,state,comment_id,now()))


_store=None
def store():
    global _store
    if _store is None:
        _store=Store(Path(os.environ['FASAD_CONNECT_DATA']))
    return _store
