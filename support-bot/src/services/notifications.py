from __future__ import annotations

import logging

from src.config.settings import Settings
from src.models import Platform, User
from src.services.platforms import MessengerGateway, OutgoingMessage

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        *,
        settings: Settings,
        telegram_gateway: MessengerGateway | None = None,
        max_gateway: MessengerGateway | None = None,
    ) -> None:
        self.settings = settings
        self.telegram_gateway = telegram_gateway
        self.max_gateway = max_gateway

    async def send_to_user(self, user: User, message: OutgoingMessage) -> None:
        gateway = (
            self.telegram_gateway
            if user.platform == Platform.TELEGRAM
            else self.max_gateway
        )
        if gateway is None:
            logger.warning(
                "notification.skipped platform=%s user_id=%s", user.platform, user.id
            )
            return
        try:
            await gateway.send_message(
                chat_id=user.platform_user_id,
                user_id=user.platform_user_id,
                message=message,
            )
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.exception(
                "notification.user_failed platform=%s user_id=%s error=%s",
                user.platform,
                user.id,
                exc,
            )

    async def notify_admins(self, text: str) -> None:
        if not self.telegram_gateway:
            logger.warning("notification.admins_skipped reason=no_gateway")
            return
        if not self.settings.admin_user_ids:
            logger.warning("notification.admins_skipped reason=no_admin_ids")
            return
        for admin_id in self.settings.admin_user_ids:
            try:
                await self.telegram_gateway.send_message(
                    chat_id=str(admin_id),
                    user_id=str(admin_id),
                    message=OutgoingMessage(text=text),
                )
            except Exception as exc:  # pragma: no cover - defensive branch
                logger.exception(
                    "notification.admin_failed admin_id=%s error=%s", admin_id, exc
                )
