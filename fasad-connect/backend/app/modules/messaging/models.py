from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base_class import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ChannelAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "channel_accounts"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    channel_type: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    inbound_mode: Mapped[str] = mapped_column(String(50), default="webhook")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    secrets_json: Mapped[dict] = mapped_column(JSON, default=dict)
    poll_cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_poll_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    default_manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    default_manager: Mapped[User | None] = relationship("User", foreign_keys=[default_manager_id])
    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="channel_account",
        cascade="all, delete-orphan",
    )


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    channel_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("channel_accounts.id"),
        index=True,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id"),
        nullable=True,
        index=True,
    )
    source_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id"),
        nullable=True,
        index=True,
    )
    assigned_manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)
    contact_key: Mapped[str] = mapped_column(String(255), index=True)
    external_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    external_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    participant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    participant_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    participant_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    participant_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_preview: Mapped[str | None] = mapped_column(Text, nullable=True)

    channel_account: Mapped[ChannelAccount] = relationship(back_populates="conversations")
    client: Mapped[Client | None] = relationship("Client")
    source_lead: Mapped[Lead | None] = relationship("Lead")
    assigned_manager: Mapped[User | None] = relationship("User", foreign_keys=[assigned_manager_id])
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "source_channel",
            "external_message_id",
            name="uq_messages_source_external",
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(50), default="received", index=True)
    source_channel: Mapped[str] = mapped_column(String(50), index=True)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sender_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    lead: Mapped[Lead | None] = relationship("Lead")
    user: Mapped[User | None] = relationship("User")
    attachments: Mapped[list[MessageAttachment]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )


Index("ix_messages_external_message_id", Message.external_message_id)


class MessageAttachment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "message_attachments"

    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column()

    message: Mapped[Message] = relationship(back_populates="attachments")


class TelegramBotSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "telegram_bot_sessions"

    chat_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    telegram_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    current_step: Mapped[str] = mapped_column(String(50), default="choose_product")
    selected_product_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    collected_data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
