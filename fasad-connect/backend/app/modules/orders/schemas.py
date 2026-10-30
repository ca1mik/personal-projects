from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.modules.clients.schemas import ClientRead
from app.modules.directions.schemas import DirectionSummaryRead
from app.modules.order_statuses.schemas import OrderStatusHistoryRead, OrderStatusRead
from app.modules.shared.schemas import ORMModel
from app.modules.templates.schemas import ProductTemplateRead
from app.modules.users.schemas import UserRead


class OrderCreate(BaseModel):
    client_id: uuid.UUID
    manager_id: uuid.UUID
    status_id: uuid.UUID | None = None
    comment: str | None = None
    source_lead_id: uuid.UUID | None = None
    # Свой номер заказа: студия ведёт нумерацию по своим правилам («44 03 п»).
    # Пусто — номер ставит система сквозной нумерацией, как было.
    order_number: str | None = Field(default=None, max_length=50)
    # Тип работ заявки. Если направление не выбрано, буква номера берётся
    # отсюда: фрезеровка — «Ф», мыло — «М», шпон — «Ш», плёнка — «П».
    work_kind: str | None = Field(default=None, max_length=50)
    # Срок сдачи. Приезжает из заявки — там его назвали клиенту.
    due_date: date | None = None
    # Направление можно передать идентификатором или кодом («enamel», «pvc», «veneer»).
    direction_id: uuid.UUID | None = None
    direction_code: str | None = None
    # Текстурный материал нельзя вращать при раскрое. Умолчание «нет текстуры»
    # сохраняет поведение старых клиентов, которые это поле не передают.
    has_texture: bool = False
    # Прямой запрет поворота, отдельно от текстуры.
    no_rotation: bool = False


class OrderUpdate(BaseModel):
    """Частичное редактирование заказа: передаются только изменяемые поля."""

    has_texture: bool | None = None
    no_rotation: bool | None = None
    comment: str | None = None
    # Срок переносят по заказу: заказ живёт дольше заявки.
    due_date: date | None = None
    # Направление правится в карточке заказа: до этого проставить его было
    # негде вовсе, и все отборы по направлениям стояли пустыми.
    direction_id: uuid.UUID | None = None
    direction_code: str | None = None
    order_number: str | None = Field(default=None, min_length=1, max_length=50)

    @field_validator("order_number")
    @classmethod
    def validate_order_number(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("Укажите номер заказа")
        value = value.strip()
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Номер должен быть одной строкой")
        return value


class OrderItemCreate(BaseModel):
    template_id: uuid.UUID | None = None
    item_type: str
    name: str
    width: Decimal
    height: Decimal
    depth: Decimal
    quantity: int = Field(default=1, ge=1)
    material_id: uuid.UUID | None = None
    facade_material_id: uuid.UUID | None = None
    thickness: Decimal | None = None
    params_json: dict[str, Any] = Field(default_factory=dict)


class OrderPositionWrite(BaseModel):
    """Строка сметы, как её присылает таблица в карточке заказа.

    Цена подтягивается из справочника по ``price_item_id``. Присланный
    ``unit_price`` перебивает её — это «индивидуальная цена под заказ»: строка
    помечается как поправленная вручную, а справочник остаётся прежним. У
    нестандарта своя цена обязательна, брать её негде.
    """

    price_item_id: uuid.UUID | None = None
    is_custom: bool = False
    article: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    kind: str = Field(default="other", max_length=50)
    unit: str = Field(default="sqm", max_length=20)
    quantity: Decimal = Field(default=Decimal("1"), ge=0)
    width: Decimal | None = Field(default=None, ge=0)
    height: Decimal | None = Field(default=None, ge=0)
    # Площадь можно прислать напрямую — например, суммой по деталям из раскроя.
    # Если пришли размеры, она считается по ним и присланное значение не нужно.
    area_sqm: Decimal | None = Field(default=None, ge=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    amount_override: Decimal | None = Field(default=None, ge=0)
    thickness: Decimal | None = Field(default=None, ge=0)
    color: str | None = Field(default=None, max_length=255)
    milling: str | None = Field(default=None, max_length=255)
    comment: str | None = None


class OrderPositionsReplace(BaseModel):
    """Таблица позиций целиком.

    Таблица правится на экране как единое целое: строки добавляют, удаляют и
    двигают. Присылать её целиком проще и надёжнее, чем собирать diff на фронте.
    """

    positions: list[OrderPositionWrite] = Field(default_factory=list)


class OrderPositionRead(ORMModel):
    id: uuid.UUID
    order_id: uuid.UUID
    line_no: int
    price_item_id: uuid.UUID | None
    is_custom: bool
    article: str | None
    name: str
    kind: str
    kind_label: str = ""
    unit: str
    unit_label: str = ""
    quantity: Decimal
    width: Decimal | None
    height: Decimal | None
    area_sqm: Decimal
    unit_price: Decimal
    # Цена поправлена под этот заказ, и по прайсу она была другой.
    price_overridden: bool = False
    base_price: Decimal | None = None
    amount: Decimal
    thickness: Decimal | None
    color: str | None
    milling: str | None
    comment: str | None


class OrderPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str = Field(default="cash", max_length=30)
    paid_at: datetime | None = None
    comment: str | None = None


class OrderPaymentRead(ORMModel):
    id: uuid.UUID
    order_id: uuid.UUID
    amount: Decimal
    method: str
    method_label: str = ""
    paid_at: datetime
    comment: str | None
    created_at: datetime


class OrderBalanceRead(BaseModel):
    """Деньги по заказу одной строкой.

    ``balance`` = оплачено − сумма сметы. Плюс — аванс или переплата, минус —
    долг. ``status`` подписывает это по-русски, чтобы фронт не считал сам.
    """

    positions_total: Decimal
    final_amount: Decimal
    paid_amount: Decimal
    balance: Decimal
    status: str
    by_method: list[dict[str, str]] = Field(default_factory=list)


class OrderShippedRequest(BaseModel):
    """Галочка «отгружено» в карточке заказа."""

    shipped: bool = True


class OrderMaterialOrderedRequest(BaseModel):
    """Галочка «материал заказан».

    Студия помечала это заливкой в экселе. Здесь — отметка, по которой можно
    отобрать «на что материал ещё не заказан».
    """

    material_ordered: bool = True


class AdditionalOrderRequest(BaseModel):
    """Доп. заказ к основному.

    Номер по умолчанию наследуется от родителя — «1024-Ф/1». Свой можно назвать,
    если у студии на доп своя нумерация.
    """

    manager_id: uuid.UUID | None = None
    order_number: str | None = Field(default=None, max_length=50)
    # Смету можно занести сразу при создании допа — тем же контуром, что и на
    # «Рабочем месте», одним действием, а не отдельным заходом на пустую
    # карточку. Необязательно: доп можно завести и пустым, как раньше.
    positions: list[OrderPositionWrite] = Field(default_factory=list)


class OrderCuttingLayoutSaveRequest(BaseModel):
    sheet_settings: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)
    parts: list[dict[str, Any]] = Field(default_factory=list)
    sheets: list[dict[str, Any]] = Field(default_factory=list)
    pattern_filter: str | None = None
    active_sheet_index: int | None = None
    note: str | None = None
    sheet_svg: str | None = None


class AdditionalOrderLink(ORMModel):
    """Доп. заказ строкой в карточке родителя.

    Раньше наружу уходил только счётчик, и «2 доп. заказа» были в карточке
    просто текстом: менеджер видел, что допы есть, а открыть их мог только
    поиском по номеру — сам номер система не показывала. Здесь ровно то, что
    нужно строке со ссылкой: куда вести, под каким номером и на сколько денег.

    Поля названы как атрибуты ``Order``: список собирается прямо из
    ``order.additional_orders`` при валидации ``OrderRead``, без сборки руками.
    """

    id: uuid.UUID
    order_number: str
    created_at: datetime
    final_amount: Decimal
    currency: str
    # Отгрузка и материал у допа свои — по ним видно, догоняет ли доп основной
    # заказ или уедет отдельной машиной.
    shipped_at: datetime | None = None
    material_ordered: bool = False
    status: OrderStatusRead | None = None
    # Статус оплаты этого конкретного допа («Долг» / «Аванс» / «Оплачен
    # полностью»), той же подписью, что и у главного заказа. Допы часто везут
    # довозом к уже оплаченному заказу, и по одному счётчику родителя не
    # видно, кто из них должен ещё денег.
    payment_status: str = "Нет расчёта"


class OrderItemRead(ORMModel):
    id: uuid.UUID
    order_id: uuid.UUID
    template_id: uuid.UUID | None
    item_type: str
    name: str
    width: Decimal
    height: Decimal
    depth: Decimal
    quantity: int
    material_id: uuid.UUID | None
    facade_material_id: uuid.UUID | None
    thickness: Decimal | None
    params_json: dict[str, Any]
    price: Decimal
    created_at: datetime
    updated_at: datetime
    template: ProductTemplateRead | None = None


class OrderRead(ORMModel):
    id: uuid.UUID
    deleted_at: datetime | None = None
    lifecycle: str = "estimate"
    lifecycle_label: str = "Расчёт"
    order_number: str
    direction_id: uuid.UUID | None = None
    client_id: uuid.UUID
    manager_id: uuid.UUID
    status_id: uuid.UUID
    total_amount: Decimal
    discount_amount: Decimal
    final_amount: Decimal
    currency: str
    comment: str | None
    customer_comment: str | None = None
    has_texture: bool = False
    # Прямой запрет поворота детали при раскрое, отдельно от текстуры.
    no_rotation: bool = False
    source_lead_id: uuid.UUID | None
    # Срок сдачи, названный клиенту.
    due_date: date | None = None
    # Материал заказан поставщику: раньше это была заливка ячейки в экселе.
    material_ordered: bool = False
    material_ordered_at: datetime | None = None
    # Доп. заказ: ссылка на основной. У основного — сколько допов к нему висит,
    # чтобы в списке читалось «заказ 1024 (2 доп. заказа)».
    parent_order_id: uuid.UUID | None = None
    parent_order_number: str | None = None
    additional_orders_count: int = 0
    additional_orders_total: Decimal = Decimal("0")
    # Сами допы, а не только их число: без списка карточка не может дать на них
    # ссылку, и родитель с допом связаны в интерфейсе одним текстом.
    additional_orders: list[AdditionalOrderLink] = []
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    production_start_at: datetime | None
    shipped_at: datetime | None
    client: ClientRead | None = None
    direction: DirectionSummaryRead | None = None
    manager: UserRead | None = None
    status: OrderStatusRead | None = None
    items: list[OrderItemRead] = []
    status_history: list[OrderStatusHistoryRead] = []
    positions: list[OrderPositionRead] = []
    # None keeps legacy lead dimensions; [] is an explicitly empty estimate.
    specification_parts: list[dict[str, Any]] | None = None
    payments: list[OrderPaymentRead] = []
    balance: OrderBalanceRead | None = None


class OrderFilterParams(BaseModel):
    status_code: str | None = None
    client_id: uuid.UUID | None = None
    search: str | None = None


class ChangeOrderStatusRequest(BaseModel):
    status_code: str
    comment: str | None = None


class PricingComponent(BaseModel):
    code: str
    name: str
    amount: Decimal
    unit: str
    quantity: Decimal


class OrderCalculationResult(BaseModel):
    total_amount: Decimal
    discount_amount: Decimal
    final_amount: Decimal
    currency: str
    components: list[PricingComponent]
