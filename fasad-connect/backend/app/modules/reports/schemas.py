from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PeriodRead(BaseModel):
    code: str
    label: str
    date_from: datetime | None
    date_to: datetime | None


class VolumeTotals(BaseModel):
    """Итоги в деньгах и в квадратных метрах — как требует ТЗ."""

    orders_count: int = 0
    amount: Decimal = Decimal("0")
    currency: str = "RUB"
    facade_area_sqm: Decimal = Decimal("0")
    material_area_sqm: Decimal = Decimal("0")
    items_count: int = 0


class VolumeRow(VolumeTotals):
    key: str
    label: str


class DirectionScope(BaseModel):
    """Какое направление отобрано в отчёте.

    Заказчик: цифры в файле молча расходились с экраном, потому что отбор жил
    только на странице. Отчёт обязан сам сказать, по какому направлению он
    посчитан, — тогда это можно напечатать в шапке выгрузки.
    """

    direction_code: str | None = None
    direction_label: str | None = None


class VolumeReport(DirectionScope):
    """Сколько принято или отгружено за период: всего и по направлениям."""

    metric: str
    metric_label: str
    period: PeriodRead
    total: VolumeTotals
    by_direction: list[VolumeRow] = Field(default_factory=list)
    by_month: list[VolumeRow] = Field(default_factory=list)


class WorkKindRow(BaseModel):
    """Строка отчёта по обработке: фрезеровка, шпон, мыло и что заказчик заведёт.

    Считается по строкам сметы заказа, а не по направлению: в одном заказе может
    быть и фрезеровка, и шпон, и направление их не различает.
    """

    kind: str
    kind_label: str
    orders_count: int = 0
    positions_count: int = 0
    quantity: Decimal = Decimal("0")
    area_sqm: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")


class WorkKindArticleRow(WorkKindRow):
    """То же, но с разбивкой до артикула."""

    article: str | None = None
    name: str = ""


class WorkKindReport(DirectionScope):
    metric: str
    metric_label: str
    period: PeriodRead
    total: WorkKindRow
    by_kind: list[WorkKindRow] = Field(default_factory=list)
    by_article: list[WorkKindArticleRow] = Field(default_factory=list)


class ClientActivityRow(BaseModel):
    """Строка отчёта по клиентам: сумма покупок, объёмы, частота, давность."""

    client_id: uuid.UUID
    full_name: str
    organization: str | None = None
    phone: str | None = None
    email: str | None = None
    category: str
    category_label: str
    orders_count: int = 0
    amount: Decimal = Decimal("0")
    currency: str = "RUB"
    facade_area_sqm: Decimal = Decimal("0")
    material_area_sqm: Decimal = Decimal("0")
    items_count: int = 0
    first_order_at: datetime | None = None
    last_order_at: datetime | None = None
    days_since_last_order: int | None = None
    average_days_between_orders: int | None = None
    directions: list[str] = Field(default_factory=list)
    #: Материал по ПОСЛЕДНЕМУ заказу клиента — не заказан / заказан / отгружен.
    #: None — заказов у клиента ещё не было вообще.
    last_order_material_status: str | None = None
    last_order_material_status_label: str | None = None


class ClientActivityReport(DirectionScope):
    period: PeriodRead
    total: VolumeTotals
    rows: list[ClientActivityRow] = Field(default_factory=list)
    #: Порог «давно не покупал» — печатается в шапке выгрузки, иначе по файлу не
    #: понять, почему в нём двенадцать клиентов из ста.
    inactive_days: int | None = None
    #: Сколько клиентов отмечено галочками. ``None`` — отбора не было.
    selected_clients: int | None = None


class StageDurationRow(BaseModel):
    """Сколько времени занимает этап. Основа отчёта по выработке."""

    stage_code: str
    stage_name: str
    work_center_name: str | None = None
    completed_count: int = 0
    in_progress_count: int = 0
    blocked_count: int = 0
    average_hours: Decimal | None = None
    median_hours: Decimal | None = None
    longest_hours: Decimal | None = None


class OrderCycleRow(BaseModel):
    """Сколько заказ шёл от запуска в производство до готовности."""

    order_id: uuid.UUID
    order_number: str
    direction_name: str | None = None
    client_name: str | None = None
    stages_total: int = 0
    stages_done: int = 0
    current_stage_name: str | None = None
    production_hours: Decimal | None = None
    is_finished: bool = False


class ProductionTimeReport(DirectionScope):
    period: PeriodRead
    by_stage: list[StageDurationRow] = Field(default_factory=list)
    orders: list[OrderCycleRow] = Field(default_factory=list)


class OrderVolumeRow(BaseModel):
    """Строка «заказ»: сумма и площадь одной сделки.

    Заказчик сводит объёмы руками по заказам, поэтому нужен файл, где строка —
    это заказ, а не свёрнутый итог по направлению.
    """

    order_id: uuid.UUID
    order_number: str
    created_at: datetime | None = None
    shipped_at: datetime | None = None
    client_name: str | None = None
    organization: str | None = None
    direction_name: str | None = None
    status_name: str | None = None
    items_count: int = 0
    facade_area_sqm: Decimal = Decimal("0")
    material_area_sqm: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    currency: str = "RUB"


class OrderVolumeReport(DirectionScope):
    metric: str
    metric_label: str
    period: PeriodRead
    total: VolumeTotals
    rows: list[OrderVolumeRow] = Field(default_factory=list)
