from __future__ import annotations

from pathlib import Path

from lika_bot.config.settings import Settings
from lika_bot.models.entities import CategoryOverview, VideoSelection
from lika_bot.repositories.videos import VideosRepository
from lika_bot.texts.content import pretty_category_title


class VideoService:
    """Selects non-repeating videos for the current user."""

    def __init__(self, settings: Settings, videos_repository: VideosRepository) -> None:
        self._settings = settings
        self._videos_repository = videos_repository

    async def select_random_video(self, user_id: int) -> VideoSelection:
        return await self._select_from_scope(user_id, category=None, excluded_categories=("special", "final"))

    async def select_category_video(self, user_id: int, category: str) -> VideoSelection:
        return await self._select_from_scope(user_id, category=category)

    async def select_special_video(self, user_id: int) -> VideoSelection:
        return await self._select_from_scope(user_id, category="special")

    async def select_final_video(self, user_id: int) -> VideoSelection:
        return await self._select_from_scope(user_id, category="final")

    async def list_video_categories(self, user_id: int) -> list[CategoryOverview]:
        raw_categories = await self._videos_repository.list_categories_with_counts(
            user_id,
            excluded_categories=("random", "special", "final"),
        )
        return [
            CategoryOverview(
                category=item.category,
                title=pretty_category_title(item.category),
                total=item.total,
                remaining=item.remaining,
            )
            for item in raw_categories
        ]

    def absolute_path(self, relative_path: str) -> Path:
        return (self._settings.assets_dir / relative_path).resolve()

    async def _select_from_scope(
        self,
        user_id: int,
        category: str | None,
        excluded_categories: tuple[str, ...] = (),
    ) -> VideoSelection:
        total = await self._videos_repository.count_active(
            category=category,
            excluded_categories=excluded_categories,
        )
        if total == 0:
            return VideoSelection(
                status="empty",
                video=None,
                total_in_scope=0,
                remaining_after_send=0,
                requested_category=category,
            )

        remaining_before_send = await self._videos_repository.count_remaining_for_user(
            user_id=user_id,
            category=category,
            excluded_categories=excluded_categories,
        )
        if remaining_before_send == 0:
            return VideoSelection(
                status="exhausted",
                video=None,
                total_in_scope=total,
                remaining_after_send=0,
                requested_category=category,
            )

        video = await self._videos_repository.get_random_unsent_for_user(
            user_id=user_id,
            category=category,
            excluded_categories=excluded_categories,
        )
        return VideoSelection(
            status="ready",
            video=video,
            total_in_scope=total,
            remaining_after_send=max(remaining_before_send - 1, 0),
            requested_category=category,
        )
