from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.modules.shared.schemas import ORMModel


class PartEdgeRead(ORMModel):
    id: uuid.UUID
    part_id: uuid.UUID
    side: str
    edge_material_id: uuid.UUID
    thickness: Decimal | None
    color: str | None
    length_mm: Decimal


class PartOperationRead(ORMModel):
    id: uuid.UUID
    part_id: uuid.UUID
    operation_type: str
    x: Decimal | None
    y: Decimal | None
    z: Decimal | None
    diameter: Decimal | None
    depth: Decimal | None
    width: Decimal | None
    height: Decimal | None
    angle: Decimal | None
    params_json: dict[str, Any]


class PartRead(ORMModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_item_id: uuid.UUID
    part_code: str
    name: str
    length: Decimal
    width: Decimal
    thickness: Decimal
    quantity: int
    material_id: uuid.UUID
    grain_direction: str | None
    rotation_allowed: bool
    barcode: str | None
    label_text: str | None
    created_at: datetime
    updated_at: datetime
    edges: list[PartEdgeRead] = []
    operations: list[PartOperationRead] = []
