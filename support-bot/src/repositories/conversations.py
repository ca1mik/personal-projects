from __future__ import annotations

from sqlalchemy import func, select

from src.models import Conversation, Message, MessageRole
from src.repositories.base import SQLAlchemyRepository


class ConversationRepository(SQLAlchemyRepository):
    async def get_or_create(self, user_id: int) -> Conversation:
        conversation = await self.session.scalar(
            select(Conversation).where(Conversation.user_id == user_id)
        )
        if conversation:
            return conversation

        conversation = Conversation(user_id=user_id)
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def add_message(
        self, conversation_id: int, role: MessageRole | str, content: str
    ) -> Message:
        message = Message(
            conversation_id=conversation_id, role=str(role), content=content
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def get_recent_messages(
        self, conversation_id: int, limit: int = 8
    ) -> list[Message]:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        messages = list(await self.session.scalars(query))
        messages.reverse()
        return messages

    async def count_messages_by_role(
        self, conversation_id: int, role: MessageRole | str
    ) -> int:
        query = select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id,
            Message.role == str(role),
        )
        return int((await self.session.scalar(query)) or 0)

    async def count_messages(self, conversation_id: int) -> int:
        query = select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id
        )
        return int((await self.session.scalar(query)) or 0)

    async def update_summary(
        self, conversation: Conversation, summary: str
    ) -> Conversation:
        conversation.summary = summary
        await self.session.flush()
        return conversation
