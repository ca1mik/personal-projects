from __future__ import annotations

import uuid
from datetime import datetime

from app.modules.shared.schemas import ORMModel


class OrderStatusRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    sort_order: int
    is_terminal: bool


class OrderStatusHistoryRead(ORMModel):
    id: uuid.UUID
    order_id: uuid.UUID
    old_status_id: uuid.UUID | None
    new_status_id: uuid.UUID
    changed_by: uuid.UUID | None
    changed_at: datetime
    comment: str | None
    old_status: OrderStatusRead | None = None
    new_status: OrderStatusRead
