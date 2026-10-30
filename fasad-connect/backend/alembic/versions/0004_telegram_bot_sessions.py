"""telegram bot sessions

Revision ID: 0004_telegram_bot_sessions
Revises: 0003_stage_part_reports
Create Date: 2026-04-02 15:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_telegram_bot_sessions"
down_revision = "0003_stage_part_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_bot_sessions",
        sa.Column("chat_id", sa.String(length=100), nullable=False),
        sa.Column("telegram_user_id", sa.String(length=100), nullable=True),
        sa.Column("current_step", sa.String(length=50), nullable=False),
        sa.Column("selected_product_code", sa.String(length=100), nullable=True),
        sa.Column("collected_data_json", sa.JSON(), nullable=False),
        sa.Column("last_message_id", sa.String(length=100), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_bot_sessions")),
        sa.UniqueConstraint("chat_id", name=op.f("uq_telegram_bot_sessions_chat_id")),
    )
    op.create_index(
        op.f("ix_telegram_bot_sessions_chat_id"),
        "telegram_bot_sessions",
        ["chat_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_telegram_bot_sessions_telegram_user_id"),
        "telegram_bot_sessions",
        ["telegram_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_telegram_bot_sessions_telegram_user_id"), table_name="telegram_bot_sessions")
    op.drop_index(op.f("ix_telegram_bot_sessions_chat_id"), table_name="telegram_bot_sessions")
    op.drop_table("telegram_bot_sessions")
