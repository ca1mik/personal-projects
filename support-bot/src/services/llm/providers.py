from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import uuid4

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import Settings
from src.services.llm.base import LLMMessage


class BaseHTTPProvider(ABC):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)

    async def close(self) -> None:
        await self.client.aclose()

    @abstractmethod
    async def generate(
        self, *, system_prompt: str, messages: list[LLMMessage], max_tokens: int = 350
    ) -> str:
        raise NotImplementedError

    async def _post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json_payload: dict[str, Any] | None = None,
        form_payload: dict[str, Any] | None = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        merged_headers = {"Content-Type": content_type, **headers}
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.settings.llm_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
            reraise=True,
        ):
            with attempt:
                response = await self.client.post(
                    url,
                    headers=merged_headers,
                    json=json_payload,
                    data=form_payload,
                )
                response.raise_for_status()
                return response.json()
        raise RuntimeError("LLM request failed unexpectedly")


class MockProvider:
    async def generate(
        self, *, system_prompt: str, messages: list[LLMMessage], max_tokens: int = 350
    ) -> str:
        if "Сожми диалог" in system_prompt:
            return "Краткая сводка разговора сохранена."
        last_user_message = next(
            (
                message.content
                for message in reversed(messages)
                if message.role == "user"
            ),
            "",
        )
        if not last_user_message:
            return (
                "Я рядом. Можешь рассказать чуть подробнее, что сейчас самое тяжёлое?"
            )
        return "Слышу, что тебе сейчас непросто. Что в этом моменте ощущается самым тяжёлым? Если хочешь, можем остаться с этим ещё немного."

    async def close(self) -> None:
        return None


class OpenAIProvider(BaseHTTPProvider):
    async def generate(
        self, *, system_prompt: str, messages: list[LLMMessage], max_tokens: int = 350
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "instructions": system_prompt,
            "input": [asdict(message) for message in messages],
            "store": False,
            "max_output_tokens": max_tokens,
            "text": {"format": {"type": "text"}},
            "reasoning": {"effort": self.settings.llm_openai_reasoning_effort},
        }
        data = await self._post_json(
            self.settings.llm_base_url or "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.settings.resolved_openai_api_key}"
            },
            json_payload=payload,
        )
        return _extract_openai_output_text(data)


class AnthropicProvider(BaseHTTPProvider):
    async def generate(
        self, *, system_prompt: str, messages: list[LLMMessage], max_tokens: int = 350
    ) -> str:
        payload = {
            "model": self.settings.llm_model,
            "system": system_prompt,
            "max_tokens": max_tokens,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in messages
                if msg.role != "system"
            ],
        }
        data = await self._post_json(
            self.settings.llm_base_url or "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.settings.resolved_anthropic_api_key,
                "anthropic-version": self.settings.llm_anthropic_version,
            },
            json_payload=payload,
        )
        content = data.get("content", [])
        return "\n".join(
            item.get("text", "") for item in content if item.get("type") == "text"
        ).strip()


class YandexGPTProvider(BaseHTTPProvider):
    async def generate(
        self, *, system_prompt: str, messages: list[LLMMessage], max_tokens: int = 350
    ) -> str:
        payload = {
            "modelUri": self.settings.llm_model,
            "completionOptions": {
                "stream": False,
                "temperature": 0.7,
                "maxTokens": str(max_tokens),
            },
            "messages": [
                {"role": "system", "text": system_prompt},
                *(
                    {"role": msg.role, "text": msg.content}
                    for msg in messages
                    if msg.content
                ),
            ],
        }
        data = await self._post_json(
            self.settings.llm_yandex_api_url,
            headers={
                "Authorization": f"{self.settings.llm_yandex_auth_scheme} {self.settings.resolved_yandexgpt_api_key}",
                **(
                    {"x-folder-id": self.settings.llm_yandex_folder_id}
                    if self.settings.llm_yandex_folder_id
                    else {}
                ),
            },
            json_payload=payload,
        )
        alternatives = data.get("result", {}).get("alternatives", [])
        if not alternatives:
            raise RuntimeError("YandexGPT returned no alternatives")
        return alternatives[0].get("message", {}).get("text", "").strip()


class GigaChatProvider(BaseHTTPProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    async def generate(
        self, *, system_prompt: str, messages: list[LLMMessage], max_tokens: int = 350
    ) -> str:
        token = await self._get_access_token()
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *(
                    {"role": msg.role, "content": msg.content}
                    for msg in messages
                    if msg.content
                ),
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }
        data = await self._post_json(
            self.settings.llm_gigachat_api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            json_payload=payload,
        )
        return data["choices"][0]["message"]["content"].strip()

    async def _get_access_token(self) -> str:
        if (
            self._access_token
            and self._token_expires_at
            and self._token_expires_at.timestamp() > datetime.utcnow().timestamp() + 60
        ):
            return self._access_token

        data = await self._post_json(
            self.settings.llm_gigachat_auth_url,
            headers={
                "Authorization": f"Basic {self.settings.resolved_gigachat_basic_token}",
                "RqUID": str(uuid4()),
                "Accept": "application/json",
            },
            form_payload={"scope": self.settings.llm_gigachat_scope},
            content_type="application/x-www-form-urlencoded",
        )
        self._access_token = data["access_token"]
        self._token_expires_at = datetime.fromtimestamp(data["expires_at"])
        return self._access_token


def _extract_openai_output_text(payload: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") == "output_text":
                texts.append(part.get("text", ""))
    result = "\n".join(texts).strip()
    if not result:
        raise RuntimeError(f"OpenAI returned empty output: {json.dumps(payload)[:500]}")
    return result
