"""Symmetric encryption for channel credentials.

Channel accounts store third-party credentials (IMAP/SMTP passwords, bot tokens,
provider API keys). They are encrypted at rest with Fernet, keyed by
``CHANNEL_SECRET_KEY`` from settings.

The raw setting is an arbitrary human-typed string, so it is stretched into a
valid 32-byte Fernet key with SHA-256. Stored values carry the ``enc:v1:``
prefix, which lets ``decrypt_secret`` transparently pass through plaintext left
by manual DB edits instead of raising.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.exceptions import AppError

SECRET_PREFIX = "enc:v1:"
INSECURE_SECRET_KEYS = {"", "change-me", "changeme", "secret"}


@lru_cache
def _get_fernet(secret_key: str) -> Fernet:
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def channel_secret_key_is_insecure() -> bool:
    return get_settings().channel_secret_key.strip().lower() in INSECURE_SECRET_KEYS


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    if value.startswith(SECRET_PREFIX):
        return value
    fernet = _get_fernet(get_settings().channel_secret_key)
    token = fernet.encrypt(value.encode("utf-8")).decode("ascii")
    return f"{SECRET_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    if not value.startswith(SECRET_PREFIX):
        return value
    fernet = _get_fernet(get_settings().channel_secret_key)
    try:
        return fernet.decrypt(value[len(SECRET_PREFIX) :].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError(
            "Не удалось расшифровать секрет канала. Проверьте CHANNEL_SECRET_KEY — "
            "он должен совпадать с ключом, которым секрет был сохранён."
        ) from exc


def encrypt_secret_map(values: dict[str, str | None]) -> dict[str, str]:
    return {key: encrypt_secret(value) for key, value in values.items() if value}
