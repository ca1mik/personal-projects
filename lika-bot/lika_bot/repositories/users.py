from __future__ import annotations

from aiogram.types import User

from lika_bot.db.database import Database
from lika_bot.models.entities import UserRecord
from lika_bot.utils.time import utcnow_iso


def _map_user(row: object) -> UserRecord | None:
    if row is None:
        return None
    return UserRecord(
        id=int(row["id"]),
        telegram_id=int(row["telegram_id"]),
        chat_id=int(row["chat_id"]),
        username=row["username"],
        first_name=row["first_name"],
        is_primary=bool(row["is_primary"]),
        intro_completed=bool(row["intro_completed"]),
    )


class UsersRepository:
    """Persistence for Telegram users interacting with the gift bot."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def upsert_from_telegram(self, user: User, chat_id: int, is_primary: bool = False) -> UserRecord:
        now = utcnow_iso()
        await self._db.execute(
            """
            INSERT INTO users (
                telegram_id, chat_id, username, first_name, is_primary, first_seen_at, last_seen_at, last_interaction_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                username = excluded.username,
                first_name = COALESCE(excluded.first_name, users.first_name),
                is_primary = CASE WHEN excluded.is_primary = 1 THEN 1 ELSE users.is_primary END,
                last_seen_at = excluded.last_seen_at,
                last_interaction_at = excluded.last_interaction_at
            """,
            (
                user.id,
                chat_id,
                user.username,
                user.first_name,
                int(is_primary),
                now,
                now,
                now,
            ),
        )
        user_record = await self.get_by_telegram_id(user.id)
        if user_record is None:
            raise RuntimeError("Failed to persist Telegram user.")
        return user_record

    async def ensure_system_user(
        self,
        telegram_id: int,
        first_name: str = "Лика",
        is_primary: bool = False,
    ) -> UserRecord:
        now = utcnow_iso()
        await self._db.execute(
            """
            INSERT INTO users (
                telegram_id, chat_id, username, first_name, is_primary, first_seen_at, last_seen_at, last_interaction_at
            )
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                first_name = COALESCE(users.first_name, excluded.first_name),
                is_primary = CASE WHEN excluded.is_primary = 1 THEN 1 ELSE users.is_primary END,
                last_seen_at = excluded.last_seen_at
            """,
            (telegram_id, telegram_id, first_name, int(is_primary), now, now, now),
        )
        user_record = await self.get_by_telegram_id(telegram_id)
        if user_record is None:
            raise RuntimeError("Failed to persist system user.")
        return user_record

    async def get_by_telegram_id(self, telegram_id: int) -> UserRecord | None:
        row = await self._db.fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return _map_user(row)

    async def get_by_id(self, user_id: int) -> UserRecord | None:
        row = await self._db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        return _map_user(row)

    async def mark_intro_completed(self, user_id: int) -> None:
        await self._db.execute(
            "UPDATE users SET intro_completed = 1, last_interaction_at = ? WHERE id = ?",
            (utcnow_iso(), user_id),
        )

    async def touch_last_interaction(self, user_id: int) -> None:
        await self._db.execute(
            "UPDATE users SET last_interaction_at = ? WHERE id = ?",
            (utcnow_iso(), user_id),
        )

    async def count_users(self) -> int:
        value = await self._db.fetchval("SELECT COUNT(*) FROM users")
        return int(value or 0)
