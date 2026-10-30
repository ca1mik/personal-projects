from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, get_page_params
from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.leads.schemas import LeadRead
from app.modules.messaging.email_service import EmailChannelService
from app.modules.messaging.intake_auth import require_intake_access
from app.modules.messaging.inbox_service import InboxService
from app.modules.messaging.schemas import (
    ChannelAccountCreate,
    ChannelAccountRead,
    ChannelAccountUpdate,
    ChannelHealthCheckResult,
    ChannelPollResult,
    ConversationAssignRequest,
    ConversationRead,
    ConversationReplyCreate,
    ConversationSummaryRead,
    EmailPayload,
    GenericWebhookPayload,
    TelegramBotWebhookResult,
    TelegramPayload,
    WhatsAppPayload,
)
from app.modules.messaging.service import MessagingService
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter()


def _telegram_chat_id(payload: TelegramPayload) -> int | str | None:
    if payload.callback_query:
        return payload.callback_query.get("message", {}).get("chat", {}).get("id")
    return payload.message.get("chat", {}).get("id")


@router.post("/email/intake", response_model=Envelope[LeadRead], dependencies=[Depends(require_intake_access)])
def email_intake(
    payload: EmailPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    lead = MessagingService.intake_email(db, payload)
    return envelope(LeadRead.model_validate(lead))


@router.post("/telegram/webhook", response_model=Envelope[LeadRead], dependencies=[Depends(require_intake_access)])
def telegram_webhook(
    payload: TelegramPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    lead = MessagingService.intake_telegram(db, payload)
    return envelope(LeadRead.model_validate(lead))


@router.post("/telegram/bot/webhook", response_model=Envelope[TelegramBotWebhookResult], dependencies=[Depends(require_intake_access)])
def telegram_bot_webhook(
    payload: TelegramPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    result = MessagingService.handle_telegram_bot_webhook(db, payload)
    return envelope(result)


@router.post("/telegram/bot/telegram-api", dependencies=[Depends(require_intake_access)])
def telegram_bot_telegram_api(
    payload: TelegramPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    result = MessagingService.handle_telegram_bot_webhook(db, payload)
    chat_id = _telegram_chat_id(payload)
    return {
        "method": "sendMessage",
        "chat_id": chat_id,
        "text": result.reply.text,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": button.text,
                        "callback_data": button.callback_data,
                    }
                    for button in row
                ]
                for row in result.reply.buttons
            ]
        },
    }


@router.post("/whatsapp/webhook", response_model=Envelope[LeadRead], dependencies=[Depends(require_intake_access)])
def whatsapp_webhook(
    payload: WhatsAppPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    lead = MessagingService.intake_whatsapp(db, payload)
    return envelope(LeadRead.model_validate(lead))


@router.post("/webhook/intake", response_model=Envelope[LeadRead], dependencies=[Depends(require_intake_access)])
def generic_webhook_intake(
    payload: GenericWebhookPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    lead = MessagingService.intake_generic_webhook(db, payload)
    return envelope(LeadRead.model_validate(lead))


@router.get("/conversations", response_model=Envelope[list[ConversationSummaryRead]])
def list_conversations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("messaging.read"))],
    params: Annotated[PageParams, Depends(get_page_params)],
    status: str | None = Query(default=None),
    channel_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    assigned_to_me: bool = Query(default=False),
) -> dict[str, object]:
    conversations, meta = InboxService.list_conversations(
        db,
        params,
        current_user_id=current_user.id,
        status=status,
        channel_type=channel_type,
        search=search,
        unread_only=unread_only,
        assigned_to_me=assigned_to_me,
    )
    return envelope([ConversationSummaryRead.model_validate(item) for item in conversations], meta)


@router.get("/conversations/{conversation_id}", response_model=Envelope[ConversationRead])
def get_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("messaging.read"))],
) -> dict[str, object]:
    conversation = InboxService.get_conversation(db, conversation_id)
    return envelope(ConversationRead.model_validate(conversation))


@router.post(
    "/conversations/{conversation_id}/mark-read", response_model=Envelope[ConversationRead]
)
def mark_conversation_read(
    conversation_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("messaging.reply"))],
) -> dict[str, object]:
    conversation = InboxService.mark_read(db, conversation_id, current_user)
    return envelope(ConversationRead.model_validate(conversation))


@router.post("/conversations/{conversation_id}/assign", response_model=Envelope[ConversationRead])
def assign_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationAssignRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("messaging.reply"))],
) -> dict[str, object]:
    conversation = InboxService.assign_conversation(db, conversation_id, payload, current_user)
    return envelope(ConversationRead.model_validate(conversation))


@router.post("/conversations/{conversation_id}/messages", response_model=Envelope[ConversationRead])
def reply_to_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationReplyCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("messaging.reply"))],
) -> dict[str, object]:
    conversation = InboxService.create_outbound_message(db, conversation_id, payload, current_user)
    return envelope(ConversationRead.model_validate(conversation))


@router.get("/channel-accounts", response_model=Envelope[list[ChannelAccountRead]])
def list_channel_accounts(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("channels.manage"))],
    params: Annotated[PageParams, Depends(get_page_params)],
    channel_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> dict[str, object]:
    accounts, meta = InboxService.list_channel_accounts(
        db,
        params,
        channel_type=channel_type,
        is_active=is_active,
    )
    return envelope([ChannelAccountRead.model_validate(item) for item in accounts], meta)


@router.post("/channel-accounts", response_model=Envelope[ChannelAccountRead])
def create_channel_account(
    payload: ChannelAccountCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("channels.manage"))],
) -> dict[str, object]:
    account = InboxService.create_channel_account(db, payload, current_user.id)
    return envelope(ChannelAccountRead.model_validate(account))


@router.patch("/channel-accounts/{account_id}", response_model=Envelope[ChannelAccountRead])
def update_channel_account(
    account_id: uuid.UUID,
    payload: ChannelAccountUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("channels.manage"))],
) -> dict[str, object]:
    account = InboxService.update_channel_account(db, account_id, payload, current_user.id)
    return envelope(ChannelAccountRead.model_validate(account))


@router.post(
    "/channel-accounts/{account_id}/health-check",
    response_model=Envelope[ChannelHealthCheckResult],
)
def channel_account_health_check(
    account_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("channels.manage"))],
) -> dict[str, object]:
    result = EmailChannelService.health_check(db, account_id)
    return envelope(result)


@router.post("/channel-accounts/{account_id}/poll", response_model=Envelope[ChannelPollResult])
def channel_account_poll(
    account_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("channels.manage"))],
    limit: int = Query(default=25, ge=1, le=200),
) -> dict[str, object]:
    result = EmailChannelService.poll_account(db, account_id, limit=limit)
    return envelope(result)
