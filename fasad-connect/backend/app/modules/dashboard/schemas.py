from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.modules.production.schemas import ProductionDashboardRead


class StatusCounter(BaseModel):
    code: str
    name: str
    count: int


class MaterialStockCounter(BaseModel):
    material_type: str
    count: int


class DashboardSummary(BaseModel):
    total_orders: int
    new_leads: int
    # Выручка приходит только тому, кто ведёт деньги.
    #
    # `None` — не «ноль выручки», а «не показываем». Работник цеха открывает
    # сводку ради своих этапов и брака, и деньги студии ему там не место:
    # описание его роли прямо обещает, что денег он не видит. Пустое поле, а не
    # отдельный эндпоинт — чтобы у сводки остался один контракт.
    mock_revenue: Decimal | None = None
    orders_by_status: list[StatusCounter]
    stock_by_material_type: list[MaterialStockCounter]
    production: ProductionDashboardRead
