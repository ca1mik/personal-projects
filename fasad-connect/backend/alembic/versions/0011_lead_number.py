"""Lead number

У заявки был только UUID: менеджер не мог назвать её клиенту по телефону, а после
создания заявки на экране не появлялось ничего, за что можно зацепиться. Добавляем
человеческий номер вида «З-0001» — своя сквозная нумерация, отдельная от заказов,
чтобы «0012» (заказ) и «З-0012» (заявка) нельзя было спутать.

Существующие заявки нумеруются по дате создания, чтобы старые записи тоже
открывались по номеру.

Revision ID: 0011_lead_number
Revises: 0010_russian_channel_names
Create Date: 2026-08-04 11:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_lead_number"
down_revision = "0010_russian_channel_names"
branch_labels = None
depends_on = None

LEAD_NUMBER_PREFIX = "З-"


def upgrade() -> None:
    op.add_column("leads", sa.Column("lead_number", sa.String(length=20), nullable=True))
    op.create_index("ix_leads_lead_number", "leads", ["lead_number"], unique=True)

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id FROM leads ORDER BY created_at ASC, id ASC")
    ).fetchall()
    for sequence, (lead_id,) in enumerate(rows, start=1):
        connection.execute(
            sa.text("UPDATE leads SET lead_number = :number WHERE id = :id"),
            {"number": f"{LEAD_NUMBER_PREFIX}{sequence:04d}", "id": lead_id},
        )


def downgrade() -> None:
    op.drop_index("ix_leads_lead_number", table_name="leads")
    op.drop_column("leads", "lead_number")
