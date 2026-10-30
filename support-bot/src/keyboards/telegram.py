from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from src.services.platforms import Button

TELEGRAM_MENU_START = "Попробовать бесплатно"
TELEGRAM_MENU_HOME = "Главное меню"
TELEGRAM_MENU_SUBSCRIPTION = "Моя подписка"
TELEGRAM_MENU_PRICING = "Тарифы"
TELEGRAM_MENU_MINUTE = "Минутка для себя"
TELEGRAM_MENU_DIARY = "Дневник благодарностей"
TELEGRAM_MENU_ABOUT = "Что это"
TELEGRAM_MENU_LEGAL = "Условия и приватность"
TELEGRAM_MENU_SUPPORT = "Поддержка"


def build_telegram_inline_markup(
    buttons: list[list[Button]],
) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None

    rows: list[list[InlineKeyboardButton]] = []
    for row in buttons:
        rendered_row = []
        for button in row:
            if button.kind == "url" and button.url:
                rendered_row.append(
                    InlineKeyboardButton(text=button.text, url=button.url)
                )
            else:
                rendered_row.append(
                    InlineKeyboardButton(
                        text=button.text, callback_data=button.action or "noop"
                    )
                )
        rows.append(rendered_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_telegram_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TELEGRAM_MENU_START)],
            [
                KeyboardButton(text=TELEGRAM_MENU_SUBSCRIPTION),
                KeyboardButton(text=TELEGRAM_MENU_PRICING),
            ],
            [
                KeyboardButton(text=TELEGRAM_MENU_MINUTE),
                KeyboardButton(text=TELEGRAM_MENU_DIARY),
            ],
            [
                KeyboardButton(text=TELEGRAM_MENU_ABOUT),
                KeyboardButton(text=TELEGRAM_MENU_LEGAL),
            ],
            [
                KeyboardButton(text=TELEGRAM_MENU_SUPPORT),
                KeyboardButton(text=TELEGRAM_MENU_HOME),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выбери действие или напиши сообщение",
    )


def resolve_telegram_menu_input(text: str | None) -> tuple[str | None, str | None]:
    mapping = {
        TELEGRAM_MENU_START: ("start:free", None),
        TELEGRAM_MENU_HOME: (None, "/start"),
        TELEGRAM_MENU_SUBSCRIPTION: ("menu:subscription", None),
        TELEGRAM_MENU_PRICING: ("pricing:show", None),
        TELEGRAM_MENU_MINUTE: (None, "/minute"),
        TELEGRAM_MENU_DIARY: (None, "/diary"),
        TELEGRAM_MENU_ABOUT: ("start:about", None),
        TELEGRAM_MENU_LEGAL: ("start:legal", None),
        TELEGRAM_MENU_SUPPORT: ("start:support", None),
    }
    if not text:
        return None, None
    return mapping.get(text.strip(), (None, None))
