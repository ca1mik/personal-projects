from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.users.schemas import UserRead


class LoginRequest(BaseModel):
    login: str = Field(min_length=2)
    password: str = Field(min_length=4)


class TokenPayload(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    token: TokenPayload
    user: UserRead
