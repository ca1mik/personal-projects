from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from lika_bot.app import create_app_context
from lika_bot.config.settings import Settings
from lika_bot.handlers.admin import create_admin_router
from lika_bot.handlers.user import create_user_router
from lika_bot.scheduler.manager import SchedulerManager
from lika_bot.utils.logging import configure_logging


async def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)

    context = await create_app_context(settings)
    session = AiohttpSession(proxy=settings.bot_proxy) if settings.bot_proxy else None
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    scheduler = SchedulerManager(context=context, bot=bot)
    context.scheduler = scheduler

    await context.services.content_sync.sync(notify_about_new=False, reason="startup")

    try:
        await scheduler.start()
    except Exception:  # pragma: no cover - defensive fallback for runtime failures
        logging.getLogger(__name__).exception("Scheduler failed to start, bot will continue without it.")

    dp = Dispatcher()
    dp.include_router(create_admin_router(context))
    dp.include_router(create_user_router(context))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await scheduler.shutdown()
        await context.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
