from __future__ import annotations

from src.keyboards.telegram import (
    TELEGRAM_MENU_DIARY,
    TELEGRAM_MENU_MINUTE,
    TELEGRAM_MENU_PRICING,
    TELEGRAM_MENU_START,
    TELEGRAM_MENU_SUBSCRIPTION,
    build_telegram_reply_menu,
    resolve_telegram_menu_input,
)


def test_build_telegram_reply_menu_is_persistent() -> None:
    markup = build_telegram_reply_menu()

    assert markup.is_persistent is True
    assert markup.resize_keyboard is True
    assert markup.keyboard[0][0].text == TELEGRAM_MENU_START
    assert markup.keyboard[1][0].text == TELEGRAM_MENU_SUBSCRIPTION
    assert markup.keyboard[1][1].text == TELEGRAM_MENU_PRICING
    assert markup.keyboard[2][0].text == TELEGRAM_MENU_MINUTE
    assert markup.keyboard[2][1].text == TELEGRAM_MENU_DIARY


def test_resolve_telegram_menu_input_maps_menu_buttons() -> None:
    assert resolve_telegram_menu_input(TELEGRAM_MENU_START) == ("start:free", None)
    assert resolve_telegram_menu_input(TELEGRAM_MENU_SUBSCRIPTION) == (
        "menu:subscription",
        None,
    )
    assert resolve_telegram_menu_input(TELEGRAM_MENU_PRICING) == (
        "pricing:show",
        None,
    )
    assert resolve_telegram_menu_input(TELEGRAM_MENU_MINUTE) == (None, "/minute")
    assert resolve_telegram_menu_input(TELEGRAM_MENU_DIARY) == (None, "/diary")
    assert resolve_telegram_menu_input("Свободный текст") == (None, None)
