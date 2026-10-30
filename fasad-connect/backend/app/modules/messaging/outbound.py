"""Outbound delivery dispatch for inbox replies.

Channels without a configured real transport keep the historical ``mock_sent``
behaviour, so existing demo/manual channels and their tests are untouched. Only
a channel that is genuinely wired up (active, correct type, credentials present)
attempts a real send.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import AppError
from app.modules.messaging.channel_config import get_secret, load_email_config
from app.modules.messaging.email_service import EMAIL_CHANNEL_TYPE, EmailChannelService
from app.modules.messaging.models import ChannelAccount, Conversation

MOCK_STATUS = "mock_sent"
SENT_STATUS = "sent"
FAILED_STATUS = "failed"


@dataclass
class DeliveryResult:
    status: str
    external_message_id: str | None = None
    error: str | None = None
    raw_payload: dict[str, object] | None = None


def _email_transport_ready(account: ChannelAccount) -> bool:
    if account.channel_type != EMAIL_CHANNEL_TYPE or not account.is_active:
        return False
    try:
        config = load_email_config(account)
    except AppError:
        return False
    has_sender = bool(config.smtp.from_email or config.smtp.login)
    return bool(config.smtp.host) and has_sender and bool(get_secret(account, "smtp_password"))


def has_real_transport(account: ChannelAccount) -> bool:
    return _email_transport_ready(account)


def _resolve_recipient(conversation: Conversation) -> str:
    recipient = conversation.participant_email or (
        conversation.client.email if conversation.client else None
    )
    if not recipient:
        raise AppError("У диалога нет email-адреса получателя — ответ отправить нельзя")
    return recipient


def _reply_subject(conversation: Conversation, subject: str | None) -> str:
    base = subject or conversation.subject or "Ответ на ваше обращение"
    return base if base.lower().startswith("re:") else f"Re: {base}"


def _last_inbound_message_id(conversation: Conversation) -> str | None:
    for message in reversed(conversation.messages):
        if message.direction == "inbound" and message.external_message_id:
            return message.external_message_id
    return None


def dispatch_reply(
    conversation: Conversation,
    *,
    body_text: str,
    subject: str | None,
) -> DeliveryResult:
    account = conversation.channel_account

    if not _email_transport_ready(account):
        return DeliveryResult(status=MOCK_STATUS, raw_payload={"mode": "crm_mock_outbound"})

    recipient = _resolve_recipient(conversation)
    resolved_subject = _reply_subject(conversation, subject)
    in_reply_to = _last_inbound_message_id(conversation)

    try:
        message_id = EmailChannelService.send_email(
            account,
            to_email=recipient,
            subject=resolved_subject,
            body_text=body_text,
            in_reply_to=in_reply_to,
        )
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001 - SMTP failures surface as a delivery error
        return DeliveryResult(
            status=FAILED_STATUS,
            error=str(exc),
            raw_payload={"mode": "smtp", "to": recipient, "error": str(exc)},
        )

    return DeliveryResult(
        status=SENT_STATUS,
        external_message_id=message_id,
        raw_payload={"mode": "smtp", "to": recipient, "in_reply_to": in_reply_to},
    )
