import httpx
import json
import logging
from typing import Any, Dict, Optional

from src.config.settings import settings
from src.services.telegram_client import TelegramClient

logger = logging.getLogger(__name__)


class MaxClient:
    """Client for Yandex Alice (MAX) integration.

    When `settings.max_mock_mode` is **False** we try to send to the configured
    MAX webhook. If the webhook URL is not set (or the request fails), we fall
    back to sending the message via the Telegram bot, using the same ``user_id``
    as the Telegram ``chat_id``.
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.max_webhook_url
        self.is_mock = getattr(settings, "max_mock_mode", False)
        self.telegram = TelegramClient()  # always available for fallback
        if not self.webhook_url:
            logger.warning("MAX webhook URL is not configured – will use Telegram fallback.")
            self.is_mock = False  # treat as real mode but without MAX endpoint

    async def send_message(self, user_id: str, message: str, **extra: Any) -> Dict[str, Any]:
        payload = {"user_id": user_id, "message": message, **extra}
        if self.is_mock:
            logger.debug("[MAX MOCK] payload: %s", json.dumps(payload, ensure_ascii=False))
            return {"status": "ok", "mock": True, "payload": payload}
        # Try MAX endpoint first
        if self.webhook_url:
            async with httpx.AsyncClient(timeout=10) as client:
                try:
                    response = await client.post(self.webhook_url, json=payload)
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPError as exc:
                    logger.error("MAX request failed, falling back to Telegram: %s", exc)
        # Fallback to Telegram
        return await self.telegram.send_message(chat_id=user_id, text=message)

    # Helper for quick text‑only messages
    async def text(self, user_id: str, text: str) -> Dict[str, Any]:
        return await self.send_message(user_id, text)
