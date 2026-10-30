from __future__ import annotations

import logging

from aiogram import Bot

from lika_bot.config.settings import Settings
from lika_bot.models.entities import SyncSummary
from lika_bot.repositories.videos import VideosRepository
from lika_bot.texts.content import NEW_VIDEOS_NOTIFICATION_TEMPLATE
from lika_bot.utils.files import is_media_file
from lika_bot.utils.time import utcnow_iso

logger = logging.getLogger(__name__)


class ContentSyncService:
    """Scans local folders with videos and keeps the database in sync."""

    def __init__(self, settings: Settings, videos_repository: VideosRepository) -> None:
        self._settings = settings
        self._videos_repository = videos_repository

    async def sync(
        self,
        notify_about_new: bool,
        reason: str,
        bot: Bot | None = None,
    ) -> SyncSummary:
        videos_dir = self._settings.videos_dir
        videos_dir.mkdir(parents=True, exist_ok=True)

        seen_paths: set[str] = set()
        scanned_categories: set[str] = set()
        new_videos = 0
        reactivated_videos = 0

        for category_dir in sorted(path for path in videos_dir.iterdir() if path.is_dir()):
            scanned_categories.add(category_dir.name)
            for file_path in sorted(category_dir.rglob("*")):
                if not is_media_file(file_path):
                    continue

                relative_path = file_path.relative_to(self._settings.assets_dir).as_posix()
                title = file_path.stem.replace("_", " ").strip() or file_path.stem
                timestamp = utcnow_iso()
                is_new, is_reactivated = await self._videos_repository.register_video(
                    category=category_dir.name,
                    relative_path=relative_path,
                    title=title,
                    detected_at=timestamp,
                    last_seen_at=timestamp,
                )
                seen_paths.add(relative_path)
                if is_new:
                    new_videos += 1
                if is_reactivated:
                    reactivated_videos += 1

        deactivated_videos = await self._videos_repository.deactivate_missing(seen_paths)
        active_videos = await self._videos_repository.count_active()

        logger.info(
            "Video sync finished. reason=%s new=%s reactivated=%s deactivated=%s active=%s",
            reason,
            new_videos,
            reactivated_videos,
            deactivated_videos,
            active_videos,
        )

        if notify_about_new and new_videos > 0 and bot is not None:
            await bot.send_message(
                chat_id=self._settings.lika_chat_id,
                text=NEW_VIDEOS_NOTIFICATION_TEMPLATE.format(count=new_videos),
            )

        return SyncSummary(
            new_videos=new_videos,
            reactivated_videos=reactivated_videos,
            deactivated_videos=deactivated_videos,
            scanned_categories=sorted(scanned_categories),
            active_videos=active_videos,
        )
