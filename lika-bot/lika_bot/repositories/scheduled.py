from __future__ import annotations

from lika_bot.db.database import Database
from lika_bot.utils.time import utcnow_iso


class ScheduledNotificationsRepository:
    """Stores planned and delivered story notifications."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def mark_pending(self, user_id: int, notification_key: str, scheduled_for: str) -> None:
        existing = await self._db.fetchone(
            """
            SELECT status
            FROM scheduled_notifications
            WHERE user_id = ? AND notification_key = ?
            """,
            (user_id, notification_key),
        )
        if existing is not None and existing["status"] == "sent":
            return

        await self._db.execute(
            """
            INSERT INTO scheduled_notifications (user_id, notification_key, scheduled_for, status)
            VALUES (?, ?, ?, 'pending')
            ON CONFLICT(user_id, notification_key) DO UPDATE SET
                scheduled_for = excluded.scheduled_for,
                status = 'pending',
                error_text = NULL
            """,
            (user_id, notification_key, scheduled_for),
        )

    async def was_sent(self, user_id: int, notification_key: str) -> bool:
        row = await self._db.fetchone(
            """
            SELECT 1
            FROM scheduled_notifications
            WHERE user_id = ? AND notification_key = ? AND status = 'sent'
            """,
            (user_id, notification_key),
        )
        return row is not None

    async def mark_sent(self, user_id: int, notification_key: str, scheduled_for: str) -> None:
        await self._db.execute(
            """
            INSERT INTO scheduled_notifications (
                user_id, notification_key, scheduled_for, sent_at, status, error_text
            )
            VALUES (?, ?, ?, ?, 'sent', NULL)
            ON CONFLICT(user_id, notification_key) DO UPDATE SET
                scheduled_for = excluded.scheduled_for,
                sent_at = excluded.sent_at,
                status = 'sent',
                error_text = NULL
            """,
            (user_id, notification_key, scheduled_for, utcnow_iso()),
        )

    async def mark_failed(
        self,
        user_id: int,
        notification_key: str,
        scheduled_for: str,
        error_text: str,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO scheduled_notifications (
                user_id, notification_key, scheduled_for, status, error_text
            )
            VALUES (?, ?, ?, 'failed', ?)
            ON CONFLICT(user_id, notification_key) DO UPDATE SET
                scheduled_for = excluded.scheduled_for,
                status = 'failed',
                error_text = excluded.error_text
            """,
            (user_id, notification_key, scheduled_for, error_text[:500]),
        )

    async def count_sent(self, user_id: int) -> int:
        value = await self._db.fetchval(
            """
            SELECT COUNT(*)
            FROM scheduled_notifications
            WHERE user_id = ? AND status = 'sent'
            """,
            (user_id,),
        )
        return int(value or 0)
