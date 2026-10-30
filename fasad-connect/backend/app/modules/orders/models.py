from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base_class import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    direction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("production_directions.id"),
        nullable=True,
        index=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    manager_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_statuses.id"), index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    final_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Текстура материала запрещает поворот детали при раскрое: у текстурной плёнки
    # рисунок пойдёт поперёк. По умолчанию текстуры нет — раскрой волен вращать
    # деталь и экономить лист.
    has_texture: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )
    # Прямой запрет поворота, отдельно от текстуры. Заказчик: «сделай сразу в
    # самом заказе „нельзя поворачивать“». Причина не всегда в текстуре —
    # бывает направление шлифовки, рисунок фрезы, требование клиента. Раскрой
    # не вращает деталь, если стоит любой из двух признаков.
    no_rotation: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )
    source_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id"),
        nullable=True,
        index=True,
    )
    # Доп. заказ к основному: клиент довёз замер, добавил фасады взамен
    # испорченных, попросил доборы. Деньги и отгрузка у допа свои, но в списке
    # он висит под родителем — «заказ 1024 (2 доп. заказа)».
    parent_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id"),
        nullable=True,
        index=True,
    )
    additional_orders: Mapped[list[Order]] = relationship(
        back_populates="parent_order",
        foreign_keys="Order.parent_order_id",
        order_by="Order.created_at.asc()",
    )
    parent_order: Mapped[Order | None] = relationship(
        back_populates="additional_orders",
        foreign_keys="Order.parent_order_id",
        remote_side="Order.id",
    )
    # Срок сдачи, названный клиенту. Приезжает из заявки и дальше правится по
    # заказу: заказ живёт дольше заявки, его переносят.
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    # Материал на этот заказ уже заказан поставщику. Раньше студия помечала это
    # заливкой ячейки в экселе: заливку не отфильтруешь и не спросишь «что ещё
    # не заказано», а спрашивают это каждый день.
    material_ordered: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
        index=True,
    )
    material_ordered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    production_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped[Client] = relationship(back_populates="orders")
    direction: Mapped[ProductionDirection | None] = relationship("ProductionDirection")
    manager: Mapped[User] = relationship()
    status: Mapped[OrderStatus] = relationship(back_populates="orders")
    source_lead: Mapped[Lead | None] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    status_history: Mapped[list[OrderStatusHistory]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    parts: Mapped[list[Part]] = relationship(back_populates="order")
    stage_instances: Mapped[list[OrderStageInstance]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    positions: Mapped[list[OrderPosition]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderPosition.line_no.asc()",
    )
    payments: Mapped[list[OrderPayment]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderPayment.paid_at.asc()",
    )


class OrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_templates.id"),
        nullable=True,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    width: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    height: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    depth: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column(default=1)
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), nullable=True)
    facade_material_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("materials.id"),
        nullable=True,
    )
    thickness: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    order: Mapped[Order] = relationship(back_populates="items")
    template: Mapped[ProductTemplate | None] = relationship(back_populates="order_items")
    material: Mapped[Material | None] = relationship(foreign_keys=[material_id])
    facade_material: Mapped[Material | None] = relationship(foreign_keys=[facade_material_id])
    parts: Mapped[list[Part]] = relationship(back_populates="order_item")


class OrderPosition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Строка сметы заказа: что делаем, сколько и почём.

    Отдельно от ``OrderItem``: тот описывает изделие из каталога (ширина, высота,
    глубина, шаблон), а у фасадов каталога нет — есть строка «фрезеровка такая-то,
    столько-то м², по такой-то цене».

    Цена копируется из справочника **в момент добавления** и дальше живёт своей
    жизнью. Заказчик: «все последующие заказы будут с новой стоимостью и старые
    мы не трогаем никак». Ссылка ``price_item_id`` остаётся, но она — только
    происхождение строки, пересчёт по ней не делается.
    """

    __tablename__ = "order_positions"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    line_no: Mapped[int] = mapped_column(Integer, default=1)
    price_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("price_items.id"),
        nullable=True,
        index=True,
    )
    # Нестандарт: артикула в справочнике нет, цену менеджер пишет руками. В
    # справочник такая строка не попадает — иначе разовая договорённость станет
    # прайсом для всех.
    is_custom: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )
    article: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(50), default="other", index=True)
    unit: Mapped[str] = mapped_column(String(20), default="sqm")
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("1"))
    width: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    height: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    area_sqm: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=Decimal("0"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    # Цена поправлена руками поверх справочника: «индивидуальная цена под
    # заказ». Справочник при этом не меняется — правка живёт только здесь.
    price_overridden: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )
    # Цена по прайсу на момент продажи. Через полгода прайс будет другой, и без
    # этой копии нельзя ответить, была ли скидка или просто подорожание.
    base_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    thickness: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    color: Mapped[str | None] = mapped_column(String(255), nullable=True)
    milling: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order] = relationship(back_populates="positions")
    price_item: Mapped[PriceItem | None] = relationship()


class OrderPayment(UUIDPrimaryKeyMixin, Base):
    """Приход денег по заказу.

    Баланс заказа — сумма приходов минус сумма сметы. Плюс значит аванс или
    переплату, минус — долг клиента.
    """

    __tablename__ = "order_payments"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    method: Mapped[str] = mapped_column(String(30), default="cash", index=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    order: Mapped[Order] = relationship(back_populates="payments")
