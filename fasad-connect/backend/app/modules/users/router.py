from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, get_page_params
from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User
from app.modules.users.schemas import (
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.modules.users.service import UserService

router = APIRouter(tags=["users"])


@router.get("/admin/users", response_model=Envelope[list[UserRead]])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("users.manage"))],
    params: Annotated[PageParams, Depends(get_page_params)],
    search: str | None = Query(default=None),
) -> dict[str, object]:
    users, meta = UserService.list_users(db, params, search)
    return envelope([UserRead.model_validate(item) for item in users], meta)


@router.post("/admin/users", response_model=Envelope[UserRead])
def create_user(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("users.manage"))],
) -> dict[str, object]:
    user = UserService.create_user(db, payload, current_user.id)
    return envelope(UserRead.model_validate(user))


@router.patch("/admin/users/{user_id}", response_model=Envelope[UserRead])
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("users.manage"))],
) -> dict[str, object]:
    user = UserService.update_user(db, user_id, payload, current_user.id)
    return envelope(UserRead.model_validate(user))


@router.get("/admin/roles", response_model=Envelope[list[RoleRead]])
def list_roles(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("roles.manage"))],
    params: Annotated[PageParams, Depends(get_page_params)],
) -> dict[str, object]:
    roles, meta = UserService.list_roles(db, params)
    return envelope([RoleRead.model_validate(item) for item in roles], meta)


@router.post("/admin/roles", response_model=Envelope[RoleRead])
def create_role(
    payload: RoleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("roles.manage"))],
) -> dict[str, object]:
    role = UserService.create_role(db, payload, current_user.id)
    return envelope(RoleRead.model_validate(role))


@router.patch("/admin/roles/{role_id}", response_model=Envelope[RoleRead])
def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("roles.manage"))],
) -> dict[str, object]:
    role = UserService.update_role(db, role_id, payload, current_user.id)
    return envelope(RoleRead.model_validate(role))


@router.get("/admin/permissions", response_model=Envelope[list[PermissionRead]])
def list_permissions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("permissions.manage"))],
    params: Annotated[PageParams, Depends(get_page_params)],
) -> dict[str, object]:
    permissions, meta = UserService.list_permissions(db, params)
    return envelope([PermissionRead.model_validate(item) for item in permissions], meta)


@router.post("/admin/permissions", response_model=Envelope[PermissionRead])
def create_permission(
    payload: PermissionCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("permissions.manage"))],
) -> dict[str, object]:
    permission = UserService.create_permission(db, payload, current_user.id)
    return envelope(PermissionRead.model_validate(permission))


@router.patch("/admin/permissions/{permission_id}", response_model=Envelope[PermissionRead])
def update_permission(
    permission_id: uuid.UUID,
    payload: PermissionUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("permissions.manage"))],
) -> dict[str, object]:
    permission = UserService.update_permission(db, permission_id, payload, current_user.id)
    return envelope(PermissionRead.model_validate(permission))
