"""order texture flag

Заказчик: «галка что текстуры нет например, а есть текстурные плёнки, там надо
крутить». У текстурного материала деталь нельзя разворачивать на 90° при
раскрое — рисунок пойдёт поперёк фасада. У нетекстурного разворот разрешён и
экономит лист, поэтому умолчание — «текстуры нет».

Признак живёт на заказе, а не на детали: студия набирает заказ одним
материалом, и переключать это на каждой позиции менеджеру некогда.

Revision ID: 0012_order_has_texture
Revises: 0011_lead_number
Create Date: 2026-08-06 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_order_has_texture"
down_revision = "0011_lead_number"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table — SQLite в dev не умеет ALTER с NOT NULL напрямую.
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(
            sa.Column(
                "has_texture",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("has_texture")
