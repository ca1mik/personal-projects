from __future__ import annotations

import asyncio
import logging
import os

from aiogram.types import Update

from src.config import Settings
from src.services.container import build_container

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("telegram_polling_demo")


async def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    settings = Settings(
        app_env="local",
        telegram_bot_token=token,
        llm_provider="mock",
        max_mock_mode=True,
        yookassa_enable_receipts=False,
        admin_user_ids="",
        admin_api_token="demo-admin-secret",
        database_url="sqlite+aiosqlite:///./telegram_demo.db",
    )
    container = build_container(settings)
    await container.startup()
    bot = container.telegram_runtime.bot
    dispatcher = container.telegram_runtime.dispatcher
    if bot is None:
        raise RuntimeError("Telegram runtime did not initialize bot")

    try:
        me = await bot.get_me()
        logger.info("telegram polling demo started for @%s", me.username)
        await bot.delete_webhook(drop_pending_updates=True)
        offset: int | None = None
        while True:
            updates = await bot.get_updates(
                offset=offset,
                timeout=30,
                allowed_updates=["message", "callback_query", "pre_checkout_query"],
            )
            for update in updates:
                offset = update.update_id + 1
                if isinstance(update, Update):
                    await dispatcher.feed_update(bot, update)
    finally:
        await container.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("telegram polling demo stopped")
