from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lika_bot.config.settings import Settings
from lika_bot.db.database import Database
from lika_bot.repositories.progress import ProgressRepository
from lika_bot.repositories.scheduled import ScheduledNotificationsRepository
from lika_bot.repositories.users import UsersRepository
from lika_bot.repositories.videos import VideosRepository
from lika_bot.services.access import AccessService
from lika_bot.services.ai_writer import AIWriterService
from lika_bot.services.content_sync import ContentSyncService
from lika_bot.services.progress import ProgressService
from lika_bot.services.style_profile import StyleProfileService
from lika_bot.services.story import StoryService
from lika_bot.services.video import VideoService

if TYPE_CHECKING:
    from lika_bot.scheduler.manager import SchedulerManager


@dataclass(slots=True)
class Repositories:
    users: UsersRepository
    videos: VideosRepository
    progress: ProgressRepository
    scheduled: ScheduledNotificationsRepository


@dataclass(slots=True)
class Services:
    access: AccessService
    ai_writer: AIWriterService
    content_sync: ContentSyncService
    progress: ProgressService
    style_profile: StyleProfileService
    story: StoryService
    videos: VideoService


@dataclass(slots=True)
class AppContext:
    settings: Settings
    db: Database
    repositories: Repositories
    services: Services
    scheduler: SchedulerManager | None = None

    async def close(self) -> None:
        await self.db.close()


async def create_app_context(settings: Settings) -> AppContext:
    db = Database(settings.db_path)
    await db.connect()
    style_profile_service = StyleProfileService(settings=settings)

    repositories = Repositories(
        users=UsersRepository(db),
        videos=VideosRepository(db),
        progress=ProgressRepository(db),
        scheduled=ScheduledNotificationsRepository(db),
    )
    services = Services(
        access=AccessService(settings),
        ai_writer=AIWriterService(settings=settings, style_profile_service=style_profile_service),
        content_sync=ContentSyncService(settings, repositories.videos),
        progress=ProgressService(
            settings=settings,
            videos_repository=repositories.videos,
            progress_repository=repositories.progress,
            scheduled_repository=repositories.scheduled,
        ),
        style_profile=style_profile_service,
        story=StoryService(
            settings=settings,
            progress_repository=repositories.progress,
        ),
        videos=VideoService(
            settings=settings,
            videos_repository=repositories.videos,
        ),
    )

    return AppContext(
        settings=settings,
        db=db,
        repositories=repositories,
        services=services,
    )
