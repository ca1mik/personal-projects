from __future__ import annotations

from lika_bot.db.database import Database
from lika_bot.utils.time import utcnow_iso


class ProgressRepository:
    """Keeps personal scenario progress and hidden-section milestones."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def ensure_row(self, user_id: int) -> None:
        now = utcnow_iso()
        await self._db.execute(
            """
            INSERT OR IGNORE INTO messages_progress (user_id, created_at, updated_at)
            VALUES (?, ?, ?)
            """,
            (user_id, now, now),
        )

    async def get_state(self, user_id: int) -> dict[str, str | None]:
        await self.ensure_row(user_id)
        row = await self._db.fetchone(
            "SELECT * FROM messages_progress WHERE user_id = ?",
            (user_id,),
        )
        if row is None:
            return {
                "intro_seen_at": None,
                "special_opened_at": None,
                "final_opened_at": None,
            }
        return {
            "intro_seen_at": row["intro_seen_at"],
            "special_opened_at": row["special_opened_at"],
            "final_opened_at": row["final_opened_at"],
        }

    async def mark_intro_seen(self, user_id: int) -> None:
        await self.ensure_row(user_id)
        now = utcnow_iso()
        await self._db.execute(
            """
            UPDATE messages_progress
            SET intro_seen_at = COALESCE(intro_seen_at, ?), updated_at = ?
            WHERE user_id = ?
            """,
            (now, now, user_id),
        )

    async def mark_special_opened(self, user_id: int) -> None:
        await self.ensure_row(user_id)
        now = utcnow_iso()
        await self._db.execute(
            """
            UPDATE messages_progress
            SET special_opened_at = COALESCE(special_opened_at, ?), updated_at = ?
            WHERE user_id = ?
            """,
            (now, now, user_id),
        )

    async def mark_final_opened(self, user_id: int) -> None:
        await self.ensure_row(user_id)
        now = utcnow_iso()
        await self._db.execute(
            """
            UPDATE messages_progress
            SET final_opened_at = COALESCE(final_opened_at, ?), updated_at = ?
            WHERE user_id = ?
            """,
            (now, now, user_id),
        )

    async def get_current_personal_cycle(self, user_id: int) -> int:
        value = await self._db.fetchval(
            "SELECT COALESCE(MAX(cycle), 1) FROM personal_messages_progress WHERE user_id = ?",
            (user_id,),
        )
        return int(value or 1)

    async def get_seen_personal_message_keys(self, user_id: int, cycle: int) -> set[str]:
        rows = await self._db.fetchall(
            """
            SELECT message_key
            FROM personal_messages_progress
            WHERE user_id = ? AND cycle = ?
            ORDER BY delivered_at ASC
            """,
            (user_id, cycle),
        )
        return {row["message_key"] for row in rows}

    async def record_personal_message(self, user_id: int, message_key: str, cycle: int) -> None:
        await self._db.execute(
            """
            INSERT OR IGNORE INTO personal_messages_progress (user_id, message_key, cycle, delivered_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, message_key, cycle, utcnow_iso()),
        )

    async def count_unique_personal_messages(self, user_id: int) -> int:
        value = await self._db.fetchval(
            """
            SELECT COUNT(DISTINCT message_key)
            FROM personal_messages_progress
            WHERE user_id = ?
            """,
            (user_id,),
        )
        return int(value or 0)
