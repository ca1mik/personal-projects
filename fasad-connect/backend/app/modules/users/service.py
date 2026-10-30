from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PageParams
from app.core.security import hash_password
from app.modules.audit.service import AuditService
from app.modules.users.models import Permission, Role, User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    PermissionCreate,
    PermissionUpdate,
    RoleCreate,
    RoleUpdate,
    UserCreate,
    UserUpdate,
)


class UserService:
    @staticmethod
    def get_user_by_id(db: Session, user_id: uuid.UUID) -> User:
        user = UserRepository.get_by_id(db, user_id)
        if not user:
            raise NotFoundError("User not found")
        return user

    @staticmethod
    def get_by_login(db: Session, login_or_email: str) -> User | None:
        return UserRepository.get_by_login(db, login_or_email)

    @staticmethod
    def list_users(
        db: Session, params: PageParams, search: str | None = None
    ) -> tuple[list[User], dict]:
        return UserRepository.list_users(db, params, search)

    @staticmethod
    def create_user(
        db: Session, payload: UserCreate, acting_user_id: uuid.UUID | None = None
    ) -> User:
        existing = db.scalar(
            select(User).where(or_(User.email == payload.email, User.login == payload.login))
        )
        if existing:
            raise ConflictError("User with this email or login already exists")
        role = UserRepository.get_role_by_id(db, payload.role_id)
        if not role:
            raise NotFoundError("Role not found")
        user = User(
            full_name=payload.full_name,
            email=str(payload.email),
            login=payload.login,
            password_hash=hash_password(payload.password),
            role_id=payload.role_id,
            is_active=payload.is_active,
        )
        db.add(user)
        db.flush()
        AuditService.log_event(
            db,
            entity_type="user",
            entity_id=str(user.id),
            action="create_user",
            user_id=str(acting_user_id) if acting_user_id else None,
            new_value={"login": user.login, "email": user.email, "role_id": str(user.role_id)},
        )
        db.commit()
        return UserService.get_user_by_id(db, user.id)

    @staticmethod
    def update_user(
        db: Session,
        user_id: uuid.UUID,
        payload: UserUpdate,
        acting_user_id: uuid.UUID | None = None,
    ) -> User:
        user = UserService.get_user_by_id(db, user_id)
        old_value = {
            "role_id": str(user.role_id),
            "is_active": user.is_active,
            "email": user.email,
            "login": user.login,
        }

        if payload.email and payload.email != user.email:
            duplicate_email = db.scalar(
                select(User).where(User.email == payload.email, User.id != user.id)
            )
            if duplicate_email:
                raise ConflictError("User with this email already exists")
            user.email = str(payload.email)
        if payload.login and payload.login != user.login:
            duplicate_login = db.scalar(
                select(User).where(User.login == payload.login, User.id != user.id)
            )
            if duplicate_login:
                raise ConflictError("User with this login already exists")
            user.login = payload.login
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.role_id is not None:
            role = UserRepository.get_role_by_id(db, payload.role_id)
            if not role:
                raise NotFoundError("Role not found")
            user.role_id = payload.role_id
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.password:
            user.password_hash = hash_password(payload.password)

        AuditService.log_event(
            db,
            entity_type="user",
            entity_id=str(user.id),
            action="update_user",
            user_id=str(acting_user_id) if acting_user_id else None,
            old_value=old_value,
            new_value={
                "role_id": str(user.role_id),
                "is_active": user.is_active,
                "email": user.email,
                "login": user.login,
            },
        )
        db.commit()
        return UserService.get_user_by_id(db, user.id)

    @staticmethod
    def list_roles(db: Session, params: PageParams) -> tuple[list[Role], dict]:
        return UserRepository.list_roles(db, params)

    @staticmethod
    def _resolve_permissions(db: Session, permission_codes: list[str]) -> list[Permission]:
        permissions: list[Permission] = []
        for code in permission_codes:
            permission = UserRepository.get_permission_by_code(db, code)
            if not permission:
                raise NotFoundError(f"Permission '{code}' not found")
            permissions.append(permission)
        return permissions

    @staticmethod
    def create_role(
        db: Session, payload: RoleCreate, acting_user_id: uuid.UUID | None = None
    ) -> Role:
        existing = UserRepository.get_role_by_code(db, payload.code)
        if existing:
            raise ConflictError("Role with this code already exists")
        role = Role(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            permissions=UserService._resolve_permissions(db, payload.permission_codes),
        )
        db.add(role)
        db.flush()
        AuditService.log_event(
            db,
            entity_type="role",
            entity_id=str(role.id),
            action="create_role",
            user_id=str(acting_user_id) if acting_user_id else None,
            new_value={"code": role.code, "permission_codes": payload.permission_codes},
        )
        db.commit()
        return UserRepository.get_role_by_id(db, role.id) or role

    @staticmethod
    def update_role(
        db: Session,
        role_id: uuid.UUID,
        payload: RoleUpdate,
        acting_user_id: uuid.UUID | None = None,
    ) -> Role:
        role = UserRepository.get_role_by_id(db, role_id)
        if not role:
            raise NotFoundError("Role not found")
        old_value = {
            "name": role.name,
            "description": role.description,
            "permission_codes": [item.code for item in role.permissions],
        }
        if payload.name is not None:
            role.name = payload.name
        if payload.description is not None:
            role.description = payload.description
        if payload.permission_codes is not None:
            role.permissions = UserService._resolve_permissions(db, payload.permission_codes)
        AuditService.log_event(
            db,
            entity_type="role",
            entity_id=str(role.id),
            action="update_role",
            user_id=str(acting_user_id) if acting_user_id else None,
            old_value=old_value,
            new_value={
                "name": role.name,
                "description": role.description,
                "permission_codes": [item.code for item in role.permissions],
            },
        )
        db.commit()
        return UserRepository.get_role_by_id(db, role.id) or role

    @staticmethod
    def list_permissions(db: Session, params: PageParams) -> tuple[list[Permission], dict]:
        return UserRepository.list_permissions(db, params)

    @staticmethod
    def create_permission(
        db: Session,
        payload: PermissionCreate,
        acting_user_id: uuid.UUID | None = None,
    ) -> Permission:
        existing = UserRepository.get_permission_by_code(db, payload.code)
        if existing:
            raise ConflictError("Permission with this code already exists")
        permission = Permission(code=payload.code, name=payload.name)
        db.add(permission)
        db.flush()
        AuditService.log_event(
            db,
            entity_type="permission",
            entity_id=str(permission.id),
            action="create_permission",
            user_id=str(acting_user_id) if acting_user_id else None,
            new_value={"code": permission.code, "name": permission.name},
        )
        db.commit()
        return permission

    @staticmethod
    def update_permission(
        db: Session,
        permission_id: uuid.UUID,
        payload: PermissionUpdate,
        acting_user_id: uuid.UUID | None = None,
    ) -> Permission:
        permission = UserRepository.get_permission_by_id(db, permission_id)
        if not permission:
            raise NotFoundError("Permission not found")
        old_value = {"name": permission.name}
        if payload.name is not None:
            permission.name = payload.name
        AuditService.log_event(
            db,
            entity_type="permission",
            entity_id=str(permission.id),
            action="update_permission",
            user_id=str(acting_user_id) if acting_user_id else None,
            old_value=old_value,
            new_value={"name": permission.name},
        )
        db.commit()
        return permission
