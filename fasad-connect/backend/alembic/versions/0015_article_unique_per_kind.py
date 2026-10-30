"""article numbers are unique inside a type, not globally

Заказчик: «пусть вводят номенклатуры сами... на пленку, эмаль тд тп, пусть они
выбирают при заявке выбор этих типов и дальше, уже занося в заказ — она попадала
бы в базу, именно той части, которую выбрали». И отдельно: «артикулы оставь
только цифры, по типу "арт. 112"».

Из этого следует, что номер артикула сам по себе больше не уникален. В каталоге
студии артикул 127 существует и в плёнке, и в эмали — это один рисунок фасада в
двух покрытиях, и цена у них разная (первая группа против третьей). При
уникальности по одному номеру пришлось бы либо клеить к номеру буквы, чего
заказчик просил не делать, либо держать одну цену на два разных товара.

Поэтому уникальна пара «тип + номер»: 112 в эмали и 112 в плёнке — разные
позиции справочника, каждая со своей ценой.

Revision ID: 0015_article_unique_per_kind
Revises: 0014_position_price_override
Create Date: 2026-08-18 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_article_unique_per_kind"
down_revision = "0014_position_price_override"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_price_items_article", table_name="price_items")
    # Поиск по номеру остаётся: он идёт подстрокой («3» находит «331»),
    # и без индекса на артикуле список пришлось бы перебирать целиком.
    op.create_index("ix_price_items_article", "price_items", ["article"])
    op.create_index(
        "uq_price_items_kind_article",
        "price_items",
        ["kind", "article"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_price_items_kind_article", table_name="price_items")
    op.drop_index("ix_price_items_article", table_name="price_items")
    op.create_index("ix_price_items_article", "price_items", ["article"], unique=True)
