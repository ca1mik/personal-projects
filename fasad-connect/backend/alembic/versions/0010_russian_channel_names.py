"""Russian display names for channel accounts

Каналы связи остались с английскими названиями («Sales Email», «Website Form»):
миграция 0008 переводила справочники производства и до ``channel_accounts`` не
дошла. Фронт печатает ``channel_account.name`` как есть — на карточке диалога,
в списке каналов и в тексте про отправку письма, поэтому английский пролезал в
интерфейс. Меняется только колонка ``name``; ``code`` остаётся английским, на
нём завязаны привязка входящих сообщений и настройки транспорта.

Revision ID: 0010_russian_channel_names
Revises: 0009_direction_area_factor
Create Date: 2026-08-04 04:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_russian_channel_names"
down_revision = "0009_direction_area_factor"
branch_labels = None
depends_on = None


CHANNEL_ACCOUNTS = {
    "email_sales": ("Почта отдела продаж", "Sales Email"),
    "telegram_main_bot": ("Telegram-бот приёма заявок", "Telegram Bot"),
    "telegram_operator_chat": ("Telegram оператора", "Telegram Direct"),
    "whatsapp_business_main": ("WhatsApp для клиентов", "WhatsApp Business"),
    "website_form_default": ("Форма на сайте", "Website Form"),
    "generic_webhook_default": ("Внешний вебхук", "Generic Webhook"),
    "manual_manager_default": ("Заявка от менеджера", "Manual Manager Input"),
}


def _rename(*, to_russian: bool) -> None:
    connection = op.get_bind()
    for code, (russian, english) in CHANNEL_ACCOUNTS.items():
        connection.execute(
            sa.text("UPDATE channel_accounts SET name = :name WHERE code = :code"),
            {"name": russian if to_russian else english, "code": code},
        )


def upgrade() -> None:
    _rename(to_russian=True)


def downgrade() -> None:
    _rename(to_russian=False)
