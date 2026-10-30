"""Orchestration for the email channel: poll, send, health-check.

Nothing here reaches into the intake core — polled mail is converted into the
existing :class:`EmailPayload` and handed to ``normalize_email_payload`` and
``MessagingService``, exactly like the ``/messaging/email/intake`` endpoint.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.modules.messaging import email_transport
from app.modules.messaging.adapters import normalize_email_payload
from app.modules.messaging.channel_config import (
    get_secret,
    load_email_config,
    record_poll_failure,
    record_poll_success,
)
from app.modules.messaging.email_parser import parse_email_bytes
from app.modules.messaging.models import ChannelAccount, Message
from app.modules.messaging.schemas import (
    ChannelHealthCheckResult,
    ChannelPollResult,
    EmailChannelConfig,
)

EMAIL_CHANNEL_TYPE = "email"


class EmailChannelService:
    @staticmethod
    def get_account(db: Session, account_id: uuid.UUID) -> ChannelAccount:
        account = db.get(ChannelAccount, account_id)
        if not account:
            raise NotFoundError("Channel account not found")
        return account

    @staticmethod
    def require_email_account(db: Session, account_id: uuid.UUID) -> ChannelAccount:
        account = EmailChannelService.get_account(db, account_id)
        if account.channel_type != EMAIL_CHANNEL_TYPE:
            raise AppError("Этот канал не является email-каналом")
        return account

    @staticmethod
    def list_pollable_accounts(db: Session) -> list[ChannelAccount]:
        """Active email accounts that have enough config to be polled."""
        accounts = db.scalars(
            select(ChannelAccount).where(
                ChannelAccount.channel_type == EMAIL_CHANNEL_TYPE,
                ChannelAccount.is_active.is_(True),
            )
        ).all()
        pollable: list[ChannelAccount] = []
        for account in accounts:
            config = EmailChannelConfig.model_validate(account.config_json or {})
            if config.imap.host and config.imap.login and get_secret(account, "imap_password"):
                pollable.append(account)
        return pollable

    @staticmethod
    def _already_ingested(db: Session, message_id: str | None) -> bool:
        if not message_id:
            return False
        return (
            db.scalar(
                select(Message.id).where(
                    Message.source_channel == EMAIL_CHANNEL_TYPE,
                    Message.external_message_id == message_id,
                )
            )
            is not None
        )

    @staticmethod
    def health_check(db: Session, account_id: uuid.UUID) -> ChannelHealthCheckResult:
        account = EmailChannelService.require_email_account(db, account_id)
        config = load_email_config(account)
        result = email_transport.check_connection(
            config,
            imap_password=get_secret(account, "imap_password"),
            smtp_password=get_secret(account, "smtp_password"),
        )
        if result.ok:
            account.last_error = None
            account.last_error_at = None
        else:
            failures = [step.detail for step in (result.imap, result.smtp) if step and not step.ok]
            record_poll_failure(account, "; ".join(failures))
        db.commit()
        return result

    @staticmethod
    def poll_account(
        db: Session, account_id: uuid.UUID, *, limit: int | None = None
    ) -> ChannelPollResult:
        """Fetch new mail for one account and push it through intake.

        Each message is committed by the intake layer independently, so one bad
        message cannot roll back the ones already ingested in this run.
        """
        # Imported here: messaging.service imports adapters/inbox_service, and a
        # module-level import would close an import cycle through this module.
        from app.modules.messaging.service import MessagingService

        settings = get_settings()
        account = EmailChannelService.require_email_account(db, account_id)
        config = load_email_config(account)
        email_transport.require_email_config(config)

        password = get_secret(account, "imap_password")
        if not password:
            raise AppError("Для канала не задан пароль IMAP")

        max_attachment_bytes = settings.email_max_attachment_mb * 1024 * 1024
        batch_limit = limit or settings.email_poll_batch_limit

        try:
            fetched = email_transport.fetch_messages(config, password, limit=batch_limit)
        except Exception as exc:  # noqa: BLE001 - transport failure is reported, not raised
            record_poll_failure(account, str(exc))
            db.commit()
            return ChannelPollResult(
                account_id=account.id, fetched=0, created=0, skipped=0, error=str(exc)
            )

        created = 0
        skipped = 0
        errors: list[str] = []
        last_uid: str | None = None

        for item in fetched:
            last_uid = item.uid or last_uid
            try:
                payload = parse_email_bytes(
                    item.raw,
                    fallback_message_id=(f"imap:{account.code}:{item.uid}" if item.uid else None),
                    max_attachment_bytes=max_attachment_bytes,
                )
                if EmailChannelService._already_ingested(db, payload.message_id):
                    skipped += 1
                    continue
                unified = normalize_email_payload(payload)
                unified.channel_account_code = account.code
                MessagingService.intake_unified(db, unified)
                created += 1
            except Exception as exc:  # noqa: BLE001 - one bad mail must not stop the batch
                db.rollback()
                skipped += 1
                errors.append(f"uid={item.uid}: {exc}")

        account = EmailChannelService.get_account(db, account_id)
        if errors:
            record_poll_failure(account, "; ".join(errors[:5]))
        else:
            record_poll_success(account, cursor=last_uid)
        db.commit()

        return ChannelPollResult(
            account_id=account_id,
            fetched=len(fetched),
            created=created,
            skipped=skipped,
            error="; ".join(errors[:5]) or None,
        )

    @staticmethod
    def send_email(
        account: ChannelAccount,
        *,
        to_email: str,
        subject: str,
        body_text: str,
        in_reply_to: str | None = None,
    ) -> str:
        config = load_email_config(account)
        if not config.smtp.host:
            raise AppError("Для канала не настроен SMTP-сервер — ответ отправить нельзя")
        if not (config.smtp.from_email or config.smtp.login):
            raise AppError("Для канала не задан адрес отправителя (SMTP from)")
        return email_transport.send_message(
            config,
            get_secret(account, "smtp_password"),
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            in_reply_to=in_reply_to,
        )
