from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from apps.api.app.config import get_settings


@lru_cache(maxsize=1)
def get_redis_connection() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url)


def get_queue() -> Queue:
    settings = get_settings()
    return Queue(
        settings.queue_name,
        connection=get_redis_connection(),
        default_timeout=settings.worker_job_timeout_seconds,
    )

