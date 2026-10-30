from __future__ import annotations

from src.bot.max.client import MaxClient
from src.keyboards.max import build_max_attachments
from src.services.platforms import MessengerGateway, OutgoingMessage


class MaxGateway(MessengerGateway):
    def __init__(self, client: MaxClient) -> None:
        self.client = client

    async def send_message(
        self, *, chat_id: str, user_id: str, message: OutgoingMessage
    ) -> None:
        payload: dict[str, object] = {
            "text": message.text,
            "format": "html",
        }
        attachments = build_max_attachments(message.buttons)
        if attachments:
            payload["attachments"] = attachments
        await self.client.send_message(
            user_id=user_id, chat_id=chat_id, payload=payload
        )
