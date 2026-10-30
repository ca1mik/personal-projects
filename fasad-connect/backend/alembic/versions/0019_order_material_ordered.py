"""material ordered flag on the order

Заказчик: «когда мы материал заказали на этот конкретный заказ, например плёнку,
мы цветом выделяем — все понимают, что на этот заказ плёнка заказана, больше не
трогаем. Вот тут можно, где статус, сумма, сделать: заказан материал или не
заказан, чтобы мы могли отмечать».

Сейчас это живёт в экселевской таблице заливкой ячейки. Заливку нельзя ни
отфильтровать, ни спросить «что ещё не заказано» — а именно этот вопрос задают
каждый день перед звонком поставщику.

Дата отдельно от галочки: по ней видно, сколько заказ ждёт материал. Снятая
галочка дату стирает — материал «раззаказать» нельзя, это отмена ошибки.

Revision ID: 0019_order_material_ordered
Revises: 0018_order_due_date
Create Date: 2026-08-27 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_order_material_ordered"
down_revision = "0018_order_due_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(
            sa.Column(
                "material_ordered",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("material_ordered_at", sa.DateTime(timezone=True), nullable=True)
        )
    # По этому признаку отбирают «что ещё не заказано» — без индекса это перебор
    # всех заказов на каждом открытии списка.
    op.create_index("ix_orders_material_ordered", "orders", ["material_ordered"])


def downgrade() -> None:
    op.drop_index("ix_orders_material_ordered", table_name="orders")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("material_ordered_at")
        batch_op.drop_column("material_ordered")
