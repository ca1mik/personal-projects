from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import Config, GenerationPack, ServiceOffer

CHATGPT_WEB_URL = "https://chatgpt.com/"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎨 Сгенерировать эскиз"), KeyboardButton(text="🖼 Примеры работ")],
            [KeyboardButton(text="🧠 Prompt для ChatGPT"), KeyboardButton(text="🛒 Купить генерации")],
            [KeyboardButton(text="💰 Прайс"), KeyboardButton(text="🔥 Портфолио-акция")],
            [KeyboardButton(text="💳 Оплата и бронь"), KeyboardButton(text="👛 Мой баланс")],
            [KeyboardButton(text="📝 Оставить заявку")],
            [KeyboardButton(text="📞 Связаться с мастером"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )


def booking_contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📲 Отправить номер", request_contact=True)],
            [KeyboardButton(text="Пропустить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def packs_keyboard(packs: tuple[GenerationPack, ...]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for pack in packs:
        builder.button(
            text=f"{pack.title} • {pack.price_xtr} XTR",
            callback_data=f"buy:{pack.code}",
        )
    builder.adjust(1)
    return builder.as_markup()


def service_offers_keyboard(offers: tuple[ServiceOffer, ...]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for offer in offers:
        button_text = (
            f"{offer.title} • по согласованию"
            if offer.code == "portfolio"
            else f"{offer.title} • {offer.amount_rub} ₽"
        )
        builder.button(
            text=button_text,
            callback_data=f"payservice:{offer.code}",
        )
    builder.adjust(1)
    return builder.as_markup()


def payment_link_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить через Robokassa", url=url)],
        ]
    )


def contacts_keyboard(cfg: Config) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Оставить заявку в боте", callback_data="flow:booking")],
            [InlineKeyboardButton(text="VK", url=cfg.vk_url)],
            [InlineKeyboardButton(text="Telegram", url=cfg.telegram_channel_url)],
            [InlineKeyboardButton(text="WhatsApp", url=cfg.whatsapp_url)],
        ]
    )


def chatgpt_entry_keyboard(cfg: Config) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Собрать prompt для ChatGPT", callback_data="mode:chatgpt")],
            [InlineKeyboardButton(text="Открыть ChatGPT", url=CHATGPT_WEB_URL)],
            [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="flow:booking")],
            [InlineKeyboardButton(text="WhatsApp", url=cfg.whatsapp_url)],
        ]
    )


def chatgpt_ready_keyboard(cfg: Config) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть ChatGPT", url=CHATGPT_WEB_URL)],
            [
                InlineKeyboardButton(text="📝 Оставить заявку", callback_data="flow:booking"),
                InlineKeyboardButton(text="WhatsApp", url=cfg.whatsapp_url),
            ],
            [InlineKeyboardButton(text="VK мастера", url=cfg.vk_url)],
        ]
    )


def lead_notify_keyboard(request_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    """Inline-клавиатура для уведомления мастера о новой заявке."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Связались", callback_data=f"lead_status:{request_id}:contacted")
    builder.button(text="🗄 Архив", callback_data=f"lead_status:{request_id}:archive")
    builder.button(text="💰 Предоплата", callback_data=f"lead_status:{request_id}:deposit")
    if user_id:
        builder.button(text="💬 Написать клиенту", url=f"tg://user?id={user_id}")
    builder.adjust(2)
    return builder.as_markup()
