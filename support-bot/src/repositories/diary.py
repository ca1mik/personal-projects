from __future__ import annotations

from datetime import datetime

from sqlalchemy import distinct, select

from src.models import DiaryEntry
from src.repositories.base import SQLAlchemyRepository


class DiaryRepository(SQLAlchemyRepository):
    async def create_entry(self, user_id: int, content: str) -> DiaryEntry:
        entry = DiaryEntry(user_id=user_id, content=content)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_entries_since(
        self, user_id: int, since: datetime
    ) -> list[DiaryEntry]:
        query = (
            select(DiaryEntry)
            .where(DiaryEntry.user_id == user_id, DiaryEntry.created_at >= since)
            .order_by(DiaryEntry.created_at.asc())
        )
        return list(await self.session.scalars(query))

    async def list_user_ids_with_entries_since(self, since: datetime) -> list[int]:
        query = select(distinct(DiaryEntry.user_id)).where(
            DiaryEntry.created_at >= since
        )
        return list(await self.session.scalars(query))
