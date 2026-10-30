from __future__ import annotations

from pydantic import BaseModel, Field


class ReferenceValue(BaseModel):
    """Одна подсказка: что писали и сколько раз."""

    value: str
    used: int = 0


class ReferenceValues(BaseModel):
    """Подсказки для полей заявки и заказа."""

    colors: list[ReferenceValue] = Field(default_factory=list)
    millings: list[ReferenceValue] = Field(default_factory=list)
    # Номера артикулов, которые студия набирала руками в заявках и заказах.
    articles: list[ReferenceValue] = Field(default_factory=list)
