from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.modules.shared.schemas import ORMModel


class ClientCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    comment: str | None = None


class ClientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    comment: str | None = None


class ClientRead(ORMModel):
    id: uuid.UUID
    full_name: str
    organization: str | None = None
    phone: str | None
    email: str | None
    # Адрес едет вместе с клиентом всюду, где клиента показывают: список
    # клиентов, блок «Клиент» в заказе, печатный бланк, карта раскроя. Его
    # спрашивают ради «куда везти», и одной карточки клиента для этого мало —
    # смотреть адрес приходится ровно там, где собирают машину.
    address: str | None
    comment: str | None
    created_at: datetime
    updated_at: datetime
    # Заказчик: «по клиентам больше инфы дай — когда заказ был последний,
    # баланс». Считаются одним пакетным запросом на всю страницу списка
    # (`ClientService._batch_summaries`), а не по клиенту — иначе список из
    # полусотни клиентов давал бы полсотни лишних запросов к базе.
    last_order_at: datetime | None = None
    balance_status: str | None = None


class ClientOrderHistoryItem(BaseModel):
    """Строка истории заказов клиента — по ТЗ: дата, сумма, состав."""

    id: uuid.UUID
    order_number: str
    created_at: datetime
    final_amount: Decimal
    currency: str
    status_name: str | None = None
    direction_name: str | None = None
    items_summary: str = ""
    items_count: int = 0


class ClientBalanceRead(BaseModel):
    """Деньги по клиенту одной строкой.

    ``balance`` = оплачено − начислено. Плюс — аванс, минус — долг. Заказчик
    ведёт ровно эти три числа в своей таблице как «сумма / оплата / разница».
    """

    charged: Decimal = Decimal("0")
    paid: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    status: str = "Нет расчётов"
    currency: str = "RUB"
    orders_count: int = 0
    unpaid_orders: int = 0
    due_total: Decimal = Decimal("0")


class ClientDepositCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: str = Field(default="cash", max_length=30)
    comment: str | None = None


class ClientDepositCorrection(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    reason: str = Field(min_length=1, max_length=1000)


class ClientDepositWithdrawalCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: str = Field(default="cash", max_length=30)
    comment: str = Field(min_length=1)


class ClientDepositRead(BaseModel):
    balance: Decimal = Decimal("0")
    movements: list[ClientDepositMovementRead] = Field(default_factory=list)


class ClientDepositMovementRead(ORMModel):
    id: uuid.UUID
    amount: Decimal
    kind: str
    method: str | None
    order_id: uuid.UUID | None
    comment: str | None
    created_at: datetime


class ClientOrderSettlement(BaseModel):
    """Расчёты по одному заказу: сколько начислено и сколько закрыто."""

    order_id: uuid.UUID
    order_number: str
    created_at: datetime
    shipped_at: datetime | None = None
    status_name: str | None = None
    direction_name: str | None = None
    charged: Decimal = Decimal("0")
    paid: Decimal = Decimal("0")
    due: Decimal = Decimal("0")
    overpaid: Decimal = Decimal("0")
    payments_count: int = 0
    currency: str = "RUB"


class ClientLedgerEntry(BaseModel):
    """Событие взаиморасчётов: начисление по заказу или поступление денег."""

    kind: str
    kind_label: str
    happened_at: datetime
    order_id: uuid.UUID | None = None
    order_number: str | None = None
    charged: Decimal = Decimal("0")
    paid: Decimal = Decimal("0")
    #: Откуда поступление: наличные, карта, счёт — или направление заказа.
    source: str | None = None
    comment: str | None = None
    balance_after: Decimal = Decimal("0")


class ClientStatementRead(BaseModel):
    """Выписка по клиенту: баланс, разрез по заказам и лента событий."""

    balance: ClientBalanceRead
    orders: list[ClientOrderSettlement] = Field(default_factory=list)
    ledger: list[ClientLedgerEntry] = Field(default_factory=list)


class ClientPurchaseTotals(BaseModel):
    orders_count: int = 0
    total_amount: Decimal = Decimal("0")
    currency: str = "RUB"
    first_order_at: datetime | None = None
    last_order_at: datetime | None = None
    days_since_last_order: int | None = None


class ClientCalculationItem(BaseModel):
    """Расчёт для клиента: заявка, которая может ещё не стать заказом.

    Заказчик: «сдала клиента, 2 заказа посчитала, но их здесь нет». Посчитанное
    и не купленное — это заявка: она не должна попадать в выручку, но и теряться
    из карточки клиента ей нельзя, иначе менеджер не помнит, кому что называл.
    """

    id: uuid.UUID
    lead_number: str | None = None
    created_at: datetime
    due_date: date | None = None
    status: str
    status_label: str = ""
    quantity: int = 0
    facade_area_sqm: Decimal = Decimal("0")
    estimated_amount: Decimal | None = None
    order_id: uuid.UUID | None = None
    order_number: str | None = None
    currency: str = "RUB"


class ClientDetailRead(ClientRead):
    """Карточка клиента с историей заказов и сводкой покупок."""

    totals: ClientPurchaseTotals = Field(default_factory=ClientPurchaseTotals)
    order_history: list[ClientOrderHistoryItem] = Field(default_factory=list)
    # Расчёты клиента: и ждущие ответа, и уже ставшие заказами.
    #
    # Имя не «leads»: у модели клиента есть связь с тем же именем, и Pydantic
    # подставлял бы в это поле сами заявки вместо собранных строк.
    calculations: list[ClientCalculationItem] = Field(default_factory=list)
    #: Сколько расчётов ждут ответа клиента и на какую сумму.
    pending_calculations_count: int = 0
    pending_calculations_amount: Decimal = Decimal("0")
    #: Взаиморасчёты: баланс, разрез по заказам и лента поступлений.
    statement: ClientStatementRead | None = None
    deposit: ClientDepositRead = Field(default_factory=ClientDepositRead)
