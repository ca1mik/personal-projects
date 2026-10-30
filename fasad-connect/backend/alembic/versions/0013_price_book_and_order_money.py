"""price book, order estimate, payments and order files

Заказчик: «нужна база артикулов, чтобы цена сама подтягивалась… если нет такого,
то прописывается в таблице нестандарт и записывается цена своя», «все
последующие заказы будут с новой стоимостью и старые мы не трогаем никак»,
«по варианту оплаты сделать чекбоксы разные», «разницу балансу… в минусы или
аванс», «добавить подгрузку файлов к самому заказу с комментариями».

Четыре новые таблицы и три колонки к существующим файлам:

* ``price_items`` — справочник артикулов со стоимостью, заполняется вручную;
* ``price_item_changes`` — история цены, чтобы ответить «почему тогда было
  дешевле»;
* ``order_positions`` — строки сметы заказа с **копией** цены на момент
  продажи: справочник дорожает, а старые заказы остаются как были;
* ``order_payments`` — приход денег, из него считается баланс аванс/долг;
* ``documents`` получает тип, размер и комментарий — раньше туда падали только
  выгрузки системы, теперь ещё и файлы от менеджера.

Revision ID: 0013_price_book_and_order_money
Revises: 0012_order_has_texture
Create Date: 2026-08-09 01:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_price_book_and_order_money"
down_revision = "0012_order_has_texture"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False, server_default="other"),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="sqm"),
        sa.Column("price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_items_article", "price_items", ["article"], unique=True)
    op.create_index("ix_price_items_kind", "price_items", ["kind"])
    op.create_index("ix_price_items_is_active", "price_items", ["is_active"])

    op.create_table(
        "price_item_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("price_item_id", sa.Uuid(), nullable=False),
        sa.Column("old_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("new_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["price_item_id"], ["price_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_item_changes_price_item_id",
        "price_item_changes",
        ["price_item_id"],
    )

    op.create_table(
        "order_positions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("price_item_id", sa.Uuid(), nullable=True),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("article", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False, server_default="other"),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="sqm"),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("width", sa.Numeric(10, 2), nullable=True),
        sa.Column("height", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_sqm", sa.Numeric(14, 6), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("thickness", sa.Numeric(10, 2), nullable=True),
        sa.Column("color", sa.String(length=255), nullable=True),
        sa.Column("milling", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["price_item_id"], ["price_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_positions_order_id", "order_positions", ["order_id"])
    op.create_index("ix_order_positions_price_item_id", "order_positions", ["price_item_id"])
    op.create_index("ix_order_positions_kind", "order_positions", ["kind"])

    op.create_table(
        "order_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("method", sa.String(length=30), nullable=False, server_default="cash"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_payments_order_id", "order_payments", ["order_id"])
    op.create_index("ix_order_payments_method", "order_payments", ["method"])

    # batch_alter_table — SQLite в dev не умеет ALTER TABLE напрямую.
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("content_type", sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column("size_bytes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("comment", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("comment")
        batch_op.drop_column("size_bytes")
        batch_op.drop_column("content_type")

    op.drop_index("ix_order_payments_method", table_name="order_payments")
    op.drop_index("ix_order_payments_order_id", table_name="order_payments")
    op.drop_table("order_payments")

    op.drop_index("ix_order_positions_kind", table_name="order_positions")
    op.drop_index("ix_order_positions_price_item_id", table_name="order_positions")
    op.drop_index("ix_order_positions_order_id", table_name="order_positions")
    op.drop_table("order_positions")

    op.drop_index("ix_price_item_changes_price_item_id", table_name="price_item_changes")
    op.drop_table("price_item_changes")

    op.drop_index("ix_price_items_is_active", table_name="price_items")
    op.drop_index("ix_price_items_kind", table_name="price_items")
    op.drop_index("ix_price_items_article", table_name="price_items")
    op.drop_table("price_items")
