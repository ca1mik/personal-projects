from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.mixins import UUIDPrimaryKeyMixin, utcnow


class OrderStatus(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "order_statuses"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)

    orders: Mapped[list[Order]] = relationship(back_populates="status")


class OrderStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    old_status_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("order_statuses.id"),
        nullable=True,
    )
    new_status_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_statuses.id"))
    changed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order] = relationship(back_populates="status_history")
    old_status: Mapped[OrderStatus | None] = relationship(foreign_keys=[old_status_id])
    new_status: Mapped[OrderStatus] = relationship(foreign_keys=[new_status_id])
