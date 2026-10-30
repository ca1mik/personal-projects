"""The agreed order sum is whole roubles; payments and item prices keep kopecks."""
from decimal import Decimal, ROUND_HALF_DOWN, ROUND_HALF_UP


def round_order_amount(value: Decimal | str | float) -> Decimal:
    cents = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return cents.quantize(Decimal("1"), rounding=ROUND_HALF_DOWN).quantize(Decimal("0.01"))
