from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import Settings

logger = logging.getLogger(__name__)


class MaxClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.max_base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30)

    def is_configured(self) -> bool:
        return bool(self.settings.max_bot_token or self.settings.max_mock_mode)

    async def close(self) -> None:
        await self.client.aclose()

    async def send_message(
        self,
        *,
        user_id: str | None = None,
        chat_id: str | None = None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if self.settings.max_mock_mode:
            logger.info(
                "max.mock.send_message",
                extra={"chat_id": chat_id, "user_id": user_id, "payload": payload},
            )
            return {"ok": True, "mock": True, "payload": payload}
        if not self.settings.max_bot_token:
            raise RuntimeError("MAX bot token is not configured")
        params: dict[str, str] = {}
        if user_id:
            params["user_id"] = user_id
        if chat_id:
            params["chat_id"] = chat_id
        return await self._post("/messages", params=params, json=payload)

    async def answer_callback(self, *, callback_id: str, text: str) -> None:
        if self.settings.max_mock_mode or not self.settings.max_bot_token:
            return
        await self._post(
            "/answers",
            params={"callback_id": callback_id},
            json={"notification": {"text": text}},
        )

    async def configure_webhook(self) -> None:
        if (
            self.settings.max_mock_mode
            or not self.settings.max_bot_token
            or not self.settings.webhook_base_url
        ):
            return
        payload: dict[str, Any] = {
            "url": f"{self.settings.webhook_base_url.rstrip('/')}/webhooks/max",
            "update_types": ["message_created", "message_callback", "bot_started"],
        }
        if self.settings.max_webhook_secret:
            payload["secret"] = self.settings.max_webhook_secret
        await self._post("/subscriptions", json=payload)

    async def _post(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # TODO: if a specific MAX tenant uses a different auth header or API prefix,
        # adapt it only in this transport layer without touching workflow/business code.
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
            reraise=True,
        ):
            with attempt:
                response = await self.client.post(
                    f"{self.base_url}{path}",
                    params=params,
                    headers={
                        "Authorization": self.settings.max_bot_token,
                        "Content-Type": "application/json",
                    },
                    json=json,
                )
                response.raise_for_status()
                return response.json()
        raise RuntimeError("MAX request failed unexpectedly")
