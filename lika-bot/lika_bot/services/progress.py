from __future__ import annotations

from lika_bot.config.settings import Settings
from lika_bot.models.entities import ProgressSnapshot, UnlockState
from lika_bot.repositories.progress import ProgressRepository
from lika_bot.repositories.scheduled import ScheduledNotificationsRepository
from lika_bot.repositories.videos import VideosRepository
from lika_bot.utils.time import combine_local_date_and_time, now_in_timezone


class ProgressService:
    """Aggregates user progress and unlock state."""

    def __init__(
        self,
        settings: Settings,
        videos_repository: VideosRepository,
        progress_repository: ProgressRepository,
        scheduled_repository: ScheduledNotificationsRepository,
    ) -> None:
        self._settings = settings
        self._videos_repository = videos_repository
        self._progress_repository = progress_repository
        self._scheduled_repository = scheduled_repository

    async def get_snapshot(self, user_id: int) -> ProgressSnapshot:
        state = await self._progress_repository.get_state(user_id)
        videos_watched = await self._videos_repository.count_sent(
            user_id,
            excluded_categories=("special", "final"),
        )
        personal_messages_opened = await self._progress_repository.count_unique_personal_messages(user_id)
        scheduled_messages_sent = await self._scheduled_repository.count_sent(user_id)
        special_opened = bool(state["special_opened_at"])
        final_opened = bool(state["final_opened_at"])

        total_opened = min(
            self._settings.total_surprises,
            videos_watched
            + personal_messages_opened
            + int(special_opened)
            + int(final_opened),
        )
        remaining_surprises = max(self._settings.total_surprises - total_opened, 0)

        return ProgressSnapshot(
            videos_watched=videos_watched,
            personal_messages_opened=personal_messages_opened,
            scheduled_messages_sent=scheduled_messages_sent,
            total_opened=total_opened,
            remaining_surprises=remaining_surprises,
            special_opened=special_opened,
            final_opened=final_opened,
        )

    def get_unlock_state(self, snapshot: ProgressSnapshot) -> UnlockState:
        rules = self._settings.unlock_rules
        now_local = now_in_timezone(self._settings.timezone)
        birthday_started = now_local.date() >= self._settings.birthday_date

        special_videos_left = max(rules.special_unlock_video_count - snapshot.videos_watched, 0)
        special_unlocked = snapshot.special_opened or (
            birthday_started and snapshot.videos_watched >= rules.special_unlock_video_count
        )

        final_unlock_at = combine_local_date_and_time(
            self._settings.birthday_date,
            rules.final_unlock_time,
            self._settings.timezone,
        )
        final_time_reached = birthday_started and now_local >= final_unlock_at
        final_videos_left = max(rules.final_unlock_video_count - snapshot.videos_watched, 0)
        final_total_left = max(rules.final_unlock_total_opened - snapshot.total_opened, 0)
        final_unlocked = snapshot.final_opened or (
            birthday_started
            and (
                final_time_reached
                or snapshot.videos_watched >= rules.final_unlock_video_count
                or snapshot.total_opened >= rules.final_unlock_total_opened
            )
        )

        return UnlockState(
            birthday_started=birthday_started,
            special_unlocked=special_unlocked,
            special_videos_left=special_videos_left,
            final_unlocked=final_unlocked,
            final_videos_left=final_videos_left,
            final_total_left=final_total_left,
            final_unlock_at_label=rules.final_unlock_time,
        )
