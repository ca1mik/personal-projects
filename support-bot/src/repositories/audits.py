from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from src.models import AuditEvent
from src.repositories.base import SQLAlchemyRepository


class AuditEventRepository(SQLAlchemyRepository):
    async def create(
        self,
        *,
        category: str,
        action: str,
        user_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            user_id=user_id,
            category=category,
            action=action,
            payload=(
                json.dumps(payload, ensure_ascii=False) if payload is not None else None
            ),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_recent(
        self,
        *,
        limit: int = 100,
        category: str | None = None,
        user_id: int | None = None,
    ) -> list[AuditEvent]:
        query = select(AuditEvent)
        if category:
            query = query.where(AuditEvent.category == category)
        if user_id is not None:
            query = query.where(AuditEvent.user_id == user_id)
        query = query.order_by(AuditEvent.id.desc()).limit(limit)
        return list(await self.session.scalars(query))
