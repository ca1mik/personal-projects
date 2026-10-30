from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.shared.schemas import ORMModel


class PriceItemChangeRead(ORMModel):
    id: uuid.UUID
    old_price: Decimal
    new_price: Decimal
    comment: str | None
    changed_at: datetime
    changed_by: uuid.UUID | None


class PriceItemRead(ORMModel):
    id: uuid.UUID
    article: str
    name: str
    kind: str
    kind_label: str = ""
    unit: str
    unit_label: str = ""
    price: Decimal
    comment: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PriceItemDetailRead(PriceItemRead):
    price_changes: list[PriceItemChangeRead] = []


class PriceItemCreate(BaseModel):
    article: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    kind: str = Field(default="other", min_length=1, max_length=50)
    unit: str = Field(default="sqm", min_length=1, max_length=20)
    price: Decimal = Field(default=Decimal("0"), ge=0)
    comment: str | None = None
    sort_order: int = 0
    is_active: bool = True


class PriceItemUpdate(BaseModel):
    article: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    kind: str | None = Field(default=None, min_length=1, max_length=50)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    price: Decimal | None = Field(default=None, ge=0)
    comment: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    # Комментарий пишется в историю цены, а не в карточку артикула: «подняли на
    # 10 % с июня» относится к изменению, а не к самому артикулу.
    price_comment: str | None = None


class PriceBookOptions(BaseModel):
    """Справочник для выпадающих списков: типы работ и единицы."""

    kinds: list[dict[str, str]]
    units: list[dict[str, str]]
    # Направления для выбора при приёме заявки: эмаль, плёнка ПВХ, шпон.
    # Отдельно от `kinds`, потому что в справочнике цен типов больше — там есть
    # операции внутри заказа (фрезеровка, мыло, кромка), и в выборе направления
    # им не место.
    production_kinds: list[dict[str, str]] = []
