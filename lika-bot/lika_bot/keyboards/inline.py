from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from lika_bot.models.entities import CategoryOverview, UnlockState


def build_main_menu(unlock_state: UnlockState) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Случайный сюрприз 💌", callback_data="menu:random")
    builder.button(text="Видео от близких 🎞", callback_data="menu:categories")
    builder.button(text="Только для Лики 🌷", callback_data="menu:personal")
    builder.button(text="По настроению 💗", callback_data="menu:moods")
    builder.button(text="Ещё одно от меня ✍️", callback_data="menu:ai_message")
    builder.button(text="Сколько ещё ждёт ✨", callback_data="menu:progress")
    builder.button(
        text=(
            "Открыть особенный сюрприз 💫"
            if unlock_state.special_unlocked
            else "Особенный сюрприз пока шепчет 🔒"
        ),
        callback_data="menu:special",
    )
    builder.button(
        text=("Финал дня 🌙" if unlock_state.final_unlocked else "Финал дня пока спит 🔒"),
        callback_data="menu:final",
    )
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def build_categories_menu(categories: list[CategoryOverview]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        label = (
            f"{category.title} • {category.remaining} ждут"
            if category.remaining > 0
            else f"{category.title} • всё уже открыто"
        )
        builder.button(text=label, callback_data=f"category:{category.category}")
    builder.button(text="Вернуться к подарку ↩", callback_data="nav:menu")
    builder.adjust(1)
    return builder.as_markup()


def build_mood_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Нежное 🫶", callback_data="mood:tender")
    builder.button(text="Улыбни меня 🌤", callback_data="mood:playful")
    builder.button(text="Скучаю по тебе 💫", callback_data="mood:miss_you")
    builder.button(text="Поддержи меня 🫂", callback_data="mood:support")
    builder.button(text="Удиви меня ✨", callback_data="mood:surprise")
    builder.button(text="Вернуться к подарку ↩", callback_data="nav:menu")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()
