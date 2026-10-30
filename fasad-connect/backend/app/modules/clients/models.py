from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Client(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clients"

    full_name: Mapped[str] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    leads: Mapped[list[Lead]] = relationship(back_populates="client")
    orders: Mapped[list[Order]] = relationship(back_populates="client")


class ClientDepositMovement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "client_deposit_movements"

    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    kind: Mapped[str] = mapped_column(String(20))  # topup, spend, return
    method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("order_payments.id"), nullable=True, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
