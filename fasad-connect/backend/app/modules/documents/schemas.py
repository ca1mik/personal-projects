from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.shared.schemas import ORMModel


class DocumentRead(ORMModel):
    id: uuid.UUID
    order_id: uuid.UUID
    doc_type: str
    file_name: str
    content_type: str | None
    size_bytes: int | None
    comment: str | None
    created_at: datetime
    created_by: uuid.UUID | None
    author_name: str | None = None


class DocumentUpdate(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)
