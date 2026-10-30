from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ProductionDirection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Производственное направление: эмаль, ПВХ, шпон.

    Справочник, а не enum: заказчик добавляет направление сам, без правки кода.
    ``number_suffix`` формирует номер заказа — по ТЗ эмаль идёт без буквы,
    ПВХ с «П», шпон с «Ш».
    """

    __tablename__ = "production_directions"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    number_suffix: Mapped[str] = mapped_column(String(10), default="")
    # Сколько площади материала уходит на 1 м² фасада. ПВХ клеится с двух
    # сторон — коэффициент 2. Без него отчёт «в м²» расходится с реальным
    # расходом плёнки вдвое.
    material_area_factor: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("1.000"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
