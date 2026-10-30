from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.config import get_settings

settings = get_settings()

celery_app = Celery(
    "support_bot", broker=settings.redis_url, backend=settings.redis_url
)
celery_app.conf.timezone = settings.timezone
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.beat_schedule = {
    "renew-subscriptions-hourly": {
        "task": "src.scheduler.tasks.renew_subscriptions",
        "schedule": crontab(minute=5),
    },
    "daily-checkins-hourly": {
        "task": "src.scheduler.tasks.send_daily_checkins",
        "schedule": crontab(minute=0),
    },
    "weekly-diary-summary": {
        "task": "src.scheduler.tasks.send_weekly_diary_summaries",
        "schedule": crontab(
            minute=30, hour=settings.checkin_hour_utc, day_of_week="mon"
        ),
    },
}
celery_app.autodiscover_tasks(["src.scheduler"])
