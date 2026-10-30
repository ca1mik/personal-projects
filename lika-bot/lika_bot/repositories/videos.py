from __future__ import annotations

from collections.abc import Sequence

from lika_bot.db.database import Database
from lika_bot.models.entities import CategoryOverview, VideoRecord
from lika_bot.utils.time import utcnow_iso


def _map_video(row: object) -> VideoRecord | None:
    if row is None:
        return None
    return VideoRecord(
        id=int(row["id"]),
        category=row["category"],
        title=row["title"],
        relative_path=row["relative_path"],
        is_active=bool(row["is_active"]),
        detected_at=row["detected_at"],
        last_seen_at=row["last_seen_at"],
    )


class VideosRepository:
    """Persistence for scanned videos and delivery history."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def register_video(
        self,
        category: str,
        relative_path: str,
        title: str,
        detected_at: str,
        last_seen_at: str,
    ) -> tuple[bool, bool]:
        existing = await self._db.fetchone(
            "SELECT id, is_active FROM videos WHERE relative_path = ?",
            (relative_path,),
        )
        if existing is None:
            await self._db.execute(
                """
                INSERT INTO videos (category, title, relative_path, is_active, detected_at, last_seen_at)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (category, title, relative_path, detected_at, last_seen_at),
            )
            return True, False

        was_inactive = not bool(existing["is_active"])
        await self._db.execute(
            """
            UPDATE videos
            SET category = ?, title = ?, is_active = 1, last_seen_at = ?
            WHERE relative_path = ?
            """,
            (category, title, last_seen_at, relative_path),
        )
        return False, was_inactive

    async def deactivate_missing(self, known_paths: set[str]) -> int:
        if not known_paths:
            cursor = await self._db.execute("UPDATE videos SET is_active = 0 WHERE is_active = 1")
            return int(cursor.rowcount or 0)

        placeholders = ", ".join("?" for _ in known_paths)
        cursor = await self._db.execute(
            f"UPDATE videos SET is_active = 0 WHERE is_active = 1 AND relative_path NOT IN ({placeholders})",
            tuple(known_paths),
        )
        return int(cursor.rowcount or 0)

    async def count_active(
        self,
        category: str | None = None,
        excluded_categories: Sequence[str] = (),
    ) -> int:
        where_clause, parameters = self._build_scope_clause("videos", category, excluded_categories)
        value = await self._db.fetchval(f"SELECT COUNT(*) FROM videos WHERE {where_clause}", parameters)
        return int(value or 0)

    async def count_sent(
        self,
        user_id: int,
        excluded_categories: Sequence[str] = (),
    ) -> int:
        clauses = ["sv.user_id = ?"]
        parameters: list[object] = [user_id]
        if excluded_categories:
            placeholders = ", ".join("?" for _ in excluded_categories)
            clauses.append(f"v.category NOT IN ({placeholders})")
            parameters.extend(excluded_categories)

        value = await self._db.fetchval(
            f"""
            SELECT COUNT(*)
            FROM sent_videos sv
            JOIN videos v ON v.id = sv.video_id
            WHERE {' AND '.join(clauses)}
            """,
            tuple(parameters),
        )
        return int(value or 0)

    async def count_remaining_for_user(
        self,
        user_id: int,
        category: str | None = None,
        excluded_categories: Sequence[str] = (),
    ) -> int:
        where_clause, scope_params = self._build_scope_clause("v", category, excluded_categories)
        value = await self._db.fetchval(
            f"""
            SELECT COUNT(*)
            FROM videos v
            LEFT JOIN sent_videos sv ON sv.video_id = v.id AND sv.user_id = ?
            WHERE {where_clause} AND sv.id IS NULL
            """,
            (user_id, *scope_params),
        )
        return int(value or 0)

    async def get_random_unsent_for_user(
        self,
        user_id: int,
        category: str | None = None,
        excluded_categories: Sequence[str] = (),
    ) -> VideoRecord | None:
        where_clause, scope_params = self._build_scope_clause("v", category, excluded_categories)
        row = await self._db.fetchone(
            f"""
            SELECT v.*
            FROM videos v
            LEFT JOIN sent_videos sv ON sv.video_id = v.id AND sv.user_id = ?
            WHERE {where_clause} AND sv.id IS NULL
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (user_id, *scope_params),
        )
        return _map_video(row)

    async def mark_sent(self, user_id: int, video_id: int, source: str) -> None:
        await self._db.execute(
            """
            INSERT OR IGNORE INTO sent_videos (user_id, video_id, source, sent_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, video_id, source, utcnow_iso()),
        )

    async def list_categories_with_counts(
        self,
        user_id: int,
        excluded_categories: Sequence[str] = (),
    ) -> list[CategoryOverview]:
        clauses = ["v.is_active = 1"]
        parameters: list[object] = [user_id]
        if excluded_categories:
            placeholders = ", ".join("?" for _ in excluded_categories)
            clauses.append(f"v.category NOT IN ({placeholders})")
            parameters.extend(excluded_categories)

        rows = await self._db.fetchall(
            f"""
            SELECT
                v.category AS category,
                COUNT(*) AS total,
                SUM(CASE WHEN sv.id IS NULL THEN 1 ELSE 0 END) AS remaining
            FROM videos v
            LEFT JOIN sent_videos sv ON sv.video_id = v.id AND sv.user_id = ?
            WHERE {' AND '.join(clauses)}
            GROUP BY v.category
            ORDER BY v.category
            """,
            tuple(parameters),
        )
        return [
            CategoryOverview(
                category=row["category"],
                title=row["category"],
                total=int(row["total"]),
                remaining=int(row["remaining"] or 0),
            )
            for row in rows
        ]

    def _build_scope_clause(
        self,
        alias: str,
        category: str | None,
        excluded_categories: Sequence[str],
    ) -> tuple[str, list[object]]:
        clauses = [f"{alias}.is_active = 1"]
        parameters: list[object] = []

        if category is not None:
            clauses.append(f"{alias}.category = ?")
            parameters.append(category)
        elif excluded_categories:
            placeholders = ", ".join("?" for _ in excluded_categories)
            clauses.append(f"{alias}.category NOT IN ({placeholders})")
            parameters.extend(excluded_categories)

        return " AND ".join(clauses), parameters
