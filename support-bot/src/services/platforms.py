from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.models import Platform


@dataclass(slots=True)
class Button:
    text: str
    action: str | None = None
    url: str | None = None
    kind: str = "callback"


@dataclass(slots=True)
class OutgoingMessage:
    text: str
    buttons: list[list[Button]] = field(default_factory=list)
    parse_mode: str = "HTML"
    disable_link_preview: bool = True


@dataclass(slots=True)
class IncomingEvent:
    platform: Platform
    platform_user_id: str
    chat_id: str
    username: str | None
    first_name: str | None
    text: str | None = None
    command: str | None = None
    action: str | None = None
    callback_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class MessengerGateway:
    async def send_message(
        self, *, chat_id: str, user_id: str, message: OutgoingMessage
    ) -> None:
        raise NotImplementedError
