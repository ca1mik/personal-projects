from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
import json, sqlite3


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            INSERT OR IGNORE INTO settings VALUES('mode','healthy');
            CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY,marker TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,email TEXT NOT NULL,at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,marker TEXT NOT NULL UNIQUE,
              mode TEXT NOT NULL,status TEXT NOT NULL,started TEXT NOT NULL,finished TEXT,
              result TEXT NOT NULL DEFAULT '{}');
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON runs(status) WHERE status='running';
            ''')

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def mode(self):
        with self.db() as c:
            return c.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]

    def receipt(self, marker):
        with self.db() as c:
            r = c.execute('SELECT id,marker,at FROM leads WHERE marker=?', (marker,)).fetchone()
            return dict(r) if r else None

    def runs(self):
        with self.db() as c:
            return [{**dict(r), 'result': json.loads(r['result'])}
                    for r in c.execute('SELECT * FROM runs ORDER BY id DESC LIMIT 30')]

    def finish(self, ident, result):
        with self.db() as c:
            c.execute("UPDATE runs SET status=?,finished=?,result=? WHERE id=? AND status='running'",
                      (result['status'], now(), json.dumps(result, ensure_ascii=False), ident))
