"""production directions, order numbering by direction, client organization

Соответствует пунктам ТЗ заказчика:
  п. 2 — заявки фиксируются как Эмаль (номер), ПВХ (номер и «П»), Шпон (номер и «Ш»);
  п. 3 — карточка клиента: ФИО, организация, адрес, телефон.

Revision ID: 0007_directions_and_client_org
Revises: 0006_email_channel
Create Date: 2026-08-04 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_directions_and_client_org"
down_revision = "0006_email_channel"
branch_labels = None
depends_on = None


DIRECTIONS = [
    ("enamel", "Эмаль", "", "Фасады с эмалевым покрытием.", 10),
    ("pvc", "ПВХ", "П", "Фасады с плёнкой ПВХ.", 20),
    ("veneer", "Шпон", "Ш", "Шпонированные фасады.", 30),
]


def upgrade() -> None:
    directions = op.create_table(
        "production_directions",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("number_suffix", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_production_directions")),
        sa.UniqueConstraint("code", name=op.f("uq_production_directions_code")),
    )
    op.create_index(
        op.f("ix_production_directions_code"), "production_directions", ["code"], unique=True
    )
    op.create_index(
        op.f("ix_production_directions_is_active"),
        "production_directions",
        ["is_active"],
        unique=False,
    )

    # Три направления из ТЗ создаются миграцией, а не сидом: без них
    # нумерация заказов не работает, а сид на прод-сервере не запускается.
    import uuid
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    op.bulk_insert(
        directions,
        [
            {
                "id": uuid.uuid4(),
                "code": code,
                "name": name,
                "number_suffix": suffix,
                "description": description,
                "sort_order": sort_order,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for code, name, suffix, description, sort_order in DIRECTIONS
        ],
    )

    with op.batch_alter_table("clients") as batch_op:
        batch_op.add_column(sa.Column("organization", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_clients_organization"), "clients", ["organization"], unique=False)

    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("direction_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_orders_direction_id_production_directions"),
            "production_directions",
            ["direction_id"],
            ["id"],
        )
    op.create_index(op.f("ix_orders_direction_id"), "orders", ["direction_id"], unique=False)

    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(sa.Column("direction_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_leads_direction_id_production_directions"),
            "production_directions",
            ["direction_id"],
            ["id"],
        )
    op.create_index(op.f("ix_leads_direction_id"), "leads", ["direction_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_leads_direction_id"), table_name="leads")
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_leads_direction_id_production_directions"), type_="foreignkey"
        )
        batch_op.drop_column("direction_id")

    op.drop_index(op.f("ix_orders_direction_id"), table_name="orders")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_orders_direction_id_production_directions"), type_="foreignkey"
        )
        batch_op.drop_column("direction_id")

    op.drop_index(op.f("ix_clients_organization"), table_name="clients")
    with op.batch_alter_table("clients") as batch_op:
        batch_op.drop_column("organization")

    op.drop_index(op.f("ix_production_directions_is_active"), table_name="production_directions")
    op.drop_index(op.f("ix_production_directions_code"), table_name="production_directions")
    op.drop_table("production_directions")
