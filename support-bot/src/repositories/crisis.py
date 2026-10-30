from __future__ import annotations

from sqlalchemy import select

from src.models import CrisisIncident
from src.repositories.base import SQLAlchemyRepository


class CrisisRepository(SQLAlchemyRepository):
    async def create(
        self, *, user_id: int, message: str, detected_reason: str
    ) -> CrisisIncident:
        incident = CrisisIncident(
            user_id=user_id, message=message, detected_reason=detected_reason
        )
        self.session.add(incident)
        await self.session.flush()
        return incident

    async def list_recent(self, limit: int = 100) -> list[CrisisIncident]:
        query = select(CrisisIncident).order_by(CrisisIncident.id.desc()).limit(limit)
        return list(await self.session.scalars(query))
