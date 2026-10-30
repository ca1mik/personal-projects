from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.modules.shared.schemas import ORMModel


class PermissionRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str


class RoleRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    permissions: list[PermissionRead] = Field(default_factory=list)


class UserRead(ORMModel):
    id: uuid.UUID
    full_name: str
    email: str
    login: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    role: RoleRead


class PermissionCreate(BaseModel):
    code: str = Field(min_length=3, max_length=100)
    name: str = Field(min_length=2, max_length=100)


class PermissionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)


class RoleCreate(BaseModel):
    code: str = Field(min_length=3, max_length=50)
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None
    permission_codes: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None
    permission_codes: list[str] | None = None


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    login: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=6, max_length=255)
    role_id: uuid.UUID
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: EmailStr | None = None
    login: str | None = Field(default=None, min_length=2, max_length=100)
    password: str | None = Field(default=None, min_length=6, max_length=255)
    role_id: uuid.UUID | None = None
    is_active: bool | None = None
