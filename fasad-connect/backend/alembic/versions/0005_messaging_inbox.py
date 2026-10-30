"""messaging inbox foundation

Revision ID: 0005_messaging_inbox
Revises: 0004_telegram_bot_sessions
Create Date: 2026-04-03 11:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_messaging_inbox"
down_revision = "0004_telegram_bot_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_accounts",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("channel_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("inbound_mode", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("default_manager_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["default_manager_id"],
            ["users.id"],
            name=op.f("fk_channel_accounts_default_manager_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_channel_accounts")),
        sa.UniqueConstraint("code", name=op.f("uq_channel_accounts_code")),
    )
    op.create_index(op.f("ix_channel_accounts_code"), "channel_accounts", ["code"], unique=True)
    op.create_index(
        op.f("ix_channel_accounts_channel_type"),
        "channel_accounts",
        ["channel_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_channel_accounts_default_manager_id"),
        "channel_accounts",
        ["default_manager_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_channel_accounts_is_active"),
        "channel_accounts",
        ["is_active"],
        unique=False,
    )

    op.create_table(
        "conversations",
        sa.Column("channel_account_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("source_lead_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_manager_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("contact_key", sa.String(length=255), nullable=False),
        sa.Column("external_chat_id", sa.String(length=255), nullable=True),
        sa.Column("external_thread_id", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("participant_name", sa.String(length=255), nullable=True),
        sa.Column("participant_phone", sa.String(length=50), nullable=True),
        sa.Column("participant_email", sa.String(length=255), nullable=True),
        sa.Column("participant_external_id", sa.String(length=255), nullable=True),
        sa.Column("unread_count", sa.Integer(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_preview", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assigned_manager_id"],
            ["users.id"],
            name=op.f("fk_conversations_assigned_manager_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["channel_account_id"],
            ["channel_accounts.id"],
            name=op.f("fk_conversations_channel_account_id_channel_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_conversations_client_id_clients"),
        ),
        sa.ForeignKeyConstraint(
            ["source_lead_id"],
            ["leads.id"],
            name=op.f("fk_conversations_source_lead_id_leads"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(
        op.f("ix_conversations_assigned_manager_id"),
        "conversations",
        ["assigned_manager_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_channel_account_id"),
        "conversations",
        ["channel_account_id"],
        unique=False,
    )
    op.create_index(op.f("ix_conversations_client_id"), "conversations", ["client_id"], unique=False)
    op.create_index(
        op.f("ix_conversations_contact_key"),
        "conversations",
        ["contact_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_external_chat_id"),
        "conversations",
        ["external_chat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_external_thread_id"),
        "conversations",
        ["external_thread_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_source_lead_id"),
        "conversations",
        ["source_lead_id"],
        unique=False,
    )
    op.create_index(op.f("ix_conversations_status"), "conversations", ["status"], unique=False)

    op.create_table(
        "messages",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source_channel", sa.String(length=50), nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("sender_name", sa.String(length=255), nullable=True),
        sa.Column("sender_phone", sa.String(length=50), nullable=True),
        sa.Column("sender_email", sa.String(length=255), nullable=True),
        sa.Column("sender_external_id", sa.String(length=255), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_messages_lead_id_leads"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_messages_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.UniqueConstraint(
            "source_channel",
            "external_message_id",
            name="uq_messages_source_external",
        ),
    )
    op.create_index(
        op.f("ix_messages_conversation_id"),
        "messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(op.f("ix_messages_direction"), "messages", ["direction"], unique=False)
    op.create_index(
        op.f("ix_messages_external_message_id"),
        "messages",
        ["external_message_id"],
        unique=False,
    )
    op.create_index(op.f("ix_messages_lead_id"), "messages", ["lead_id"], unique=False)
    op.create_index(
        op.f("ix_messages_source_channel"),
        "messages",
        ["source_channel"],
        unique=False,
    )
    op.create_index(op.f("ix_messages_status"), "messages", ["status"], unique=False)
    op.create_index(op.f("ix_messages_user_id"), "messages", ["user_id"], unique=False)

    op.create_table(
        "message_attachments",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_message_attachments_message_id_messages"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_attachments")),
    )
    op.create_index(
        op.f("ix_message_attachments_message_id"),
        "message_attachments",
        ["message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_message_attachments_message_id"), table_name="message_attachments")
    op.drop_table("message_attachments")

    op.drop_index(op.f("ix_messages_user_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_status"), table_name="messages")
    op.drop_index(op.f("ix_messages_source_channel"), table_name="messages")
    op.drop_index(op.f("ix_messages_lead_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_external_message_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_direction"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_table("messages")

    op.drop_index(op.f("ix_conversations_status"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_source_lead_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_external_thread_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_external_chat_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_contact_key"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_client_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_channel_account_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_assigned_manager_id"), table_name="conversations")
    op.drop_table("conversations")

    op.drop_index(op.f("ix_channel_accounts_is_active"), table_name="channel_accounts")
    op.drop_index(op.f("ix_channel_accounts_default_manager_id"), table_name="channel_accounts")
    op.drop_index(op.f("ix_channel_accounts_channel_type"), table_name="channel_accounts")
    op.drop_index(op.f("ix_channel_accounts_code"), table_name="channel_accounts")
    op.drop_table("channel_accounts")
