from __future__ import annotations

import logging

from src.config.settings import Settings
from src.services.documents import DocumentService
from src.services.llm.base import LLMMessage, ProviderClient

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(
        self,
        *,
        settings: Settings,
        documents: DocumentService,
        provider: ProviderClient,
    ) -> None:
        self.settings = settings
        self.documents = documents
        self.provider = provider

    async def close(self) -> None:
        await self.provider.close()

    async def generate_reply(
        self, *, summary: str | None, messages: list[LLMMessage]
    ) -> str:
        system_prompt = self.documents.load_prompt("system.md")
        if summary:
            system_prompt += f"\n\nКраткая сводка диалога:\n{summary}"
        try:
            return await self.provider.generate(
                system_prompt=system_prompt, messages=messages, max_tokens=350
            )
        except Exception as exc:  # pragma: no cover - provider/network branch
            logger.exception("llm.generate_reply_failed error=%s", exc)
            return "Сейчас у меня техническая пауза. Попробуй написать ещё раз через минуту, я буду рядом."

    async def summarize(
        self, *, current_summary: str | None, messages: list[LLMMessage]
    ) -> str:
        base = (
            "Сожми диалог в 5-7 коротких предложений. Сохрани факты, повторяющиеся переживания, "
            "главные темы, что уже помогало и открытые вопросы. Не добавляй ничего от себя."
        )
        if current_summary:
            base += f"\n\nПредыдущая сводка:\n{current_summary}"
        try:
            return await self.provider.generate(
                system_prompt=base, messages=messages, max_tokens=220
            )
        except Exception as exc:  # pragma: no cover - provider/network branch
            logger.exception("llm.summarize_failed error=%s", exc)
            return current_summary or ""
