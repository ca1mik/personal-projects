import sqlite3
from pathlib import Path
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  user_id INTEGER NOT NULL,
  chat_id INTEGER NOT NULL,
  command TEXT NOT NULL,
  ok INTEGER NOT NULL,
  details TEXT
);
"""

class AuditDB:
    def __init__(self, path: Path):
        self.path = str(path)
        self._init()

    def _init(self):
        with sqlite3.connect(self.path) as con:
            con.execute(SCHEMA)
            con.commit()

    def log(self, user_id: int, chat_id: int, command: str, ok: bool, details: str | None = None):
        with sqlite3.connect(self.path) as con:
            con.execute(
                "INSERT INTO audit(ts,user_id,chat_id,command,ok,details) VALUES(?,?,?,?,?,?)",
                (datetime.utcnow().isoformat(), user_id, chat_id, command, 1 if ok else 0, details),
            )
            con.commit()
