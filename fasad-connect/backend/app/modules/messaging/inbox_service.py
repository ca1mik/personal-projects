from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.pagination import PageParams, pagination_meta
from app.db.mixins import utcnow
from app.modules.audit.service import AuditService
from app.modules.clients.models import Client
from app.modules.leads.models import Lead
from app.modules.leads.service import LeadService
from app.modules.messaging import outbound
from app.modules.messaging.channel_config import apply_secrets, schedule_next_poll
from app.modules.messaging.models import (
    ChannelAccount,
    Conversation,
    Message,
    MessageAttachment,
)
from app.modules.messaging.schemas import (
    ChannelAccountCreate,
    ChannelAccountUpdate,
    ConversationAssignRequest,
    ConversationReplyCreate,
    UnifiedLeadIn,
)
from app.modules.users.models import User

PHONE_DIGITS_RE = re.compile(r"\D+")


class InboxService:
    @staticmethod
    def _normalize_phone(phone: str | None) -> str | None:
        if not phone:
            return None
        digits = PHONE_DIGITS_RE.sub("", phone)
        if not digits:
            return None
        return f"+{digits}" if phone.strip().startswith("+") else digits

    @staticmethod
    def _channel_name(source_channel: str) -> str:
        """Название канала для интерфейса — по-русски.

        Сюда попадают каналы, которых ещё нет в базе: их создаёт приём заявок.
        ``code`` при этом остаётся английским, на нём завязана привязка сообщений.
        """
        mapping = {
            "website_form": "Форма на сайте",
            "manual_manager_input": "Заявка от менеджера",
            "telegram_bot": "Telegram-бот приёма заявок",
            "telegram": "Telegram оператора",
            "whatsapp": "WhatsApp для клиентов",
            "email": "Почта",
            "email_inbox": "Почтовый ящик",
            "webhook": "Внешний вебхук",
        }
        return mapping.get(source_channel, f"Канал «{source_channel}»")

    @staticmethod
    def _extract_external_context(payload: UnifiedLeadIn) -> tuple[str | None, str | None]:
        raw = payload.raw_payload or {}
        source_channel = payload.source_channel

        if source_channel in {"telegram", "telegram_bot"}:
            callback = raw.get("callback_query") or {}
            if callback:
                message = callback.get("message", {})
                chat = message.get("chat", {})
                return (
                    str(chat.get("id")) if chat.get("id") is not None else None,
                    (
                        str(message.get("message_id") or callback.get("id"))
                        if message.get("message_id") or callback.get("id")
                        else None
                    ),
                )

            message = raw.get("message", {})
            chat = message.get("chat", {})
            return (
                str(chat.get("id")) if chat.get("id") is not None else None,
                (
                    str(message.get("message_id") or raw.get("update_id"))
                    if message.get("message_id") or raw.get("update_id")
                    else None
                ),
            )

        if source_channel == "email":
            sender_email = payload.sender.email if payload.sender and payload.sender.email else None
            return (str(sender_email) if sender_email else None, payload.external_message_id)

        if source_channel == "whatsapp":
            sender_id = payload.sender.external_id if payload.sender else None
            return (sender_id, payload.external_message_id)

        sender_id = payload.sender.external_id if payload.sender else None
        return (sender_id, payload.external_message_id)

    @staticmethod
    def _build_contact_key(
        payload: UnifiedLeadIn,
        lead: Lead,
        external_chat_id: str | None,
    ) -> str:
        sender = payload.sender
        candidates = [
            sender.external_id if sender else None,
            str(sender.email).lower() if sender and sender.email else None,
            InboxService._normalize_phone(sender.phone if sender else None),
            external_chat_id,
            str(lead.client_id) if lead.client_id else None,
            str(lead.id),
        ]
        for candidate in candidates:
            if candidate:
                return f"{payload.source_channel}:{candidate}"
        return f"{payload.source_channel}:{lead.id}"

    @staticmethod
    def _preview_text(text: str) -> str:
        return LeadService.normalize_text(text)[:240]

    @staticmethod
    def _conversation_options():
        return (
            joinedload(Conversation.channel_account).joinedload(ChannelAccount.default_manager),
            joinedload(Conversation.client),
            joinedload(Conversation.source_lead),
            joinedload(Conversation.source_lead).joinedload(Lead.client),
            joinedload(Conversation.assigned_manager),
        )

    @staticmethod
    def _conversation_detail_options():
        return (
            *InboxService._conversation_options(),
            selectinload(Conversation.messages).selectinload(Message.attachments),
            selectinload(Conversation.messages).joinedload(Message.user),
            selectinload(Conversation.messages).joinedload(Message.lead),
        )

    @staticmethod
    def _message_options():
        return (
            joinedload(Message.conversation),
            selectinload(Message.attachments),
        )

    @staticmethod
    def _resolve_channel_account(
        db: Session,
        source_channel: str,
        account_code: str | None = None,
    ) -> ChannelAccount:
        if account_code:
            account = db.scalar(select(ChannelAccount).where(ChannelAccount.code == account_code))
            if account:
                return account

        account = db.scalar(
            select(ChannelAccount)
            .where(
                ChannelAccount.channel_type == source_channel, ChannelAccount.is_active.is_(True)
            )
            .order_by(ChannelAccount.created_at.asc())
        )
        if account:
            return account

        code = f"{source_channel}_default"
        account = db.scalar(select(ChannelAccount).where(ChannelAccount.code == code))
        if account:
            account.is_active = True
            return account

        account = ChannelAccount(
            code=code,
            channel_type=source_channel,
            name=InboxService._channel_name(source_channel),
            description="Канал создан автоматически при приёме первой заявки",
            inbound_mode="webhook",
            is_active=True,
            config_json={"provisioned": "auto"},
        )
        db.add(account)
        db.flush()
        return account

    @staticmethod
    def _sort_messages(conversation: Conversation) -> Conversation:
        conversation.messages = sorted(conversation.messages, key=lambda item: item.created_at)
        return conversation

    @staticmethod
    def get_conversation(db: Session, conversation_id: uuid.UUID) -> Conversation:
        stmt = (
            select(Conversation)
            .options(*InboxService._conversation_detail_options())
            .where(Conversation.id == conversation_id)
        )
        conversation = db.scalar(stmt)
        if not conversation:
            raise NotFoundError("Conversation not found")
        return InboxService._sort_messages(conversation)

    @staticmethod
    def list_conversations(
        db: Session,
        params: PageParams,
        *,
        current_user_id: uuid.UUID | None = None,
        status: str | None = None,
        channel_type: str | None = None,
        search: str | None = None,
        unread_only: bool = False,
        assigned_to_me: bool = False,
    ) -> tuple[list[Conversation], dict[str, Any]]:
        stmt = (
            select(Conversation)
            .join(ChannelAccount, Conversation.channel_account_id == ChannelAccount.id)
            .outerjoin(Client, Conversation.client_id == Client.id)
            .options(*InboxService._conversation_options())
            .order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc())
        )
        count_stmt = (
            select(func.count())
            .select_from(Conversation)
            .join(ChannelAccount, Conversation.channel_account_id == ChannelAccount.id)
            .outerjoin(Client, Conversation.client_id == Client.id)
        )

        if status:
            stmt = stmt.where(Conversation.status == status)
            count_stmt = count_stmt.where(Conversation.status == status)
        if channel_type:
            stmt = stmt.where(ChannelAccount.channel_type == channel_type)
            count_stmt = count_stmt.where(ChannelAccount.channel_type == channel_type)
        if unread_only:
            stmt = stmt.where(Conversation.unread_count > 0)
            count_stmt = count_stmt.where(Conversation.unread_count > 0)
        if assigned_to_me and current_user_id:
            stmt = stmt.where(Conversation.assigned_manager_id == current_user_id)
            count_stmt = count_stmt.where(Conversation.assigned_manager_id == current_user_id)
        if search:
            pattern = f"%{search.lower()}%"
            criteria = or_(
                func.lower(func.coalesce(Conversation.subject, "")).like(pattern),
                func.lower(func.coalesce(Conversation.last_message_preview, "")).like(pattern),
                func.lower(func.coalesce(Conversation.participant_name, "")).like(pattern),
                func.lower(func.coalesce(Conversation.participant_email, "")).like(pattern),
                func.lower(func.coalesce(Conversation.participant_phone, "")).like(pattern),
                func.lower(func.coalesce(Client.full_name, "")).like(pattern),
            )
            stmt = stmt.where(criteria)
            count_stmt = count_stmt.where(criteria)

        total = db.scalar(count_stmt) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).unique().all()
        return items, pagination_meta(total, params)

    @staticmethod
    def list_channel_accounts(
        db: Session,
        params: PageParams,
        *,
        channel_type: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[ChannelAccount], dict[str, Any]]:
        stmt = select(ChannelAccount).options(joinedload(ChannelAccount.default_manager))
        count_stmt = select(func.count()).select_from(ChannelAccount)
        if channel_type:
            stmt = stmt.where(ChannelAccount.channel_type == channel_type)
            count_stmt = count_stmt.where(ChannelAccount.channel_type == channel_type)
        if is_active is not None:
            stmt = stmt.where(ChannelAccount.is_active.is_(is_active))
            count_stmt = count_stmt.where(ChannelAccount.is_active.is_(is_active))
        stmt = stmt.order_by(ChannelAccount.channel_type.asc(), ChannelAccount.name.asc())
        total = db.scalar(count_stmt) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return items, pagination_meta(total, params)

    @staticmethod
    def create_channel_account(
        db: Session,
        payload: ChannelAccountCreate,
        acting_user_id: uuid.UUID,
    ) -> ChannelAccount:
        existing = db.scalar(select(ChannelAccount).where(ChannelAccount.code == payload.code))
        if existing:
            raise ConflictError("Channel account code already exists")
        account = ChannelAccount(**payload.model_dump(exclude={"secrets"}))
        changed_secrets = apply_secrets(account, payload.secrets)
        db.add(account)
        db.flush()
        if account.is_active:
            schedule_next_poll(account)
        AuditService.log_event(
            db,
            entity_type="channel_account",
            entity_id=str(account.id),
            action="create_channel_account",
            user_id=str(acting_user_id),
            new_value={
                "code": account.code,
                "channel_type": account.channel_type,
                "secrets_set": changed_secrets,
            },
        )
        db.commit()
        return (
            db.scalar(
                select(ChannelAccount)
                .options(joinedload(ChannelAccount.default_manager))
                .where(ChannelAccount.id == account.id)
            )
            or account
        )

    @staticmethod
    def update_channel_account(
        db: Session,
        account_id: uuid.UUID,
        payload: ChannelAccountUpdate,
        acting_user_id: uuid.UUID,
    ) -> ChannelAccount:
        account = db.get(ChannelAccount, account_id)
        if not account:
            raise NotFoundError("Channel account not found")
        old_value = {
            "name": account.name,
            "is_active": account.is_active,
            "inbound_mode": account.inbound_mode,
            "default_manager_id": (
                str(account.default_manager_id) if account.default_manager_id else None
            ),
        }
        for key, value in payload.model_dump(exclude_unset=True, exclude={"secrets"}).items():
            setattr(account, key, value)
        changed_secrets = apply_secrets(account, payload.secrets)
        if account.is_active and account.next_poll_at is None:
            schedule_next_poll(account)
        AuditService.log_event(
            db,
            entity_type="channel_account",
            entity_id=str(account.id),
            action="update_channel_account",
            user_id=str(acting_user_id),
            old_value=old_value,
            new_value={
                "name": account.name,
                "is_active": account.is_active,
                "inbound_mode": account.inbound_mode,
                "default_manager_id": (
                    str(account.default_manager_id) if account.default_manager_id else None
                ),
                "secrets_set": changed_secrets,
            },
        )
        db.commit()
        return (
            db.scalar(
                select(ChannelAccount)
                .options(joinedload(ChannelAccount.default_manager))
                .where(ChannelAccount.id == account.id)
            )
            or account
        )

    @staticmethod
    def _find_message_by_external_id(
        db: Session,
        source_channel: str,
        external_message_id: str | None,
    ) -> Message | None:
        if not external_message_id:
            return None
        return db.scalar(
            select(Message)
            .options(*InboxService._message_options())
            .where(
                Message.source_channel == source_channel,
                Message.external_message_id == external_message_id,
            )
        )

    @staticmethod
    def record_inbound_lead(
        db: Session,
        payload: UnifiedLeadIn,
        lead: Lead,
        acting_user_id: str | None = None,
    ) -> Conversation:
        existing_message = InboxService._find_message_by_external_id(
            db,
            payload.source_channel,
            payload.external_message_id,
        )
        if existing_message:
            conversation = InboxService.get_conversation(db, existing_message.conversation_id)
            if conversation.client_id is None and lead.client_id is not None:
                conversation.client_id = lead.client_id
            if conversation.source_lead_id is None:
                conversation.source_lead_id = lead.id
            db.commit()
            return InboxService.get_conversation(db, conversation.id)

        account = InboxService._resolve_channel_account(
            db, payload.source_channel, payload.channel_account_code
        )
        external_chat_id, external_thread_id = InboxService._extract_external_context(payload)
        contact_key = InboxService._build_contact_key(payload, lead, external_chat_id)

        conversation = db.scalar(
            select(Conversation)
            .options(*InboxService._conversation_options())
            .where(
                Conversation.channel_account_id == account.id,
                Conversation.contact_key == contact_key,
            )
            .order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc())
        )

        if conversation is None:
            conversation = Conversation(
                channel_account_id=account.id,
                client_id=lead.client_id,
                source_lead_id=lead.id,
                assigned_manager_id=lead.assigned_manager_id or account.default_manager_id,
                status="needs_reply",
                contact_key=contact_key,
                external_chat_id=external_chat_id,
                external_thread_id=external_thread_id,
                subject=payload.subject or lead.subject,
                participant_name=payload.sender.full_name if payload.sender else None,
                participant_phone=payload.sender.phone if payload.sender else None,
                participant_email=(
                    str(payload.sender.email) if payload.sender and payload.sender.email else None
                ),
                participant_external_id=payload.sender.external_id if payload.sender else None,
                unread_count=0,
            )
            db.add(conversation)
            db.flush()
            AuditService.log_event(
                db,
                entity_type="conversation",
                entity_id=str(conversation.id),
                action="create_conversation",
                user_id=acting_user_id,
                new_value={"channel_type": payload.source_channel, "source_lead_id": str(lead.id)},
            )
        else:
            conversation.client_id = lead.client_id or conversation.client_id
            conversation.source_lead_id = conversation.source_lead_id or lead.id
            conversation.assigned_manager_id = (
                conversation.assigned_manager_id
                or lead.assigned_manager_id
                or account.default_manager_id
            )
            conversation.external_chat_id = conversation.external_chat_id or external_chat_id
            conversation.external_thread_id = conversation.external_thread_id or external_thread_id
            conversation.subject = conversation.subject or payload.subject or lead.subject
            conversation.participant_name = (
                conversation.participant_name
                or (payload.sender.full_name if payload.sender else None)
                or (lead.client.full_name if lead.client else None)
            )
            conversation.participant_phone = conversation.participant_phone or (
                payload.sender.phone if payload.sender else None
            )
            conversation.participant_email = conversation.participant_email or (
                str(payload.sender.email) if payload.sender and payload.sender.email else None
            )
            conversation.participant_external_id = conversation.participant_external_id or (
                payload.sender.external_id if payload.sender else None
            )

        raw_text = payload.text or lead.raw_text
        message = Message(
            conversation_id=conversation.id,
            lead_id=lead.id,
            direction="inbound",
            status="received",
            source_channel=payload.source_channel,
            external_message_id=payload.external_message_id,
            subject=payload.subject or lead.subject,
            body_text=raw_text,
            normalized_text=LeadService.normalize_text(raw_text),
            raw_payload_json=payload.raw_payload or lead.parsed_payload_json,
            sender_name=payload.sender.full_name if payload.sender else None,
            sender_phone=payload.sender.phone if payload.sender else None,
            sender_email=(
                str(payload.sender.email) if payload.sender and payload.sender.email else None
            ),
            sender_external_id=payload.sender.external_id if payload.sender else None,
        )
        db.add(message)
        db.flush()

        for attachment in lead.attachments:
            db.add(
                MessageAttachment(
                    message_id=message.id,
                    file_name=attachment.file_name,
                    file_path=attachment.file_path,
                    mime_type=attachment.mime_type,
                    size_bytes=attachment.size_bytes,
                )
            )

        conversation.status = "needs_reply"
        conversation.unread_count = int(conversation.unread_count or 0) + 1
        conversation.last_message_at = message.created_at
        conversation.last_message_preview = InboxService._preview_text(message.body_text)

        AuditService.log_event(
            db,
            entity_type="message",
            entity_id=str(message.id),
            action="create_inbound_message",
            user_id=acting_user_id,
            new_value={"conversation_id": str(conversation.id), "lead_id": str(lead.id)},
        )
        db.commit()
        return InboxService.get_conversation(db, conversation.id)

    @staticmethod
    def mark_read(
        db: Session,
        conversation_id: uuid.UUID,
        current_user: User,
    ) -> Conversation:
        conversation = InboxService.get_conversation(db, conversation_id)
        conversation.unread_count = 0
        if conversation.assigned_manager_id is None:
            conversation.assigned_manager_id = current_user.id
        if conversation.status == "needs_reply":
            conversation.status = "open"
        AuditService.log_event(
            db,
            entity_type="conversation",
            entity_id=str(conversation.id),
            action="mark_conversation_read",
            user_id=str(current_user.id),
            new_value={"status": conversation.status, "unread_count": 0},
        )
        db.commit()
        return InboxService.get_conversation(db, conversation.id)

    @staticmethod
    def assign_conversation(
        db: Session,
        conversation_id: uuid.UUID,
        payload: ConversationAssignRequest,
        current_user: User,
    ) -> Conversation:
        conversation = InboxService.get_conversation(db, conversation_id)
        old_value = (
            str(conversation.assigned_manager_id) if conversation.assigned_manager_id else None
        )
        conversation.assigned_manager_id = payload.assigned_manager_id
        if conversation.source_lead is not None:
            conversation.source_lead.assigned_manager_id = payload.assigned_manager_id
        AuditService.log_event(
            db,
            entity_type="conversation",
            entity_id=str(conversation.id),
            action="assign_conversation",
            user_id=str(current_user.id),
            old_value={"assigned_manager_id": old_value},
            new_value={
                "assigned_manager_id": (
                    str(payload.assigned_manager_id) if payload.assigned_manager_id else None
                )
            },
        )
        db.commit()
        return InboxService.get_conversation(db, conversation.id)

    @staticmethod
    def create_outbound_message(
        db: Session,
        conversation_id: uuid.UUID,
        payload: ConversationReplyCreate,
        current_user: User,
    ) -> Conversation:
        conversation = InboxService.get_conversation(db, conversation_id)
        if not payload.body_text.strip():
            raise AppError("Message body must not be empty")

        body_text = payload.body_text.strip()
        delivery = outbound.dispatch_reply(
            conversation,
            body_text=body_text,
            subject=payload.subject,
        )

        message = Message(
            conversation_id=conversation.id,
            lead_id=conversation.source_lead_id,
            user_id=current_user.id,
            direction="outbound",
            status=delivery.status,
            source_channel=conversation.channel_account.channel_type,
            external_message_id=delivery.external_message_id,
            subject=payload.subject or conversation.subject,
            body_text=body_text,
            normalized_text=LeadService.normalize_text(payload.body_text),
            raw_payload_json=delivery.raw_payload or {"mode": "crm_mock_outbound"},
            sender_name=current_user.full_name,
            sender_email=current_user.email,
            sender_external_id=str(current_user.id),
            delivered_at=utcnow() if delivery.status == outbound.SENT_STATUS else None,
            delivery_error=delivery.error,
        )
        db.add(message)
        db.flush()

        conversation.assigned_manager_id = conversation.assigned_manager_id or current_user.id
        if conversation.source_lead is not None:
            conversation.source_lead.assigned_manager_id = (
                conversation.source_lead.assigned_manager_id or current_user.id
            )
        conversation.unread_count = 0
        # A failed send leaves the dialog needing a reply — the client got nothing.
        conversation.status = (
            "needs_reply" if delivery.status == outbound.FAILED_STATUS else "waiting_client"
        )
        conversation.last_message_at = message.created_at
        conversation.last_message_preview = InboxService._preview_text(message.body_text)

        AuditService.log_event(
            db,
            entity_type="message",
            entity_id=str(message.id),
            action="create_outbound_message",
            user_id=str(current_user.id),
            new_value={
                "conversation_id": str(conversation.id),
                "direction": "outbound",
                "delivery_status": delivery.status,
            },
        )
        db.commit()

        if delivery.status == outbound.FAILED_STATUS:
            # The attempt is persisted above, so the manager keeps a record of it,
            # but the request still fails loudly instead of pretending success.
            raise AppError(f"Письмо не отправлено: {delivery.error}", status_code=502)

        return InboxService.get_conversation(db, conversation.id)
