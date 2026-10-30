from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class LLMMessage:
    role: str
    content: str


class ProviderClient(Protocol):
    async def generate(
        self, *, system_prompt: str, messages: list[LLMMessage], max_tokens: int = 350
    ) -> str: ...

    async def close(self) -> None: ...
