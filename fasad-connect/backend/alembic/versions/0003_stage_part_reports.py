"""stage part reports

Revision ID: 0003_stage_part_reports
Revises: 0002_production_workflow
Create Date: 2026-04-01 22:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_stage_part_reports"
down_revision = "0002_production_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stage_part_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_stage_instance_id", sa.Uuid(), nullable=False),
        sa.Column("part_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=True),
        sa.Column("report_status", sa.String(length=50), nullable=False),
        sa.Column("quantity_done", sa.Integer(), nullable=False),
        sa.Column("quantity_defect", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("photo_file_name", sa.String(length=255), nullable=True),
        sa.Column("photo_file_path", sa.String(length=500), nullable=True),
        sa.Column("photo_mime_type", sa.String(length=100), nullable=True),
        sa.Column("photo_size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_stage_instance_id"], ["order_stage_instances.id"], name=op.f("fk_stage_part_reports_order_stage_instance_id_order_stage_instances")),
        sa.ForeignKeyConstraint(["part_id"], ["parts.id"], name=op.f("fk_stage_part_reports_part_id_parts")),
        sa.ForeignKeyConstraint(["worker_id"], ["users.id"], name=op.f("fk_stage_part_reports_worker_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stage_part_reports")),
    )
    op.create_index(op.f("ix_stage_part_reports_order_stage_instance_id"), "stage_part_reports", ["order_stage_instance_id"], unique=False)
    op.create_index(op.f("ix_stage_part_reports_part_id"), "stage_part_reports", ["part_id"], unique=False)
    op.create_index(op.f("ix_stage_part_reports_worker_id"), "stage_part_reports", ["worker_id"], unique=False)


def downgrade() -> None:
    op.drop_table("stage_part_reports")
