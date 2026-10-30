import httpx
import logging
from typing import Any, Dict

from src.config.settings import settings

logger = logging.getLogger(__name__)


class TelegramClient:
    """Thin wrapper around Telegram Bot API for sending simple text messages.
    Used as a fallback when MAX integration is disabled.
    """

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        if not self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required for TelegramClient")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.client = httpx.AsyncClient(timeout=10)

    async def send_message(self, chat_id: str | int, text: str, **kwargs: Any) -> Dict[str, Any]:
        payload = {"chat_id": chat_id, "text": text, **kwargs}
        try:
            response = await self.client.post(f"{self.base_url}/sendMessage", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.error("Telegram sendMessage failed: %s", exc)
            raise
