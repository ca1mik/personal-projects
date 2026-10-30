from __future__ import annotations

import uuid
from datetime import datetime

from app.modules.shared.schemas import ORMModel


class ExportRead(ORMModel):
    id: uuid.UUID
    order_id: uuid.UUID
    export_type: str
    format: str
    file_name: str
    file_path: str
    version: int
    created_at: datetime
    created_by: uuid.UUID | None
