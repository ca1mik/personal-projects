"""Authentication for external intake and webhook endpoints."""

from __future__ import annotations

import hmac
import logging
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.modules.users.models import User
from app.modules.users.service import UserService

bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger("app.intake_auth")


def require_intake_access(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    webhook_token: Annotated[str | None, Header(alias="X-Fasad-Webhook-Token")] = None,
    telegram_token: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> None:
    configured = get_settings().public_intake_secret
    supplied = webhook_token or telegram_token
    if configured and supplied and hmac.compare_digest(supplied, configured):
        return
    if credentials and credentials.scheme.lower() == "bearer":
        subject = decode_token(credentials.credentials).get("sub")
        if subject:
            user = UserService.get_by_login(db, subject)
            if user is None:
                import uuid

                try:
                    user = db.get(User, uuid.UUID(subject))
                except ValueError:
                    pass
            if user and user.is_active:
                permissions = {permission.code for permission in user.role.permissions}
                if user.role.code == "admin" or "leads.manage" in permissions:
                    return
                raise ForbiddenError()
    if supplied and configured:
        logger.warning("intake_auth_rejected peer=%s path=%s reason=invalid_secret", request.client.host if request.client else "unknown", request.url.path)
        raise UnauthorizedError("Неверный ключ приёма заявок")
    if not configured:
        logger.warning("intake_auth_rejected peer=%s path=%s reason=not_configured", request.client.host if request.client else "unknown", request.url.path)
        raise AppError("Приём внешних заявок отключён: PUBLIC_INTAKE_SECRET не задан", 503)
    logger.warning("intake_auth_rejected peer=%s path=%s reason=missing_credentials", request.client.host if request.client else "unknown", request.url.path)
    raise UnauthorizedError("Требуется вход или ключ приёма заявок")
