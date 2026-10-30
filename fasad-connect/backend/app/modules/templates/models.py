from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base_class import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ProductTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_templates"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    formula_config_json: Mapped[dict] = mapped_column(JSON, default=dict)

    order_items: Mapped[list[OrderItem]] = relationship(back_populates="template")
