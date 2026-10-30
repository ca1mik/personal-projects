from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, MenuButtonCommands

from src.bot.telegram.gateway import TelegramGateway
from src.config.settings import Settings
from src.handlers.telegram import create_telegram_router
from src.middlewares import LoggingMiddleware
from src.services.payments import TelegramInvoiceService
from src.services.payments.service import PaymentApplicationService
from src.services.workflow import SupportBotWorkflow

logger = logging.getLogger(__name__)


class TelegramBotRuntime:
    def __init__(
        self,
        *,
        settings: Settings,
        workflow: SupportBotWorkflow,
        payment_service: PaymentApplicationService,
        invoice_service: TelegramInvoiceService,
    ) -> None:
        self.settings = settings
        self.bot = (
            Bot(token=settings.telegram_bot_token)
            if settings.telegram_bot_token
            else None
        )
        self.dispatcher = Dispatcher()
        self.gateway = TelegramGateway(self.bot) if self.bot else None

        if self.bot:
            router = create_telegram_router(
                workflow=workflow,
                gateway=self.gateway,
                payment_service=payment_service,
                invoice_service=invoice_service,
            )
            router.message.middleware(LoggingMiddleware())
            router.callback_query.middleware(LoggingMiddleware())
            self.dispatcher.include_router(router)

    async def configure_webhook(self) -> None:
        if not self.bot or not self.gateway:
            return
        await self._configure_commands()
        if not self.settings.resolved_telegram_webhook_url:
            return
        webhook_url = self.settings.resolved_telegram_webhook_url
        logger.info("telegram.configure_webhook url=%s", webhook_url)
        await self.gateway.configure_webhook(webhook_url)

    async def close(self) -> None:
        if self.gateway:
            await self.gateway.close()

    async def _configure_commands(self) -> None:
        if not self.bot:
            return
        commands = [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="subscription", description="Моя подписка"),
            BotCommand(command="minute", description="Минутка для себя"),
            BotCommand(command="diary", description="Дневник благодарностей"),
        ]
        try:
            await self.bot.set_my_commands(
                commands, scope=BotCommandScopeAllPrivateChats()
            )
            await self.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        except Exception as exc:  # pragma: no cover - network branch
            logger.exception("telegram.configure_commands_failed error=%s", exc)
