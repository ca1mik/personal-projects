from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from src.repositories import DiaryRepository, UserPreferenceRepository, UserRepository
from src.scheduler.celery_app import celery_app
from src.scheduler.runtime import get_scheduler_container
from src.services.llm import LLMMessage
from src.services.platforms import OutgoingMessage
from src.services.utils import utcnow

logger = logging.getLogger(__name__)


@celery_app.task(name="src.scheduler.tasks.renew_subscriptions")
def renew_subscriptions() -> list[int]:
    return asyncio.run(_renew_subscriptions())


@celery_app.task(name="src.scheduler.tasks.send_daily_checkins")
def send_daily_checkins() -> int:
    return asyncio.run(_send_daily_checkins())


@celery_app.task(name="src.scheduler.tasks.send_weekly_diary_summaries")
def send_weekly_diary_summaries() -> int:
    return asyncio.run(_send_weekly_diary_summaries())


async def _renew_subscriptions() -> list[int]:
    container = get_scheduler_container()
    logger.info("celery.renew_subscriptions.started")
    async with container.session_factory() as session:
        user_ids = await container.payments.renew_due_subscriptions(session)
        await session.commit()
    logger.info("celery.renew_subscriptions.completed renewed_count=%s", len(user_ids))
    return user_ids


async def _send_daily_checkins() -> int:
    container = get_scheduler_container()
    if not container.settings.checkin_enabled:
        logger.info("celery.daily_checkins.skipped reason=disabled_by_env")
        return 0

    sent = 0
    async with container.session_factory() as session:
        preferences = await UserPreferenceRepository(
            session
        ).list_daily_checkin_enabled()
        users_repo = UserRepository(session)
        now = utcnow()
        logger.info(
            "celery.daily_checkins.started preferences_count=%s hour=%s",
            len(preferences),
            now.hour,
        )
        for preference in preferences:
            try:
                if not preference.checkin_consent_answered:
                    continue
                target_hour = (
                    preference.checkin_hour_utc
                    if preference.checkin_hour_utc is not None
                    else container.settings.checkin_hour_utc
                )
                if target_hour != now.hour:
                    continue
                today = now.date()
                if (
                    preference.last_checkin_at
                    and preference.last_checkin_at.date() == today
                ):
                    continue
                user = await users_repo.get_by_id(preference.user_id)
                if not user:
                    continue
                await container.notifications.send_to_user(
                    user, OutgoingMessage(text=container.settings.daily_checkin_message)
                )
                preference.last_checkin_at = now
                sent += 1
            except Exception as exc:  # pragma: no cover - defensive branch
                logger.exception(
                    "celery.daily_checkins.user_failed user_id=%s error=%s",
                    preference.user_id,
                    exc,
                )
        await session.commit()
    logger.info("celery.daily_checkins.completed sent=%s", sent)
    return sent


async def _send_weekly_diary_summaries() -> int:
    container = get_scheduler_container()
    sent = 0
    since = utcnow() - timedelta(days=7)
    async with container.session_factory() as session:
        diary_repo = DiaryRepository(session)
        user_repo = UserRepository(session)
        user_ids = await diary_repo.list_user_ids_with_entries_since(since)
        logger.info("celery.weekly_diary.started users=%s", len(user_ids))
        for user_id in user_ids:
            try:
                entries = await diary_repo.get_entries_since(user_id, since)
                if not entries:
                    continue
                user = await user_repo.get_by_id(user_id)
                if not user:
                    continue
                joined_entries = "\n".join(f"- {entry.content}" for entry in entries)
                summary = await container.llm.summarize(
                    current_summary=None,
                    messages=[LLMMessage(role="user", content=joined_entries)],
                )
                await container.notifications.send_to_user(
                    user,
                    OutgoingMessage(
                        text=f"Твоя недельная сводка дневника:\n\n{summary}"
                    ),
                )
                sent += 1
            except Exception as exc:  # pragma: no cover - defensive branch
                logger.exception(
                    "celery.weekly_diary.user_failed user_id=%s error=%s", user_id, exc
                )
        await session.commit()
    logger.info("celery.weekly_diary.completed sent=%s", sent)
    return sent
