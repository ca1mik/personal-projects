from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, EmailStr, Field, field_validator

from app.modules.clients.schemas import ClientRead
from app.modules.shared.schemas import ORMModel


class UnifiedAttachmentIn(BaseModel):
    file_name: str
    mime_type: str | None = None
    size_bytes: int = 0
    content_base64: str | None = None
    external_url: str | None = None


class UnifiedSenderIn(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    # Адрес доставки или объекта: менеджер спрашивает его в первом же разговоре,
    # а занести было некуда. Необязательный — из письма и мессенджера адрес не
    # приходит, там поле останется пустым.
    address: str | None = None
    # Заказчик: поле «Организация» на рабочем месте существовало только на
    # экране — уходило текстом внутрь заявки, но не доходило до карточки
    # клиента ни при заведении нового, ни при довыборе существующего.
    organization: str | None = None
    external_id: str | None = None
    # Менеджер выбрал клиента из базы в форме заявки. Телефон и почта в карточке
    # могут быть не заполнены, и тогда узнать клиента по контактам нельзя —
    # заводился дубль. С явным id заявка ложится ровно на выбранного клиента.
    client_id: uuid.UUID | None = None


class UnifiedLeadIn(BaseModel):
    source_channel: str = Field(max_length=50)
    external_message_id: str | None = None
    subject: str | None = None
    text: str = ""
    sender: UnifiedSenderIn | None = None
    attachments: list[UnifiedAttachmentIn] = []
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    assigned_manager_id: str | None = None
    # Set by pollers that know which account received the message, so that a
    # second mailbox on the same channel type does not land on the first one.
    channel_account_code: str | None = None
    # Производственное направление: «enamel» | «pvc» | «veneer». Ручной ввод
    # указывает его сразу; для писем менеджер выставляет его позже через PATCH.
    direction_code: str | None = None
    # Срок, названный клиенту. Пусто — считаем типовым по типу работ (мыло —
    # 14 дней). Из письма срок не приходит, там поле останется пустым.
    due_date: date | None = None
    # Тип работ заявки: по нему берётся типовой срок и буква номера заказа.
    work_kind: str | None = Field(default=None, max_length=50)
    # Свой номер заявки. Пусто — система ставит следующий по порядку.
    lead_number: str | None = Field(default=None, max_length=20)


class EmailAttachmentPayload(BaseModel):
    file_name: str
    mime_type: str | None = None
    content_base64: str | None = None
    size_bytes: int = 0


class EmailPayload(BaseModel):
    message_id: str | None = None
    subject: str | None = None
    from_name: str | None = None
    from_email: EmailStr | None = None
    from_phone: str | None = None
    body_text: str = ""
    attachments: list[EmailAttachmentPayload] = []
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class TelegramPayload(BaseModel):
    update_id: int | None = None
    message: dict[str, Any] = Field(default_factory=dict)
    callback_query: dict[str, Any] = Field(default_factory=dict)


class WhatsAppPayload(BaseModel):
    entry: list[dict[str, Any]] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class GenericWebhookPayload(BaseModel):
    external_message_id: str | None = None
    subject: str | None = None
    text: str = ""
    sender_name: str | None = None
    sender_phone: str | None = None
    sender_email: EmailStr | None = None
    attachments: list[UnifiedAttachmentIn] = []
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class TelegramBotMenuButton(BaseModel):
    text: str
    callback_data: str | None = None


class TelegramBotReply(BaseModel):
    text: str
    session_state: str
    buttons: list[list[TelegramBotMenuButton]] = Field(default_factory=list)
    lead_id: str | None = None
    estimated_total: str | None = None
    estimated_area_sqm: str | None = None


class TelegramBotWebhookResult(BaseModel):
    reply: TelegramBotReply


class MessagingUserSummaryRead(ORMModel):
    id: uuid.UUID
    full_name: str
    login: str


class LeadReferenceRead(ORMModel):
    id: uuid.UUID
    # номер нужен в списке диалогов: там печатался обрезанный UUID
    lead_number: str | None = None
    source_channel: str
    status: str
    created_at: datetime


class ImapSettings(BaseModel):
    host: str = ""
    port: int = 993
    ssl: bool = True
    login: str = ""
    folder: str = "INBOX"


class SmtpSettings(BaseModel):
    host: str = ""
    port: int = 465
    security: Literal["ssl", "starttls", "none"] = "ssl"
    login: str = ""
    from_email: str = ""
    from_name: str = ""


class EmailChannelConfig(BaseModel):
    """Non-secret part of an email ChannelAccount, stored in ``config_json``."""

    imap: ImapSettings = Field(default_factory=ImapSettings)
    smtp: SmtpSettings = Field(default_factory=SmtpSettings)
    poll_interval_seconds: int = Field(default=120, ge=30, le=86_400)
    since_days: int = Field(default=3, ge=1, le=90)
    unseen_only: bool = True
    mark_seen: bool = True


class ChannelSecretsIn(BaseModel):
    """Write-only credentials. Empty/omitted values keep the stored secret."""

    imap_password: str | None = None
    smtp_password: str | None = None


class ChannelAccountCreate(BaseModel):
    code: str = Field(min_length=2, max_length=100)
    channel_type: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    inbound_mode: str = Field(default="webhook", min_length=2, max_length=50)
    is_active: bool = True
    default_manager_id: uuid.UUID | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    secrets: ChannelSecretsIn | None = None


class ChannelAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    inbound_mode: str | None = Field(default=None, min_length=2, max_length=50)
    is_active: bool | None = None
    default_manager_id: uuid.UUID | None = None
    config_json: dict[str, Any] | None = None
    secrets: ChannelSecretsIn | None = None


class ChannelAccountRead(ORMModel):
    id: uuid.UUID
    code: str
    channel_type: str
    name: str
    description: str | None
    inbound_mode: str
    is_active: bool
    default_manager_id: uuid.UUID | None
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    next_poll_at: datetime | None = None
    last_polled_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    configured_secrets: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("configured_secrets", "secrets_json"),
    )
    default_manager: MessagingUserSummaryRead | None = None

    @field_validator("configured_secrets", mode="before")
    @classmethod
    def _mask_secrets(cls, value: Any) -> list[str]:
        """Expose only which credentials exist, never their values."""
        if isinstance(value, dict):
            return sorted(key for key, item in value.items() if item)
        return value or []


class ChannelHealthCheckStep(BaseModel):
    ok: bool
    detail: str


class ChannelHealthCheckResult(BaseModel):
    ok: bool
    imap: ChannelHealthCheckStep | None = None
    smtp: ChannelHealthCheckStep | None = None


class ChannelPollResult(BaseModel):
    account_id: uuid.UUID
    fetched: int
    created: int
    skipped: int
    error: str | None = None


class MessageAttachmentRead(ORMModel):
    id: uuid.UUID
    file_name: str
    file_path: str
    mime_type: str | None
    size_bytes: int


class MessageRead(ORMModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    lead_id: uuid.UUID | None
    user_id: uuid.UUID | None
    direction: str
    status: str
    source_channel: str
    external_message_id: str | None
    subject: str | None
    body_text: str
    normalized_text: str | None
    raw_payload_json: dict[str, Any]
    sender_name: str | None
    sender_phone: str | None
    sender_email: str | None
    sender_external_id: str | None
    read_at: datetime | None
    delivered_at: datetime | None = None
    delivery_error: str | None = None
    created_at: datetime
    updated_at: datetime
    lead: LeadReferenceRead | None = None
    user: MessagingUserSummaryRead | None = None
    attachments: list[MessageAttachmentRead] = Field(default_factory=list)


class ConversationSummaryRead(ORMModel):
    id: uuid.UUID
    channel_account_id: uuid.UUID
    client_id: uuid.UUID | None
    source_lead_id: uuid.UUID | None
    assigned_manager_id: uuid.UUID | None
    status: str
    contact_key: str
    external_chat_id: str | None
    external_thread_id: str | None
    subject: str | None
    participant_name: str | None
    participant_phone: str | None
    participant_email: str | None
    participant_external_id: str | None
    unread_count: int
    last_message_at: datetime | None
    last_message_preview: str | None
    created_at: datetime
    updated_at: datetime
    channel_account: ChannelAccountRead
    client: ClientRead | None = None
    source_lead: LeadReferenceRead | None = None
    assigned_manager: MessagingUserSummaryRead | None = None


class ConversationRead(ConversationSummaryRead):
    messages: list[MessageRead] = Field(default_factory=list)


class ConversationAssignRequest(BaseModel):
    assigned_manager_id: uuid.UUID | None = None


class ConversationReplyCreate(BaseModel):
    body_text: str = Field(min_length=1)
    subject: str | None = None
