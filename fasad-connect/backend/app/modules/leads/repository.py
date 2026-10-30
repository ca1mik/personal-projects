from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.leads.models import Lead
from app.modules.users.models import User


class LeadRepository:
    @staticmethod
    def get_by_id(db: Session, lead_id: uuid.UUID) -> Lead | None:
        stmt = (
            select(Lead)
            .options(
                selectinload(Lead.attachments),
                # заказы нужны для сводки на карточке: сумма и «уже в заказе»
                selectinload(Lead.orders),
                joinedload(Lead.client),
                joinedload(Lead.direction),
                joinedload(Lead.assigned_manager).joinedload(User.role),
            )
            .where(Lead.id == lead_id)
        )
        return db.scalar(stmt)

    @staticmethod
    def get_by_external_message(
        db: Session,
        source_channel: str,
        external_message_id: str,
    ) -> Lead | None:
        stmt = (
            select(Lead)
            .options(selectinload(Lead.attachments), joinedload(Lead.client))
            .where(
                Lead.source_channel == source_channel,
                Lead.external_message_id == external_message_id,
            )
        )
        return db.scalar(stmt)

    @staticmethod
    def next_order_counter(db: Session) -> int:
        return int(db.scalar(select(func.count()).select_from(Lead)) or 0) + 1
