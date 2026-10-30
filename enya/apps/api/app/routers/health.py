from __future__ import annotations

from fastapi import APIRouter

from apps.api.app.config import get_settings
from apps.api.app.queue import get_redis_connection


router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, object]:
    settings = get_settings()
    redis_state = "up"
    if settings.queue_mode == "inline":
        redis_state = "skipped"
    else:
        try:
            get_redis_connection().ping()
        except Exception:
            redis_state = "down"
    return {
        "ok": True,
        "data": {
            "status": "ok",
            "queue_mode": settings.queue_mode,
            "redis": redis_state,
        },
    }
