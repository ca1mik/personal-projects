"""email channel configuration and outbound delivery state

Revision ID: 0006_email_channel
Revises: 0005_messaging_inbox
Create Date: 2026-08-03 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_email_channel"
down_revision = "0005_messaging_inbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("channel_accounts") as batch_op:
        batch_op.add_column(
            sa.Column("secrets_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch_op.add_column(sa.Column("poll_cursor", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        op.f("ix_channel_accounts_next_poll_at"),
        "channel_accounts",
        ["next_poll_at"],
        unique=False,
    )

    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("delivery_error", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_column("delivery_error")
        batch_op.drop_column("delivered_at")

    op.drop_index(op.f("ix_channel_accounts_next_poll_at"), table_name="channel_accounts")

    with op.batch_alter_table("channel_accounts") as batch_op:
        batch_op.drop_column("last_error_at")
        batch_op.drop_column("last_error")
        batch_op.drop_column("last_success_at")
        batch_op.drop_column("last_polled_at")
        batch_op.drop_column("next_poll_at")
        batch_op.drop_column("poll_cursor")
        batch_op.drop_column("secrets_json")
