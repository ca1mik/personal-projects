"""
Persistent memory for user context and autonomous research notes.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


class ChatMemory:
    def __init__(self, db_path: Path = Path("claw_memory.db")):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_context (
                    user_id INTEGER PRIMARY KEY,
                    name TEXT,
                    interests TEXT,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_facts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS proactive_reports (
                    id INTEGER PRIMARY KEY,
                    topic TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    sources_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def add_message(self, user_id: int, chat_id: int, role: str, message: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO chat_history (user_id, chat_id, role, message) VALUES (?, ?, ?, ?)",
                (user_id, chat_id, role, message),
            )
            conn.commit()

    def get_history(self, user_id: int, chat_id: int, limit: int = 10) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT role, message, timestamp FROM chat_history
                WHERE user_id = ? AND chat_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (user_id, chat_id, limit),
            ).fetchall()
            return [dict(row) for row in reversed(rows)]

    def remember_fact(
        self,
        user_id: int,
        chat_id: int,
        category: str,
        key: str,
        value: str,
        source: str = "dialog",
    ) -> bool:
        cleaned = (value or "").strip()
        if not cleaned:
            return False
        with sqlite3.connect(self.db_path) as conn:
            last = conn.execute(
                """
                SELECT value FROM memory_facts
                WHERE user_id=? AND chat_id=? AND category=? AND key=?
                ORDER BY id DESC LIMIT 1
                """,
                (user_id, chat_id, category, key),
            ).fetchone()
            if last and str(last[0]).strip().lower() == cleaned.lower():
                return False
            conn.execute(
                """
                INSERT INTO memory_facts (user_id, chat_id, category, key, value, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, chat_id, category, key, cleaned, source),
            )
            conn.commit()
        return True

    def list_facts(
        self,
        user_id: int,
        chat_id: int,
        category: str | None = None,
        limit: int = 30,
    ) -> list[dict]:
        sql = (
            "SELECT category,key,value,source,created_at FROM memory_facts "
            "WHERE user_id=? AND chat_id=? "
        )
        args: list[Any] = [user_id, chat_id]
        if category:
            sql += "AND category=? "
            args.append(category)
        sql += "ORDER BY id DESC LIMIT ?"
        args.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, tuple(args)).fetchall()
            return [dict(row) for row in rows]

    def summarize_profile(self, user_id: int, chat_id: int, max_lines: int = 10) -> str:
        facts = self.list_facts(user_id, chat_id, limit=100)
        if not facts:
            return "No saved profile facts yet."
        latest_by_key: dict[tuple[str, str], str] = {}
        for item in facts:
            key = (item["category"], item["key"])
            if key not in latest_by_key:
                latest_by_key[key] = item["value"]
        lines: list[str] = []
        for (category, key), value in latest_by_key.items():
            lines.append(f"- {category}.{key}: {value}")
            if len(lines) >= max_lines:
                break
        return "Known user context:\n" + "\n".join(lines)

    def get_context_summary(self, user_id: int, chat_id: int) -> str:
        history = self.get_history(user_id, chat_id, limit=5)
        profile = self.summarize_profile(user_id, chat_id, max_lines=6)
        if not history:
            return profile
        chunks = [profile, "", "Recent messages:"]
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            chunks.append(f"{role}: {msg['message'][:140]}")
        return "\n".join(chunks)

    def set_user_context(self, user_id: int, name: str | None = None, interests: list[str] | None = None):
        interests_json = _to_json(interests or [])
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_context (user_id, name, interests) VALUES (?, ?, ?)",
                (user_id, name, interests_json),
            )
            conn.commit()

    def get_user_context(self, user_id: int) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT name, interests, metadata FROM user_context WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                return {"name": None, "interests": [], "metadata": {}}
            return {
                "name": row["name"],
                "interests": json.loads(row["interests"] or "[]"),
                "metadata": json.loads(row["metadata"] or "{}"),
            }

    def add_interest(self, user_id: int, interest: str):
        context = self.get_user_context(user_id)
        interests = context["interests"]
        if interest not in interests:
            interests.append(interest)
        self.set_user_context(user_id, context["name"], interests)

    def clear_old_messages(self, days: int = 30):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                DELETE FROM chat_history
                WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days')
                """,
                (days,),
            )
            conn.commit()

    def add_proactive_report(self, topic: str, summary: str, sources: list[str] | None = None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO proactive_reports (topic, summary, sources_json)
                VALUES (?, ?, ?)
                """,
                (topic, summary, _to_json(sources or [])),
            )
            conn.commit()

    def list_recent_reports(self, limit: int = 10) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT topic, summary, sources_json, created_at
                FROM proactive_reports
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            out: list[dict] = []
            for row in rows:
                item = dict(row)
                item["sources"] = json.loads(item.pop("sources_json") or "[]")
                out.append(item)
            return out

    def auto_extract_facts(self, text: str) -> list[dict]:
        lowered = text.lower().strip()
        facts: list[dict] = []

        patterns: list[tuple[str, str, str]] = [
            (r"\b(?:меня зовут|my name is|i am)\s+([a-zа-яё\- ]{2,40})", "profile", "name"),
            (r"\b(?:я живу в|живу в|i live in)\s+([a-zа-яё\- ]{2,60})", "profile", "location"),
            (r"\b(?:я работаю|работаю в|i work in|i work at)\s+(.{2,80})", "profile", "work"),
            (r"\b(?:я люблю|мне нравится|i like)\s+(.{2,80})", "preferences", "likes"),
            (r"\b(?:я не люблю|терпеть не могу|i dislike)\s+(.{2,80})", "preferences", "dislikes"),
            (r"\b(?:моя цель|цель на этот год|my goal)\s+(.{2,120})", "goals", "primary_goal"),
        ]

        for pattern, category, key in patterns:
            match = re.search(pattern, lowered, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip(" .,!?:;")
            if key == "name":
                value = re.split(r"\s(?:и|а)\s|[,.;]", value, maxsplit=1)[0].strip()
                value = " ".join(value.split()[:3])
            if value:
                facts.append({"category": category, "key": key, "value": value})

        if any(marker in lowered for marker in ["встреча", "meeting", "созвон", "call"]):
            facts.append(
                {
                    "category": "plans",
                    "key": "latest_meeting_request",
                    "value": text[:220],
                }
            )
        return facts

    def auto_extract_and_store(self, user_id: int, chat_id: int, text: str, source: str = "dialog") -> list[dict]:
        extracted = self.auto_extract_facts(text)
        saved: list[dict] = []
        for item in extracted:
            stored = self.remember_fact(
                user_id=user_id,
                chat_id=chat_id,
                category=item["category"],
                key=item["key"],
                value=item["value"],
                source=source,
            )
            if stored:
                saved.append(item)
        return saved

    def export_snapshot(
        self,
        out_path: Path,
        user_id: int | None = None,
        chat_id: int | None = None,
        limit: int = 200,
    ) -> Path:
        payload: dict[str, Any] = {}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            history_sql = "SELECT user_id,chat_id,role,message,timestamp FROM chat_history"
            facts_sql = "SELECT user_id,chat_id,category,key,value,source,created_at FROM memory_facts"
            args: list[Any] = []
            where: list[str] = []
            if user_id is not None:
                where.append("user_id=?")
                args.append(user_id)
            if chat_id is not None:
                where.append("chat_id=?")
                args.append(chat_id)
            if where:
                clause = " WHERE " + " AND ".join(where)
                history_sql += clause
                facts_sql += clause
            history_sql += " ORDER BY id DESC LIMIT ?"
            facts_sql += " ORDER BY id DESC LIMIT ?"
            args_with_limit = [*args, limit]
            history = [dict(x) for x in conn.execute(history_sql, tuple(args_with_limit)).fetchall()]
            facts = [dict(x) for x in conn.execute(facts_sql, tuple(args_with_limit)).fetchall()]
            reports = [dict(x) for x in conn.execute("SELECT topic,summary,sources_json,created_at FROM proactive_reports ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
            for item in reports:
                item["sources"] = json.loads(item.pop("sources_json") or "[]")
            payload = {"history": history, "facts": facts, "reports": reports}

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out_path


_memory_instance: ChatMemory | None = None


def get_memory(db_path: Path = Path("claw_memory.db")) -> ChatMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ChatMemory(db_path)
    return _memory_instance
