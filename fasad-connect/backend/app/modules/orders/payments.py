from __future__ import annotations

# Способы оплаты, которыми студия реально пользуется. Список отдаётся фронту и
# рисуется чекбоксами: заказчик просил «по варианту оплаты сделать чекбоксы
# разные». Код английский, подпись русская.
PAYMENT_METHODS: dict[str, str] = {
    "deposit": "С депозита клиента",
    "cash": "Наличные",
    "card": "Карта",
    "transfer": "Перевод на карту",
    "account": "Расчётный счёт",
    "other": "Другое",
}


def payment_method_label(code: str) -> str:
    return PAYMENT_METHODS.get(code, code)
