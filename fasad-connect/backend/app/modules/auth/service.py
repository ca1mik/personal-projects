from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.modules.auth.schemas import AuthResponse, TokenPayload
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService


class AuthService:
    @staticmethod
    def login(db: Session, login: str, password: str) -> AuthResponse:
        user = UserService.get_by_login(db, login)
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid credentials")
        if not user.is_active:
            raise UnauthorizedError("User is inactive")
        token = create_access_token(str(user.id))
        return AuthResponse(
            token=TokenPayload(access_token=token), user=UserRead.model_validate(user)
        )
