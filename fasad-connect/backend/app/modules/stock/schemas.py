from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.shared.schemas import ORMModel


class StockReceiptCreate(BaseModel):
    material_type: Literal["material", "edge_material"]
    material_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    comment: str | None = Field(default=None, max_length=255)


class StockItemRead(ORMModel):
    id: uuid.UUID
    material_type: str
    material_id: uuid.UUID
    quantity: Decimal
    reserved_quantity: Decimal
    unit: str
    updated_at: datetime


class StockMovementRead(ORMModel):
    id: uuid.UUID
    stock_item_id: uuid.UUID
    order_id: uuid.UUID | None
    movement_type: str
    quantity: Decimal
    unit: str
    created_at: datetime
    created_by: uuid.UUID | None
    comment: str | None
