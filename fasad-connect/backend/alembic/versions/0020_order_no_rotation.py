"""no-rotation flag on the order

Заказчик: «сделай сразу в самом заказе „нельзя поворачивать"».

Признак «материал с текстурой» это уже делал побочно, но текстура — не
единственная причина. Бывает направление шлифовки, рисунок фрезы, просто
требование клиента класть все фасады в одну сторону. Отмечать это текстурой
значило бы врать в данных: в отчётах и на карте раскроя текстура означает
текстуру.

Поэтому отдельный флаг. Раскрой не вращает деталь, если стоит любой из двух.

Revision ID: 0020_order_no_rotation
Revises: 0019_order_material_ordered
Create Date: 2026-08-27 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0020_order_no_rotation"
down_revision = "0019_order_material_ordered"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(
            sa.Column(
                "no_rotation",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("no_rotation")
