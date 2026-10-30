from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.shared.schemas import ORMModel


class DirectionRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    number_suffix: str
    material_area_factor: Decimal
    description: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DirectionSummaryRead(ORMModel):
    """Компактный вид для встраивания в заказ и заявку."""

    id: uuid.UUID
    code: str
    name: str
    number_suffix: str
    material_area_factor: Decimal = Decimal("1")


class DirectionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=100)
    number_suffix: str = Field(default="", max_length=10)
    material_area_factor: Decimal = Field(default=Decimal("1"), gt=0, le=10)
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True


class DirectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    number_suffix: str | None = Field(default=None, max_length=10)
    material_area_factor: Decimal | None = Field(default=None, gt=0, le=10)
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
