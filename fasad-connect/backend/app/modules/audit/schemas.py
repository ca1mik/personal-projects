from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.modules.shared.schemas import ORMModel


class AuditLogRead(ORMModel):
    id: uuid.UUID
    entity_type: str
    entity_id: str
    action: str
    old_value_json: dict[str, Any] | None
    new_value_json: dict[str, Any] | None
    user_id: uuid.UUID | None
    created_at: datetime
