from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.pagination import PageParams, pagination_meta
from app.modules.users.models import Permission, Role, User


class UserRepository:
    @staticmethod
    def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .options(joinedload(User.role).joinedload(Role.permissions))
            .where(User.id == user_id)
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    @staticmethod
    def get_by_login(db: Session, login_or_email: str) -> User | None:
        stmt = (
            select(User)
            .options(joinedload(User.role).joinedload(Role.permissions))
            .where(or_(User.login == login_or_email, User.email == login_or_email))
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    @staticmethod
    def list_users(
        db: Session, params: PageParams, search: str | None = None
    ) -> tuple[list[User], dict]:
        stmt = (
            select(User)
            .options(joinedload(User.role).joinedload(Role.permissions))
            .order_by(User.created_at.desc())
        )
        count_stmt = select(func.count()).select_from(User)
        if search:
            pattern = f"%{search.lower()}%"
            criteria = or_(
                func.lower(User.full_name).like(pattern),
                func.lower(User.email).like(pattern),
                func.lower(User.login).like(pattern),
            )
            stmt = stmt.where(criteria)
            count_stmt = count_stmt.where(criteria)
        total = db.scalar(count_stmt) or 0
        users = db.scalars(stmt.offset(params.offset).limit(params.size)).unique().all()
        return users, pagination_meta(total, params)

    @staticmethod
    def list_roles(db: Session, params: PageParams) -> tuple[list[Role], dict]:
        stmt = select(Role).options(joinedload(Role.permissions)).order_by(Role.name.asc())
        total = db.scalar(select(func.count()).select_from(Role)) or 0
        roles = db.scalars(stmt.offset(params.offset).limit(params.size)).unique().all()
        return roles, pagination_meta(total, params)

    @staticmethod
    def list_permissions(db: Session, params: PageParams) -> tuple[list[Permission], dict]:
        stmt = select(Permission).order_by(Permission.code.asc())
        total = db.scalar(select(func.count()).select_from(Permission)) or 0
        permissions = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return permissions, pagination_meta(total, params)

    @staticmethod
    def get_role_by_id(db: Session, role_id: uuid.UUID) -> Role | None:
        stmt = select(Role).options(joinedload(Role.permissions)).where(Role.id == role_id)
        return db.execute(stmt).unique().scalar_one_or_none()

    @staticmethod
    def get_role_by_code(db: Session, code: str) -> Role | None:
        stmt = select(Role).options(joinedload(Role.permissions)).where(Role.code == code)
        return db.execute(stmt).unique().scalar_one_or_none()

    @staticmethod
    def get_permission_by_code(db: Session, code: str) -> Permission | None:
        return db.scalar(select(Permission).where(Permission.code == code))

    @staticmethod
    def get_permission_by_id(db: Session, permission_id: uuid.UUID) -> Permission | None:
        return db.get(Permission, permission_id)
