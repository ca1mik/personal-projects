from __future__ import annotations

import logging

from src.bot.max.schemas import MaxUpdate
from src.models import Platform
from src.services.platforms import IncomingEvent
from src.services.workflow import SupportBotWorkflow

logger = logging.getLogger(__name__)


class MaxWebhookHandler:
    def __init__(self, *, workflow: SupportBotWorkflow, gateway, client) -> None:
        self.workflow = workflow
        self.gateway = gateway
        self.client = client

    async def handle(self, update: MaxUpdate) -> None:
        event = self._normalize(update)
        logger.info(
            "max.incoming_event update_type=%s chat_id=%s user_id=%s command=%s action=%s",
            update.update_type,
            event.chat_id,
            event.platform_user_id,
            event.command,
            event.action,
        )
        result = await self.workflow.handle_event(event)
        for message in result.messages:
            await self.gateway.send_message(
                chat_id=event.chat_id, user_id=event.platform_user_id, message=message
            )
        if event.callback_id:
            await self.client.answer_callback(
                callback_id=event.callback_id, text="Принято"
            )

    def _normalize(self, update: MaxUpdate) -> IncomingEvent:
        if update.update_type == "message_callback":
            callback = update.callback
            actor = update.user or (update.message.sender if update.message else None)
            if actor is None:
                raise ValueError("MAX callback update does not contain actor")
            return IncomingEvent(
                platform=Platform.MAX,
                platform_user_id=str(actor.user_id),
                chat_id=str(
                    update.chat_id
                    or (
                        update.message.recipient.chat_id
                        if update.message and update.message.recipient
                        else actor.user_id
                    )
                ),
                username=actor.username,
                first_name=actor.name,
                action=callback.payload if callback else None,
                callback_id=callback.callback_id if callback else None,
            )

        if update.update_type == "bot_started":
            user = update.user
            if user is None:
                raise ValueError("MAX bot_started update does not contain user")
            return IncomingEvent(
                platform=Platform.MAX,
                platform_user_id=str(user.user_id),
                chat_id=str(update.chat_id or user.user_id),
                username=user.username,
                first_name=user.name,
                action="start:free" if update.payload else None,
                command="/start",
                text="/start",
            )

        message = update.message
        sender = message.sender if message else update.user
        if sender is None:
            raise ValueError("MAX message update does not contain sender")
        text = message.body.text if message and message.body else None
        command = text.split(maxsplit=1)[0] if text and text.startswith("/") else None
        return IncomingEvent(
            platform=Platform.MAX,
            platform_user_id=str(sender.user_id),
            chat_id=str(
                update.chat_id
                or (
                    message.recipient.chat_id
                    if message and message.recipient
                    else sender.user_id
                )
            ),
            username=sender.username,
            first_name=sender.name,
            text=text,
            command=command,
        )
