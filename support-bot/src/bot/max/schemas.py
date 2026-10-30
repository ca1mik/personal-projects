from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MaxUser(BaseModel):
    user_id: int
    name: str | None = None
    username: str | None = None


class MaxMessageBody(BaseModel):
    text: str | None = None


class MaxRecipient(BaseModel):
    chat_id: int | None = None
    user_id: int | None = None


class MaxMessage(BaseModel):
    sender: MaxUser | None = None
    recipient: MaxRecipient | None = None
    body: MaxMessageBody | None = None


class MaxCallback(BaseModel):
    callback_id: str | None = None
    payload: str | None = None


class MaxUpdate(BaseModel):
    update_type: str
    timestamp: int | None = None
    chat_id: int | None = None
    user: MaxUser | None = None
    payload: str | None = None
    message: MaxMessage | None = None
    callback: MaxCallback | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
