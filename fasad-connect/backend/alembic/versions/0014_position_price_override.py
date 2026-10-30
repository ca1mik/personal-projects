"""individual price per order position

Заказчик: «цены в нашей таблице нужно сделать корректируемыми, т.е. пусть с базы
подтягиваются, но при этом менеджер может сама корректировать их, не меняя в
самой базе, просто по типу индивидуальных цен под заказ».

До этого произвольную цену принимал только нестандарт: у артикульной строки цена
бралась из справочника и руками не менялась. Теперь менеджер правит её прямо в
смете, но справочник от этого не двигается — правка живёт в строке заказа.

Отдельный признак, а не догадка «цена не совпадает с прайсом»: прайс со временем
меняется, и через полгода по расхождению уже нельзя понять, была ли это скидка
клиенту или просто подорожание. Признак отвечает на вопрос «почему тут другая
цена» в отчёте и в печатной смете.

Revision ID: 0014_position_price_override
Revises: 0013_price_book_and_order_money
Create Date: 2026-08-18 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_position_price_override"
down_revision = "0013_price_book_and_order_money"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table — SQLite в dev не умеет ALTER с NOT NULL напрямую.
    with op.batch_alter_table("order_positions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "price_overridden",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        # Цена из прайса на момент продажи. Нужна, чтобы показать «было 2100,
        # продали за 1900»: сам прайс к тому времени уже другой.
        batch_op.add_column(
            sa.Column("base_price", sa.Numeric(12, 2), nullable=True),
        )


def downgrade() -> None:
    with op.batch_alter_table("order_positions") as batch_op:
        batch_op.drop_column("base_price")
        batch_op.drop_column("price_overridden")
