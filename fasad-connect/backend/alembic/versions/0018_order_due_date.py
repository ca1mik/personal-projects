"""due date for leads and orders

Заказчик: «надо ещё сделать сроки заказа, типа например мыло типовое 14 дней, так
же с возможностью редактирования при создании заявки, и дальше уже по цепочке эта
дата пойдет со всей инфой этой заявки».

Срок живёт и на заявке, и на заказе. Не только на заказе: клиенту дату называют
уже при расчёте, и она должна доехать до заказа сама, а не вспоминаться заново.
Не только на заявке: заказ живёт дольше — его переносят, и срок правят по заказу,
не трогая заявку.

Дата, а не число дней: «14 дней» от чего считать — от разговора, от оплаты, от
запуска в цех? Менеджер называет клиенту конкретное число, его и храним. Типовой
срок по типу работ — только подстановка при создании, дальше это обычная дата.

Revision ID: 0018_order_due_date
Revises: 0017_russian_permissions
Create Date: 2026-08-21 14:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_order_due_date"
down_revision = "0017_russian_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(sa.Column("due_date", sa.Date(), nullable=True))
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("due_date", sa.Date(), nullable=True))
    # По сроку ищут «что горит на этой неделе» — без индекса это перебор всех
    # заказов на каждом открытии сводки.
    op.create_index("ix_orders_due_date", "orders", ["due_date"])


def downgrade() -> None:
    op.drop_index("ix_orders_due_date", table_name="orders")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("due_date")
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_column("due_date")
