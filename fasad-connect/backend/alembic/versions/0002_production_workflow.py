"""production workflow

Revision ID: 0002_production_workflow
Revises: 0001_initial_schema
Create Date: 2026-04-01 13:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_production_workflow"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_centers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_centers")),
        sa.UniqueConstraint("code", name=op.f("uq_work_centers_code")),
    )
    op.create_index(op.f("ix_work_centers_code"), "work_centers", ["code"], unique=False)

    op.create_table(
        "production_workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_production_workflows")),
        sa.UniqueConstraint("code", name=op.f("uq_production_workflows_code")),
    )
    op.create_index(op.f("ix_production_workflows_code"), "production_workflows", ["code"], unique=False)

    op.create_table(
        "workflow_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("work_center_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("auto_start_next", sa.Boolean(), nullable=False),
        sa.Column("requires_photo", sa.Boolean(), nullable=False),
        sa.Column("requires_comment", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["work_center_id"], ["work_centers.id"], name=op.f("fk_workflow_stages_work_center_id_work_centers")),
        sa.ForeignKeyConstraint(["workflow_id"], ["production_workflows.id"], name=op.f("fk_workflow_stages_workflow_id_production_workflows")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_stages")),
        sa.UniqueConstraint("workflow_id", "code", name="uq_workflow_stages_workflow_code"),
    )
    op.create_index(op.f("ix_workflow_stages_work_center_id"), "workflow_stages", ["work_center_id"], unique=False)
    op.create_index(op.f("ix_workflow_stages_workflow_id"), "workflow_stages", ["workflow_id"], unique=False)

    op.create_table(
        "order_stage_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_stage_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("completed_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], name=op.f("fk_order_stage_instances_assigned_user_id_users")),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"], name=op.f("fk_order_stage_instances_completed_by_users")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_order_stage_instances_created_by_users")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_order_stage_instances_order_id_orders")),
        sa.ForeignKeyConstraint(["workflow_id"], ["production_workflows.id"], name=op.f("fk_order_stage_instances_workflow_id_production_workflows")),
        sa.ForeignKeyConstraint(["workflow_stage_id"], ["workflow_stages.id"], name=op.f("fk_order_stage_instances_workflow_stage_id_workflow_stages")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_stage_instances")),
    )
    op.create_index(op.f("ix_order_stage_instances_assigned_user_id"), "order_stage_instances", ["assigned_user_id"], unique=False)
    op.create_index(op.f("ix_order_stage_instances_order_id"), "order_stage_instances", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_stage_instances_status"), "order_stage_instances", ["status"], unique=False)
    op.create_index(op.f("ix_order_stage_instances_workflow_id"), "order_stage_instances", ["workflow_id"], unique=False)
    op.create_index(op.f("ix_order_stage_instances_workflow_stage_id"), "order_stage_instances", ["workflow_stage_id"], unique=False)

    op.create_table(
        "stage_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_stage_instance_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], name=op.f("fk_stage_assignments_assigned_by_users")),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], name=op.f("fk_stage_assignments_assigned_user_id_users")),
        sa.ForeignKeyConstraint(["order_stage_instance_id"], ["order_stage_instances.id"], name=op.f("fk_stage_assignments_order_stage_instance_id_order_stage_instances")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stage_assignments")),
    )
    op.create_index(op.f("ix_stage_assignments_order_stage_instance_id"), "stage_assignments", ["order_stage_instance_id"], unique=False)

    op.create_table(
        "stage_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_stage_instance_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_stage_instance_id"], ["order_stage_instances.id"], name=op.f("fk_stage_evidence_order_stage_instance_id_order_stage_instances")),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], name=op.f("fk_stage_evidence_uploaded_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stage_evidence")),
    )
    op.create_index(op.f("ix_stage_evidence_order_stage_instance_id"), "stage_evidence", ["order_stage_instance_id"], unique=False)


def downgrade() -> None:
    for table_name in [
        "stage_evidence",
        "stage_assignments",
        "order_stage_instances",
        "workflow_stages",
        "production_workflows",
        "work_centers",
    ]:
        op.drop_table(table_name)
