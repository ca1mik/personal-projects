"""initial schema

Revision ID: 20260609_0001
Revises:
Create Date: 2026-06-09 12:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260609_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("platform_user_id", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "is_adult_confirmed", sa.Boolean(), server_default="0", nullable=False
        ),
        sa.Column(
            "free_preview_messages_used",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "preview_exhausted", sa.Boolean(), server_default="0", nullable=False
        ),
        sa.Column("preview_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "platform", "platform_user_id", name="uq_users_platform_platform_user_id"
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_table(
        "consents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("privacy_accepted", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("offer_accepted", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "disclaimer_accepted", sa.Boolean(), server_default="0", nullable=False
        ),
        sa.Column("marketing_opt_in", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("privacy_version", sa.String(length=64), nullable=True),
        sa.Column("offer_version", sa.String(length=64), nullable=True),
        sa.Column("disclaimer_version", sa.String(length=64), nullable=True),
        sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offer_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disclaimer_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("marketing_opt_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("payment_method_id", sa.String(length=255), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_subscriptions_user_status",
        "subscriptions",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_subscriptions_expires_at", "subscriptions", ["expires_at"], unique=False
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("plan", sa.String(length=32), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "currency", sa.String(length=8), server_default="RUB", nullable=False
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("payment_method_id", sa.String(length=255), nullable=True),
        sa.Column("idempotence_key", sa.String(length=128), nullable=True),
        sa.Column("confirmation_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("is_recurrent", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotence_key", name="uq_payments_idempotence_key"),
    )
    op.create_index(
        "ix_payments_provider_payment_id",
        "payments",
        ["provider_payment_id"],
        unique=False,
    )
    op.create_index(
        "ix_payments_user_created_at",
        "payments",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_messages_conversation_created_at",
        "messages",
        ["conversation_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "crisis_incidents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detected_reason", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("notified_admins_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_crisis_incidents_created_at",
        "crisis_incidents",
        ["created_at"],
        unique=False,
    )
    op.create_table(
        "deletion_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_deletion_requests_status", "deletion_requests", ["status"], unique=False
    )
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "daily_checkin_enabled", sa.Boolean(), server_default="0", nullable=False
        ),
        sa.Column(
            "checkin_consent_answered", sa.Boolean(), server_default="0", nullable=False
        ),
        sa.Column("pending_action", sa.String(length=64), nullable=True),
        sa.Column("pending_context", sa.Text(), nullable=True),
        sa.Column("last_checkin_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkin_hour_utc", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "diary_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_diary_entries_user_created_at",
        "diary_entries",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_category_created_at",
        "audit_events",
        ["category", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_user_created_at",
        "audit_events",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_user_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_category_created_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_diary_entries_user_created_at", table_name="diary_entries")
    op.drop_table("diary_entries")
    op.drop_table("user_preferences")
    op.drop_index("ix_deletion_requests_status", table_name="deletion_requests")
    op.drop_table("deletion_requests")
    op.drop_index("ix_crisis_incidents_created_at", table_name="crisis_incidents")
    op.drop_table("crisis_incidents")
    op.drop_index("ix_messages_conversation_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_index("ix_payments_user_created_at", table_name="payments")
    op.drop_index("ix_payments_provider_payment_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_subscriptions_expires_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_status", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("consents")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
