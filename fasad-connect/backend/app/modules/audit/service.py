from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, pagination_meta
from app.modules.audit.models import AuditLog


def _jsonable(value: Any) -> Any:
    """Значение, которое переживёт запись в JSON-колонку.

    Журнал складывает в JSON то, что ему передали вызывающие: строки статусов,
    суммы, даты, идентификаторы. Дата и Decimal в JSON не сериализуются, и
    первое же поле с датой уронило не запись в журнал, а весь запрос — заказ
    просто не сохранялся. Приводим по месту: журнал не должен ломать работу.
    """
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        user_id: str | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
    ) -> AuditLog:
        normalized_user_id = None
        if isinstance(user_id, uuid.UUID):
            normalized_user_id = user_id
        elif isinstance(user_id, str) and user_id:
            normalized_user_id = uuid.UUID(user_id)
        log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=normalized_user_id,
            old_value_json=_jsonable(old_value),
            new_value_json=_jsonable(new_value),
        )
        db.add(log)
        return log

    @staticmethod
    def list_events(
        db: Session,
        params: PageParams,
        *,
        entity_type: str | None = None,
        action: str | None = None,
    ) -> tuple[list[AuditLog], dict]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        count_stmt = select(func.count()).select_from(AuditLog)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
            count_stmt = count_stmt.where(AuditLog.entity_type == entity_type)
        if action:
            stmt = stmt.where(AuditLog.action == action)
            count_stmt = count_stmt.where(AuditLog.action == action)
        total = db.scalar(count_stmt) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return items, pagination_meta(total, params)
