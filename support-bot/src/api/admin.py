from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from src.api.dependencies import get_container
from src.repositories import (
    AuditEventRepository,
    CrisisRepository,
    DeletionRequestRepository,
)
from src.services.container import AppContainer

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin_token(container: AppContainer, token: str | None) -> None:
    expected_token = container.settings.effective_admin_api_token
    if not expected_token or token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _safe_payload(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


@router.get("/audit-events")
async def audit_events(
    container: AppContainer = Depends(get_container),
    x_admin_token: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    category: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
) -> dict[str, Any]:
    _require_admin_token(container, x_admin_secret or x_admin_token)
    async with container.session_factory() as session:
        events = await AuditEventRepository(session).list_recent(
            limit=limit, category=category, user_id=user_id
        )
    return {
        "items": [
            {
                "id": item.id,
                "user_id": item.user_id,
                "category": item.category,
                "action": item.action,
                "payload": _safe_payload(item.payload),
                "created_at": item.created_at.isoformat(),
            }
            for item in events
        ]
    }


@router.get("/crisis-incidents")
async def crisis_incidents(
    container: AppContainer = Depends(get_container),
    x_admin_token: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    _require_admin_token(container, x_admin_secret or x_admin_token)
    async with container.session_factory() as session:
        incidents = await CrisisRepository(session).list_recent(limit=limit)
    return {
        "items": [
            {
                "id": item.id,
                "user_id": item.user_id,
                "message": item.message,
                "detected_reason": item.detected_reason,
                "created_at": item.created_at.isoformat(),
                "notified_admins_at": (
                    item.notified_admins_at.isoformat()
                    if item.notified_admins_at
                    else None
                ),
            }
            for item in incidents
        ]
    }


@router.get("/deletion-requests")
async def deletion_requests(
    container: AppContainer = Depends(get_container),
    x_admin_token: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    _require_admin_token(container, x_admin_secret or x_admin_token)
    async with container.session_factory() as session:
        requests = await DeletionRequestRepository(session).list_recent(limit=limit)
    return {
        "items": [
            {
                "id": item.id,
                "user_id": item.user_id,
                "status": item.status,
                "note": item.note,
                "created_at": item.created_at.isoformat(),
                "processed_at": (
                    item.processed_at.isoformat() if item.processed_at else None
                ),
            }
            for item in requests
        ]
    }
