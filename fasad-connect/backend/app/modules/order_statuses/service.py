from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.modules.order_statuses.models import OrderStatus


class OrderStatusService:
    @staticmethod
    def get_by_code(db: Session, code: str) -> OrderStatus:
        status = db.scalar(select(OrderStatus).where(OrderStatus.code == code))
        if not status:
            raise NotFoundError(f"Order status '{code}' not found")
        return status

    @staticmethod
    def get_start_status(db: Session) -> OrderStatus:
        return OrderStatusService.get_by_code(db, "new")
