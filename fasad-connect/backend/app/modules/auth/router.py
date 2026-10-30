from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import AuthResponse, LoginRequest
from app.modules.auth.service import AuthService
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User
from app.modules.users.schemas import UserRead

router = APIRouter()


@router.post("/login", response_model=Envelope[AuthResponse])
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    return envelope(AuthService.login(db, payload.login, payload.password))


@router.get("/me", response_model=Envelope[UserRead])
def me(current_user: Annotated[User, Depends(get_current_user)]) -> dict[str, object]:
    return envelope(UserRead.model_validate(current_user))
