from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class PriceItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Артикул со стоимостью: фрезеровка, шпон, мыло, плита, услуга.

    Заказчик: «нужна база артикулов, чтобы цена сама подтягивалась». Справочник
    заполняется руками из админки — из заказов сюда ничего не попадает, иначе
    разовый нестандарт засорит базу и в следующий раз подставится случайная
    цена.
    """

    __tablename__ = "price_items"

    # Номер артикула уникален внутри типа, а не на весь справочник: в каталоге
    # студии 127-й существует и в плёнке, и в эмали — один рисунок в двух
    # покрытиях, с разной ценой. Ограничение живёт индексом
    # `uq_price_items_kind_article` (миграция 0015).
    article: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255))
    # Тип работы: по нему отчёты группируют выручку («сколько прошло фрезеровки
    # за месяц») и раскрой делит карты. Строка, а не enum: заказчик добавляет
    # новый тип из админки, без правки кода и миграции.
    kind: Mapped[str] = mapped_column(String(50), index=True, default="other")
    # Единица считает сумму: «sqm» — цена за м², всё остальное — за штуку или
    # погонный метр. От этого зависит, что умножать на цену.
    unit: Mapped[str] = mapped_column(String(20), default="sqm")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    price_changes: Mapped[list[PriceItemChange]] = relationship(
        back_populates="price_item",
        cascade="all, delete-orphan",
        order_by="PriceItemChange.changed_at.desc()",
    )


class PriceItemChange(UUIDPrimaryKeyMixin, Base):
    """История изменения цены артикула.

    Нужна, чтобы ответить «почему в июньском заказе была другая цена». Сам
    заказ цену не пересчитывает — он хранит свою копию, — но менеджеру надо
    видеть, когда и на сколько справочник подорожал.
    """

    __tablename__ = "price_item_changes"

    price_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_items.id", ondelete="CASCADE"),
        index=True,
    )
    old_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    new_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    price_item: Mapped[PriceItem] = relationship(back_populates="price_changes")
