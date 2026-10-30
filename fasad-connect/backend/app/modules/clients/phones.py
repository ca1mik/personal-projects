from __future__ import annotations

from sqlalchemy import ColumnElement, func

from app.modules.clients.models import Client

# Один и тот же номер менеджеры записывают как придётся: «+7 999 123-45-67»,
# «8(999)123-45-67», «79991234567». Пока сравнение шло по строке, каждый новый
# формат записи заводил «нового» клиента и история заказов разъезжалась.
_SEPARATORS = (" ", " ", "-", "(", ")", "+", ".")


def digits_only(value: str | None) -> str:
    """Только цифры номера — то, по чему номер узнаётся вне зависимости от записи."""
    return "".join(symbol for symbol in (value or "") if symbol.isdigit())


def phone_digits_expr() -> ColumnElement[str]:
    """Телефон клиента в базе без разделителей — для сравнения с набранным."""
    expr: ColumnElement[str] = func.coalesce(Client.phone, "")
    for separator in _SEPARATORS:
        expr = func.replace(expr, separator, "")
    return expr


def phone_variants(digits: str) -> list[str]:
    """Российский номер в двух равноправных записях: с «8» и с «7» в начале."""
    if not digits:
        return []
    variants = [digits]
    if len(digits) == 11 and digits[0] in {"7", "8"}:
        variants.append(("8" if digits[0] == "7" else "7") + digits[1:])
    return variants
