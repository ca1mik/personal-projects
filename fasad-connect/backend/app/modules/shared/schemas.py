from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Envelope[T](BaseModel):
    data: T
    meta: dict[str, Any] | None = None


class MessageEnvelope(BaseModel):
    data: dict[str, str]


class ConfirmPermanentDeletion(BaseModel):
    confirm: Literal[True]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
