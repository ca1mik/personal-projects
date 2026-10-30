"""
Модуль для хранения и поиска контактов пользователя (email, имя, заметки).
"""
import sqlite3
from pathlib import Path
from typing import Optional
import json

class ContactsDB:
    def __init__(self, db_path: Path = Path("claw_contacts.db")):
        self.db_path = db_path
        self._init_db()
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    email TEXT UNIQUE,
                    notes TEXT,
                    created DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    def add_contact(self, name: Optional[str], email: str, notes: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO contacts (name, email, notes) VALUES (?, ?, ?)",
                (name, email, notes)
            )
            conn.commit()
    def get_contact_by_email(self, email: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM contacts WHERE email = ?", (email,)).fetchone()
            if row:
                return dict(row)
            return None
    def search_contacts(self, query: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM contacts WHERE name LIKE ? OR email LIKE ? OR notes LIKE ? ORDER BY created DESC LIMIT 20",
                (f"%{query}%", f"%{query}%", f"%{query}%")
            ).fetchall()
            return [dict(row) for row in rows]
    def all_contacts(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM contacts ORDER BY created DESC LIMIT 100").fetchall()
            return [dict(row) for row in rows]
_contacts_instance = None
def get_contacts(db_path: Path = Path("claw_contacts.db")) -> ContactsDB:
    global _contacts_instance
    if _contacts_instance is None:
        _contacts_instance = ContactsDB(db_path)
    return _contacts_instance
