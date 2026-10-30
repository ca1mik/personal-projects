from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP


ZERO = Decimal("0")
HUNDRED = Decimal("100")
DISPLAY_QUANT = Decimal("0.0001")


def to_decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_up_to_interval(moment: datetime, interval_minutes: int) -> datetime:
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be greater than zero")

    base = moment.replace(second=0, microsecond=0)
    midnight = base.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes_since_midnight = base.hour * 60 + base.minute
    next_boundary = ((minutes_since_midnight // interval_minutes) + 1) * interval_minutes
    return midnight + timedelta(minutes=next_boundary)


def compute_change_percent(
    min_price: Decimal | int | float | str,
    max_price: Decimal | int | float | str,
) -> Decimal:
    low = to_decimal(min_price)
    high = to_decimal(max_price)
    if low <= ZERO or high <= ZERO:
        raise ValueError("prices must be greater than zero")
    if high < low:
        raise ValueError("max_price must be greater than or equal to min_price")
    return ((high - low) / high) * HUNDRED


def compute_rollback_levels(
    min_price: Decimal | int | float | str,
    max_price: Decimal | int | float | str,
    rollback_percent: Decimal | int | float | str,
) -> tuple[Decimal, Decimal]:
    low = to_decimal(min_price)
    high = to_decimal(max_price)
    rollback = to_decimal(rollback_percent)

    if low <= ZERO or high <= ZERO:
        raise ValueError("prices must be greater than zero")
    if high < low:
        raise ValueError("max_price must be greater than or equal to min_price")

    price_range = high - low
    rollback_value = price_range * (rollback / HUNDRED)
    return low + rollback_value, high - rollback_value


def crossed_level(
    previous_price: Decimal | int | float | str | None,
    current_price: Decimal | int | float | str | None,
    rollback_min: Decimal | int | float | str | None,
    rollback_max: Decimal | int | float | str | None,
) -> bool:
    if (
        previous_price is None
        or current_price is None
        or rollback_min is None
        or rollback_max is None
    ):
        return False

    previous = to_decimal(previous_price)
    price = to_decimal(current_price)
    low = to_decimal(rollback_min)
    high = to_decimal(rollback_max)
    crossed_from_low = previous < low <= price
    crossed_from_high = previous > high >= price
    return crossed_from_low or crossed_from_high


def format_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(DISPLAY_QUANT, rounding=ROUND_HALF_UP), "f")


def format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%d %H:%M:%S")
