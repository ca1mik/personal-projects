from __future__ import annotations

from sqlalchemy import select

from src.models import DeletionRequest, DeletionRequestStatus
from src.repositories.base import SQLAlchemyRepository


class DeletionRequestRepository(SQLAlchemyRepository):
    async def create_pending(self, user_id: int) -> DeletionRequest:
        request = DeletionRequest(user_id=user_id, status=DeletionRequestStatus.PENDING)
        self.session.add(request)
        await self.session.flush()
        return request

    async def list_recent(self, limit: int = 100) -> list[DeletionRequest]:
        query = select(DeletionRequest).order_by(DeletionRequest.id.desc()).limit(limit)
        return list(await self.session.scalars(query))
