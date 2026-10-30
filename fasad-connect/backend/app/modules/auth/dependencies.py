from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.modules.users.models import User
from app.modules.users.service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    payload = decode_token(token)
    subject = payload.get("sub")
    if not subject:
        raise UnauthorizedError()
    user = UserService.get_by_login(db, subject)
    if user is None:
        import uuid

        try:
            user = UserService.get_user_by_id(db, uuid.UUID(subject))
        except Exception as exc:
            raise UnauthorizedError() from exc
    if not user.is_active:
        raise UnauthorizedError("User is inactive")
    return user


def require_roles(*role_codes: str) -> Callable[[User], User]:
    def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if role_codes and current_user.role.code not in role_codes:
            raise ForbiddenError()
        return current_user

    return dependency


def require_permissions(*permission_codes: str) -> Callable[[User], User]:
    """Проверка прав на эндпоинте.

    Нехватка прав — это 403, а не 401. Разница не формальная: на 401 фронт
    уводит на страницу входа, считая, что сессия протухла, и работник цеха,
    открывший чужой раздел по прямой ссылке, попадал в петлю «войди — снова
    войди». На 403 он остаётся в системе и видит, что раздел просто не его.
    """

    def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role.code == "admin":
            return current_user
        granted_codes = {item.code for item in current_user.role.permissions}
        if permission_codes and not granted_codes.intersection(permission_codes):
            raise ForbiddenError()
        return current_user

    return dependency
