from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class StartMonitoringRequest(BaseModel):
    tickers: list[str]
    change_percent: Decimal = Field(gt=Decimal("0"))
    window_minutes: int = Field(ge=1, le=1440)
    rollback_percent: Decimal = Field(gt=Decimal("0"), le=Decimal("50"))

    @field_validator("tickers", mode="before")
    @classmethod
    def normalize_tickers(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, str):
            raw_items = value.replace("\n", ",").split(",")
        else:
            raw_items = value

        tickers = [str(item).strip().upper() for item in raw_items if str(item).strip()]
        unique = list(dict.fromkeys(tickers))
        if not unique:
            raise ValueError("Укажите хотя бы один тикер")
        return unique
