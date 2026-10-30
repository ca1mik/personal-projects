"""additional orders attached to a main one

Заказчик: «доп заказы к этому же нужно создать, чтобы когда выбирали заявку —
можно было создать доп, и в ветке было бы "заказ ** (2 доп заказа)"».

Так работает жизнь заказа: клиент довёз замер, добавил пару фасадов взамен
испорченных, попросил довезти доборы. Это не новый заказ с улицы и не правка
старого — по нему свои деньги и своя отгрузка, но привязан он к основному.

Отдельной таблицы не заводим: доп — это тот же заказ, только со ссылкой на
родителя. Иначе пришлось бы дублировать смету, оплаты, статусы и печать.

Revision ID: 0016_additional_orders
Revises: 0015_article_unique_per_kind
Create Date: 2026-08-21 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_additional_orders"
down_revision = "0015_article_unique_per_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("parent_order_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_orders_parent_order_id",
            "orders",
            ["parent_order_id"],
            ["id"],
        )
    op.create_index("ix_orders_parent_order_id", "orders", ["parent_order_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_parent_order_id", table_name="orders")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint("fk_orders_parent_order_id", type_="foreignkey")
        batch_op.drop_column("parent_order_id")
