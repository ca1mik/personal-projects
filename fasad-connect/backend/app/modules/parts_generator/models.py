from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base_class import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Part(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "parts"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id"), index=True)
    part_code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255))
    length: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    width: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    thickness: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column(default=1)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"))
    grain_direction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rotation_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    barcode: Mapped[str | None] = mapped_column(String(255), nullable=True)
    label_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order] = relationship(back_populates="parts")
    order_item: Mapped[OrderItem] = relationship(back_populates="parts")
    material: Mapped[Material] = relationship()
    edges: Mapped[list[PartEdge]] = relationship(
        back_populates="part",
        cascade="all, delete-orphan",
    )
    operations: Mapped[list[PartOperation]] = relationship(
        back_populates="part",
        cascade="all, delete-orphan",
    )


class PartEdge(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "part_edges"

    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"), index=True)
    side: Mapped[str] = mapped_column(String(20))
    edge_material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("edge_materials.id"))
    thickness: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    length_mm: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    part: Mapped[Part] = relationship(back_populates="edges")
    edge_material: Mapped[EdgeMaterial] = relationship()


class PartOperation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "part_operations"

    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"), index=True)
    operation_type: Mapped[str] = mapped_column(String(50))
    x: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    y: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    z: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    diameter: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    depth: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    width: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    height: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    angle: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)

    part: Mapped[Part] = relationship(back_populates="operations")
