from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base_class import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("source_channel", "external_message_id", name="uq_leads_source_external"),
    )

    # Номер для человека: менеджер называет его клиенту по телефону, ссылка на
    # UUID для этого не годится. Своя сквозная нумерация, отдельная от заказов.
    lead_number: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True, index=True
    )
    source_channel: Mapped[str] = mapped_column(String(50), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="new", index=True)
    # Срок, который назвали клиенту. Подставляется типовым по типу работ (мыло —
    # 14 дней), но правится менеджером: «через две недели» и «к 3 сентября» на
    # практике не одно и то же.
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    direction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("production_directions.id"),
        nullable=True,
        index=True,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id"), nullable=True, index=True
    )
    assigned_manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    client: Mapped[Client | None] = relationship(back_populates="leads")
    direction: Mapped[ProductionDirection | None] = relationship("ProductionDirection")
    assigned_manager: Mapped[User | None] = relationship()
    attachments: Mapped[list[LeadAttachment]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    orders: Mapped[list[Order]] = relationship(back_populates="source_lead")


Index("ix_leads_external_message_id", Lead.external_message_id)


class LeadAttachment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "lead_attachments"

    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column()

    lead: Mapped[Lead] = relationship(back_populates="attachments")
