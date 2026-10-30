"""Typed access to :class:`ChannelAccount` configuration and credentials.

``config_json`` holds everything safe to show in the admin UI; ``secrets_json``
holds Fernet-encrypted credentials that are never serialized to the API.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.exceptions import AppError
from app.modules.messaging.models import ChannelAccount
from app.modules.messaging.schemas import ChannelSecretsIn, EmailChannelConfig

EMAIL_SECRET_KEYS = ("imap_password", "smtp_password")


def load_email_config(account: ChannelAccount) -> EmailChannelConfig:
    try:
        return EmailChannelConfig.model_validate(account.config_json or {})
    except ValidationError as exc:
        raise AppError(
            f"Некорректная конфигурация канала «{account.code}»: {exc.error_count()} ошибок. "
            "Проверьте настройки IMAP/SMTP в админке."
        ) from exc


def get_secret(account: ChannelAccount, key: str) -> str:
    return decrypt_secret((account.secrets_json or {}).get(key))


def apply_secrets(account: ChannelAccount, secrets: ChannelSecretsIn | None) -> list[str]:
    """Merge submitted credentials into the account, returning changed keys.

    Omitted or blank values keep the stored secret, so the admin form can be
    re-submitted without retyping passwords.
    """
    if secrets is None:
        return []

    stored = dict(account.secrets_json or {})
    changed: list[str] = []
    for key, value in secrets.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if value == "":
            if stored.pop(key, None) is not None:
                changed.append(key)
            continue
        stored[key] = encrypt_secret(value)
        changed.append(key)

    if changed:
        account.secrets_json = stored
    return changed


def poll_interval_seconds(account: ChannelAccount) -> int:
    settings = get_settings()
    raw = (account.config_json or {}).get(
        "poll_interval_seconds", settings.channel_poll_default_interval_seconds
    )
    try:
        interval = int(raw)
    except (TypeError, ValueError):
        interval = settings.channel_poll_default_interval_seconds
    return max(settings.channel_poll_min_interval_seconds, interval)


def schedule_next_poll(account: ChannelAccount, *, from_time: datetime | None = None) -> datetime:
    moment = from_time or datetime.now(UTC)
    account.next_poll_at = moment + timedelta(seconds=poll_interval_seconds(account))
    return account.next_poll_at


def record_poll_success(account: ChannelAccount, *, cursor: str | None = None) -> None:
    now = datetime.now(UTC)
    account.last_polled_at = now
    account.last_success_at = now
    account.last_error = None
    account.last_error_at = None
    if cursor:
        account.poll_cursor = cursor
    schedule_next_poll(account, from_time=now)


def record_poll_failure(account: ChannelAccount, error: str) -> None:
    now = datetime.now(UTC)
    account.last_polled_at = now
    account.last_error = error[:2000]
    account.last_error_at = now
    schedule_next_poll(account, from_time=now)
