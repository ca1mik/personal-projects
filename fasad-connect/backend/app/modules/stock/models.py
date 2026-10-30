from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.mixins import UUIDPrimaryKeyMixin, utcnow


class StockItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_items"

    material_type: Mapped[str] = mapped_column(String(50), index=True)
    material_id: Mapped[uuid.UUID] = mapped_column(index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    unit: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    movements: Mapped[list[StockMovement]] = relationship(
        back_populates="stock_item",
        cascade="all, delete-orphan",
    )


class StockMovement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_movements"

    stock_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stock_items.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(50))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    stock_item: Mapped[StockItem] = relationship(back_populates="movements")
