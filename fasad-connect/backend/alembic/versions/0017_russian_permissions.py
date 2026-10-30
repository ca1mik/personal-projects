"""Russian names for permissions and roles

Заказчик: «права доступа корректно тоже сделай, чтобы даже тупой собаке понятно
было, по ролям так же ведь? и весь сайт русифицируй».

Экран прав показывал английские названия из первого наполнения — «Manage
leads», «Read audit log». Их читает не программист, а тот, кто раздаёт доступы
сотрудникам, и по такой строке невозможно понять, что человек сможет делать.

Меняются только колонки ``name`` и ``description``. Коды остаются английскими:
на них завязаны проверки прав в коде, и их переименование сломало бы доступ.

Revision ID: 0017_russian_permissions
Revises: 0016_additional_orders
Create Date: 2026-08-21 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_russian_permissions"
down_revision = "0016_additional_orders"
branch_labels = None
depends_on = None


PERMISSIONS = {
    "dashboard.read": ("Смотреть сводку", "View dashboard"),
    "messaging.read": ("Читать диалоги", "View messaging inbox"),
    "messaging.reply": ("Отвечать в диалогах", "Reply in messaging inbox"),
    "channels.manage": ("Настраивать каналы связи", "Manage channel accounts"),
    "production.read": ("Видеть работу цеха", "View production workflow"),
    "production.execute": ("Отчитываться по этапам в цехе", "Execute production stages"),
    "users.manage": ("Заводить сотрудников", "Manage users"),
    "roles.manage": ("Настраивать роли", "Manage roles"),
    "permissions.manage": ("Настраивать права", "Manage permissions"),
    "audit.read": ("Смотреть журнал действий", "Read audit log"),
    "clients.manage": ("Вести клиентов", "Manage clients"),
    "leads.manage": ("Принимать заявки", "Manage leads"),
    "orders.manage": ("Вести заказы и деньги", "Manage orders"),
    "templates.manage": ("Править справочники изделий", "Manage templates"),
    "production.manage": ("Управлять производством", "Manage production"),
    "stock.manage": ("Вести склад", "Manage stock"),
}

ROLES = {
    "admin": (
        ("Администратор", "Полный доступ: сотрудники, права, справочники, деньги, цех."),
        ("Administrator", "Полный доступ ко всем модулям."),
    ),
    "manager": (
        (
            "Менеджер",
            "Принимает заявки, ведёт клиентов, заказы и деньги. Цех только смотрит.",
        ),
        ("Manager", "Работа с клиентами, заявками и заказами."),
    ),
    "technologist": (
        (
            "Технолог",
            "Готовит производство: раскрой, справочники изделий, склад, этапы в цехе.",
        ),
        ("Technologist", "Подготовка производства и работа со складом."),
    ),
    "operator": (
        ("Работник цеха", "Отчитывается по своим этапам. Денег и клиентов не видит."),
        ("Operator", "Worker execution role."),
    ),
}


def _apply(*, to_russian: bool) -> None:
    connection = op.get_bind()
    for code, (russian, english) in PERMISSIONS.items():
        connection.execute(
            sa.text("UPDATE permissions SET name = :name WHERE code = :code"),
            {"name": russian if to_russian else english, "code": code},
        )
    for code, (russian, english) in ROLES.items():
        name, description = russian if to_russian else english
        connection.execute(
            sa.text("UPDATE roles SET name = :name, description = :description WHERE code = :code"),
            {"name": name, "description": description, "code": code},
        )


def upgrade() -> None:
    _apply(to_russian=True)


def downgrade() -> None:
    _apply(to_russian=False)
