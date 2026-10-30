"""Low-level IMAP/SMTP I/O for the email channel.

Everything that touches a socket lives here so the service layer above can be
tested by patching these three functions: :func:`fetch_messages`,
:func:`send_message`, :func:`check_connection`.
"""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.modules.messaging.schemas import (
    ChannelHealthCheckResult,
    ChannelHealthCheckStep,
    EmailChannelConfig,
)


@dataclass(frozen=True)
class FetchedEmail:
    uid: str
    raw: bytes


def _imap_criteria(config: EmailChannelConfig) -> str:
    from imap_tools import AND

    if config.unseen_only:
        return AND(seen=False)
    from datetime import UTC, datetime, timedelta

    since = (datetime.now(UTC) - timedelta(days=config.since_days)).date()
    return AND(date_gte=since)


def fetch_messages(
    config: EmailChannelConfig,
    password: str,
    *,
    limit: int,
) -> list[FetchedEmail]:
    """Fetch raw messages from IMAP, newest last.

    Marking as seen is done here (and only when configured) because it is the
    IMAP session that owns the flag; the caller is already past the point where
    a failure would lose a message, since intake dedupes on ``Message-ID``.
    """
    from imap_tools import MailBox, MailBoxUnencrypted

    settings = get_settings()
    imap = config.imap
    box_factory = MailBox if imap.ssl else MailBoxUnencrypted
    fetched: list[FetchedEmail] = []

    with box_factory(
        imap.host, port=imap.port, timeout=settings.email_connect_timeout_seconds
    ).login(imap.login, password, initial_folder=imap.folder) as mailbox:
        for message in mailbox.fetch(
            _imap_criteria(config),
            limit=limit,
            mark_seen=config.mark_seen,
            bulk=True,
            reverse=False,
        ):
            fetched.append(FetchedEmail(uid=str(message.uid or ""), raw=message.obj.as_bytes()))

    return fetched


def _smtp_connection(config: EmailChannelConfig) -> smtplib.SMTP:
    settings = get_settings()
    smtp = config.smtp
    timeout = settings.email_connect_timeout_seconds
    if smtp.security == "ssl":
        return smtplib.SMTP_SSL(
            smtp.host, smtp.port, timeout=timeout, context=ssl.create_default_context()
        )
    connection = smtplib.SMTP(smtp.host, smtp.port, timeout=timeout)
    if smtp.security == "starttls":
        connection.starttls(context=ssl.create_default_context())
        connection.ehlo()
    return connection


def build_message(
    config: EmailChannelConfig,
    *,
    to_email: str,
    subject: str,
    body_text: str,
    in_reply_to: str | None = None,
) -> EmailMessage:
    smtp = config.smtp
    from_email = smtp.from_email or smtp.login
    message = EmailMessage()
    message["From"] = formataddr((smtp.from_name, from_email)) if smtp.from_name else from_email
    message["To"] = to_email
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=from_email.split("@")[-1] or None)
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to
    message.set_content(body_text)
    return message


def send_message(
    config: EmailChannelConfig,
    password: str,
    *,
    to_email: str,
    subject: str,
    body_text: str,
    in_reply_to: str | None = None,
) -> str:
    """Send one message over SMTP and return its ``Message-ID``."""
    message = build_message(
        config,
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        in_reply_to=in_reply_to,
    )
    with _smtp_connection(config) as connection:
        if config.smtp.login and password:
            connection.login(config.smtp.login, password)
        connection.send_message(message)
    return str(message["Message-ID"])


def check_connection(
    config: EmailChannelConfig,
    *,
    imap_password: str,
    smtp_password: str,
) -> ChannelHealthCheckResult:
    """Log in to IMAP and SMTP without transferring mail."""
    from imap_tools import MailBox, MailBoxUnencrypted

    settings = get_settings()
    imap_step: ChannelHealthCheckStep
    smtp_step: ChannelHealthCheckStep

    if not config.imap.host:
        imap_step = ChannelHealthCheckStep(ok=False, detail="IMAP-хост не заполнен")
    else:
        try:
            box_factory = MailBox if config.imap.ssl else MailBoxUnencrypted
            with box_factory(
                config.imap.host,
                port=config.imap.port,
                timeout=settings.email_connect_timeout_seconds,
            ).login(config.imap.login, imap_password, initial_folder=config.imap.folder):
                pass
            imap_step = ChannelHealthCheckStep(
                ok=True, detail=f"Подключение к папке {config.imap.folder} успешно"
            )
        except Exception as exc:  # noqa: BLE001 - any transport failure is a report line
            imap_step = ChannelHealthCheckStep(ok=False, detail=f"Ошибка IMAP: {exc}")

    if not config.smtp.host:
        smtp_step = ChannelHealthCheckStep(ok=False, detail="SMTP-хост не заполнен")
    else:
        try:
            with _smtp_connection(config) as connection:
                if config.smtp.login and smtp_password:
                    connection.login(config.smtp.login, smtp_password)
            smtp_step = ChannelHealthCheckStep(ok=True, detail="Авторизация на SMTP успешна")
        except Exception as exc:  # noqa: BLE001 - any transport failure is a report line
            smtp_step = ChannelHealthCheckStep(ok=False, detail=f"Ошибка SMTP: {exc}")

    return ChannelHealthCheckResult(
        ok=imap_step.ok and smtp_step.ok,
        imap=imap_step,
        smtp=smtp_step,
    )


def require_email_config(config: EmailChannelConfig) -> None:
    missing: list[str] = []
    if not config.imap.host:
        missing.append("IMAP host")
    if not config.imap.login:
        missing.append("IMAP login")
    if missing:
        raise AppError("Не заполнены настройки канала: " + ", ".join(missing))
