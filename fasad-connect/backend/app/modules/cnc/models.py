from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.db.mixins import UUIDPrimaryKeyMixin, utcnow


class CncMachine(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "cnc_machines"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    controller: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CncJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "cnc_jobs"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    part_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("parts.id"), nullable=True, index=True
    )
    machine_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cnc_machines.id"), nullable=True, index=True
    )
    machine_name: Mapped[str] = mapped_column(String(100))
    postprocessor: Mapped[str] = mapped_column(String(100))
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
