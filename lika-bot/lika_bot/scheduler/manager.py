from __future__ import annotations

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from lika_bot.app import AppContext
from lika_bot.utils.time import combine_local_date_and_time, now_in_timezone

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Owns APScheduler jobs for story notifications and folder sync."""

    def __init__(self, context: AppContext, bot: Bot) -> None:
        self._context = context
        self._bot = bot
        self._scheduler = AsyncIOScheduler(timezone=ZoneInfo(context.settings.timezone))

    @property
    def job_count(self) -> int:
        return len(self._scheduler.get_jobs())

    async def start(self) -> None:
        await self.reschedule_all()
        if not self._scheduler.running:
            self._scheduler.start()

    async def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def reschedule_all(self) -> int:
        self._scheduler.remove_all_jobs()
        user_record = await self._context.repositories.users.ensure_system_user(
            self._context.settings.lika_chat_id,
            first_name="Лика",
            is_primary=True,
        )
        await self._context.repositories.progress.ensure_row(user_record.id)

        if self._context.settings.enable_scheduled_messages:
            await self._schedule_story_jobs(user_record.id)

        if self._context.settings.auto_scan_enabled:
            self._scheduler.add_job(
                self._run_auto_sync,
                trigger=IntervalTrigger(minutes=self._context.settings.auto_scan_interval_minutes),
                id="auto-sync",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )

        return len(self._scheduler.get_jobs())

    async def _schedule_story_jobs(self, user_id: int) -> None:
        now_local = now_in_timezone(self._context.settings.timezone)

        for moment in self._context.services.story.story_moments:
            scheduled_for = combine_local_date_and_time(
                self._context.settings.birthday_date + timedelta(days=moment.day_offset),
                moment.send_at,
                self._context.settings.timezone,
            )

            if scheduled_for <= now_local:
                if now_local - scheduled_for > timedelta(minutes=90):
                    continue
                run_at = now_local + timedelta(seconds=5)
            else:
                run_at = scheduled_for

            await self._context.repositories.scheduled.mark_pending(
                user_id=user_id,
                notification_key=moment.key,
                scheduled_for=scheduled_for.isoformat(),
            )
            self._scheduler.add_job(
                self._dispatch_story_message,
                trigger=DateTrigger(run_date=run_at),
                id=f"story:{moment.key}",
                replace_existing=True,
                kwargs={
                    "user_id": user_id,
                    "notification_key": moment.key,
                    "scheduled_for_iso": scheduled_for.isoformat(),
                },
                coalesce=True,
                misfire_grace_time=3600,
            )

    async def _dispatch_story_message(
        self,
        user_id: int,
        notification_key: str,
        scheduled_for_iso: str,
    ) -> None:
        if await self._context.repositories.scheduled.was_sent(user_id, notification_key):
            return

        moment = self._context.services.story.get_story_moment(notification_key)
        try:
            await self._bot.send_message(
                self._context.settings.lika_chat_id,
                moment.text,
            )
            await self._context.repositories.scheduled.mark_sent(
                user_id=user_id,
                notification_key=notification_key,
                scheduled_for=scheduled_for_iso,
            )
        except Exception as error:  # pragma: no cover - depends on Telegram runtime
            logger.exception("Failed to deliver scheduled message %s", notification_key)
            await self._context.repositories.scheduled.mark_failed(
                user_id=user_id,
                notification_key=notification_key,
                scheduled_for=scheduled_for_iso,
                error_text=str(error),
            )

    async def _run_auto_sync(self) -> None:
        try:
            await self._context.services.content_sync.sync(
                notify_about_new=True,
                reason="auto_scan",
                bot=self._bot,
            )
        except Exception:  # pragma: no cover - depends on runtime file/network state
            logger.exception("Automatic content sync failed.")
