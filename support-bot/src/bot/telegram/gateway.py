from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from src.keyboards.telegram import (
    build_telegram_inline_markup,
    build_telegram_reply_menu,
)
from src.services.platforms import MessengerGateway, OutgoingMessage

logger = logging.getLogger(__name__)


class TelegramGateway(MessengerGateway):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send_message(
        self, *, chat_id: str, user_id: str, message: OutgoingMessage
    ) -> None:
        reply_markup = (
            build_telegram_inline_markup(message.buttons)
            if message.buttons
            else build_telegram_reply_menu()
        )
        try:
            await self.bot.send_message(
                chat_id=int(chat_id),
                text=message.text,
                parse_mode=message.parse_mode,
                disable_web_page_preview=message.disable_link_preview,
                reply_markup=reply_markup,
            )
        except TelegramRetryAfter as exc:  # pragma: no cover - network branch
            logger.warning(
                "telegram.retry_after chat_id=%s retry_after=%s",
                chat_id,
                exc.retry_after,
            )
            await asyncio.sleep(exc.retry_after)
            await self.bot.send_message(
                chat_id=int(chat_id),
                text=message.text,
                parse_mode=message.parse_mode,
                disable_web_page_preview=message.disable_link_preview,
                reply_markup=reply_markup,
            )
        except TelegramAPIError as exc:  # pragma: no cover - network branch
            logger.exception(
                "telegram.send_message_failed chat_id=%s error=%s", chat_id, exc
            )

    async def configure_webhook(self, webhook_url: str) -> None:
        try:
            await self.bot.set_webhook(
                url=webhook_url,
                allowed_updates=["message", "callback_query", "pre_checkout_query"],
            )
        except TelegramAPIError as exc:  # pragma: no cover - network branch
            logger.exception(
                "telegram.configure_webhook_failed url=%s error=%s", webhook_url, exc
            )

    async def close(self) -> None:
        await self.bot.session.close()
