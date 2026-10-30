"""material area factor per production direction

Отчёты ТЗ (пп. 5, 6) требуют объёмы в квадратных метрах. Площадь фасада и
площадь материала — разные числа: ПВХ клеится с двух сторон, значит плёнки
нужно вдвое больше, чем площадь самого фасада. Без коэффициента отчёт «в м²»
расходится с реальным расходом.

Revision ID: 0009_direction_area_factor
Revises: 0008_russian_display_names
Create Date: 2026-08-04 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_direction_area_factor"
down_revision = "0008_russian_display_names"
branch_labels = None
depends_on = None


# Значения по умолчанию. Точные коэффициенты заказчик уточняет на обследовании
# (этап 0) — здесь заложена типовая практика.
FACTORS = {
    "enamel": "1.000",  # эмаль наносится на лицевую сторону
    "pvc": "2.000",  # плёнка ПВХ — обе стороны
    "veneer": "1.000",  # шпон — лицевая сторона
}


def upgrade() -> None:
    with op.batch_alter_table("production_directions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "material_area_factor",
                sa.Numeric(precision=6, scale=3),
                nullable=False,
                server_default="1.000",
            )
        )

    connection = op.get_bind()
    for code, factor in FACTORS.items():
        connection.execute(
            sa.text(
                "UPDATE production_directions SET material_area_factor = :factor WHERE code = :code"
            ),
            {"factor": factor, "code": code},
        )


def downgrade() -> None:
    with op.batch_alter_table("production_directions") as batch_op:
        batch_op.drop_column("material_area_factor")
