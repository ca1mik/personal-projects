from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class PricingResult(BaseModel):
    total_amount: Decimal
    final_amount: Decimal
    currency: str
