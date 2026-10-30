"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-01 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("code", name=op.f("uq_roles_code")),
    )
    op.create_index(op.f("ix_roles_code"), "roles", ["code"], unique=False)

    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )
    op.create_index(op.f("ix_permissions_code"), "permissions", ["code"], unique=False)

    op.create_table(
        "clients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
    )
    op.create_index(op.f("ix_clients_email"), "clients", ["email"], unique=False)
    op.create_index(op.f("ix_clients_phone"), "clients", ["phone"], unique=False)

    op.create_table(
        "order_statuses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_terminal", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_statuses")),
        sa.UniqueConstraint("code", name=op.f("uq_order_statuses_code")),
    )
    op.create_index(op.f("ix_order_statuses_code"), "order_statuses", ["code"], unique=False)

    op.create_table(
        "product_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("formula_config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_templates")),
        sa.UniqueConstraint("code", name=op.f("uq_product_templates_code")),
    )
    op.create_index(op.f("ix_product_templates_code"), "product_templates", ["code"], unique=False)

    op.create_table(
        "materials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("thickness", sa.Numeric(10, 2), nullable=True),
        sa.Column("length", sa.Numeric(10, 2), nullable=True),
        sa.Column("width", sa.Numeric(10, 2), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("color", sa.String(length=100), nullable=True),
        sa.Column("texture_direction", sa.String(length=100), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_materials")),
        sa.UniqueConstraint("code", name=op.f("uq_materials_code")),
    )
    op.create_index(op.f("ix_materials_code"), "materials", ["code"], unique=False)

    op.create_table(
        "edge_materials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("thickness", sa.Numeric(10, 2), nullable=True),
        sa.Column("color", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edge_materials")),
        sa.UniqueConstraint("code", name=op.f("uq_edge_materials_code")),
    )
    op.create_index(op.f("ix_edge_materials_code"), "edge_materials", ["code"], unique=False)

    op.create_table(
        "hardware",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hardware")),
        sa.UniqueConstraint("code", name=op.f("uq_hardware_code")),
    )
    op.create_index(op.f("ix_hardware_code"), "hardware", ["code"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("login", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_users_role_id_roles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("login", name=op.f("uq_users_login")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_login"), "users", ["login"], unique=False)
    op.create_index(op.f("ix_users_role_id"), "users", ["role_id"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], name=op.f("fk_role_permissions_permission_id_permissions")),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_role_permissions_role_id_roles")),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name=op.f("pk_role_permissions")),
    )

    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_channel", sa.String(length=50), nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("parsed_payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_manager_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_manager_id"], ["users.id"], name=op.f("fk_leads_assigned_manager_id_users")),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name=op.f("fk_leads_client_id_clients")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leads")),
        sa.UniqueConstraint("source_channel", "external_message_id", name="uq_leads_source_external"),
    )
    op.create_index(op.f("ix_leads_assigned_manager_id"), "leads", ["assigned_manager_id"], unique=False)
    op.create_index(op.f("ix_leads_client_id"), "leads", ["client_id"], unique=False)
    op.create_index("ix_leads_external_message_id", "leads", ["external_message_id"], unique=False)
    op.create_index(op.f("ix_leads_source_channel"), "leads", ["source_channel"], unique=False)
    op.create_index(op.f("ix_leads_status"), "leads", ["status"], unique=False)

    op.create_table(
        "lead_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], name=op.f("fk_lead_attachments_lead_id_leads")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_attachments")),
    )
    op.create_index(op.f("ix_lead_attachments_lead_id"), "lead_attachments", ["lead_id"], unique=False)

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_number", sa.String(length=50), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("manager_id", sa.Uuid(), nullable=False),
        sa.Column("status_id", sa.Uuid(), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("final_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("source_lead_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("production_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name=op.f("fk_orders_client_id_clients")),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], name=op.f("fk_orders_manager_id_users")),
        sa.ForeignKeyConstraint(["source_lead_id"], ["leads.id"], name=op.f("fk_orders_source_lead_id_leads")),
        sa.ForeignKeyConstraint(["status_id"], ["order_statuses.id"], name=op.f("fk_orders_status_id_order_statuses")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("order_number", name=op.f("uq_orders_order_number")),
    )
    op.create_index(op.f("ix_orders_client_id"), "orders", ["client_id"], unique=False)
    op.create_index(op.f("ix_orders_manager_id"), "orders", ["manager_id"], unique=False)
    op.create_index(op.f("ix_orders_order_number"), "orders", ["order_number"], unique=False)
    op.create_index(op.f("ix_orders_source_lead_id"), "orders", ["source_lead_id"], unique=False)
    op.create_index(op.f("ix_orders_status_id"), "orders", ["status_id"], unique=False)

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("old_status_id", sa.Uuid(), nullable=True),
        sa.Column("new_status_id", sa.Uuid(), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], name=op.f("fk_order_status_history_changed_by_users")),
        sa.ForeignKeyConstraint(["new_status_id"], ["order_statuses.id"], name=op.f("fk_order_status_history_new_status_id_order_statuses")),
        sa.ForeignKeyConstraint(["old_status_id"], ["order_statuses.id"], name=op.f("fk_order_status_history_old_status_id_order_statuses")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_order_status_history_order_id_orders")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_status_history")),
    )
    op.create_index(op.f("ix_order_status_history_order_id"), "order_status_history", ["order_id"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("item_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("width", sa.Numeric(10, 2), nullable=False),
        sa.Column("height", sa.Numeric(10, 2), nullable=False),
        sa.Column("depth", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=True),
        sa.Column("facade_material_id", sa.Uuid(), nullable=True),
        sa.Column("thickness", sa.Numeric(10, 2), nullable=True),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["facade_material_id"], ["materials.id"], name=op.f("fk_order_items_facade_material_id_materials")),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], name=op.f("fk_order_items_material_id_materials")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_order_items_order_id_orders")),
        sa.ForeignKeyConstraint(["template_id"], ["product_templates.id"], name=op.f("fk_order_items_template_id_product_templates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
    )
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_items_template_id"), "order_items", ["template_id"], unique=False)

    op.create_table(
        "parts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("order_item_id", sa.Uuid(), nullable=False),
        sa.Column("part_code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("length", sa.Numeric(10, 2), nullable=False),
        sa.Column("width", sa.Numeric(10, 2), nullable=False),
        sa.Column("thickness", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("grain_direction", sa.String(length=50), nullable=True),
        sa.Column("rotation_allowed", sa.Boolean(), nullable=False),
        sa.Column("barcode", sa.String(length=255), nullable=True),
        sa.Column("label_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], name=op.f("fk_parts_material_id_materials")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_parts_order_id_orders")),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], name=op.f("fk_parts_order_item_id_order_items")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parts")),
    )
    op.create_index(op.f("ix_parts_order_id"), "parts", ["order_id"], unique=False)
    op.create_index(op.f("ix_parts_order_item_id"), "parts", ["order_item_id"], unique=False)
    op.create_index(op.f("ix_parts_part_code"), "parts", ["part_code"], unique=False)

    op.create_table(
        "part_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("part_id", sa.Uuid(), nullable=False),
        sa.Column("side", sa.String(length=20), nullable=False),
        sa.Column("edge_material_id", sa.Uuid(), nullable=False),
        sa.Column("thickness", sa.Numeric(10, 2), nullable=True),
        sa.Column("color", sa.String(length=100), nullable=True),
        sa.Column("length_mm", sa.Numeric(10, 2), nullable=False),
        sa.ForeignKeyConstraint(["edge_material_id"], ["edge_materials.id"], name=op.f("fk_part_edges_edge_material_id_edge_materials")),
        sa.ForeignKeyConstraint(["part_id"], ["parts.id"], name=op.f("fk_part_edges_part_id_parts")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_part_edges")),
    )
    op.create_index(op.f("ix_part_edges_part_id"), "part_edges", ["part_id"], unique=False)

    op.create_table(
        "part_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("part_id", sa.Uuid(), nullable=False),
        sa.Column("operation_type", sa.String(length=50), nullable=False),
        sa.Column("x", sa.Numeric(10, 2), nullable=True),
        sa.Column("y", sa.Numeric(10, 2), nullable=True),
        sa.Column("z", sa.Numeric(10, 2), nullable=True),
        sa.Column("diameter", sa.Numeric(10, 2), nullable=True),
        sa.Column("depth", sa.Numeric(10, 2), nullable=True),
        sa.Column("width", sa.Numeric(10, 2), nullable=True),
        sa.Column("height", sa.Numeric(10, 2), nullable=True),
        sa.Column("angle", sa.Numeric(10, 2), nullable=True),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["part_id"], ["parts.id"], name=op.f("fk_part_operations_part_id_parts")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_part_operations")),
    )
    op.create_index(op.f("ix_part_operations_part_id"), "part_operations", ["part_id"], unique=False)

    op.create_table(
        "stock_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("material_type", sa.String(length=50), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("reserved_quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_items")),
    )
    op.create_index(op.f("ix_stock_items_material_id"), "stock_items", ["material_id"], unique=False)
    op.create_index(op.f("ix_stock_items_material_type"), "stock_items", ["material_type"], unique=False)

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stock_item_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("movement_type", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_stock_movements_created_by_users")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_stock_movements_order_id_orders")),
        sa.ForeignKeyConstraint(["stock_item_id"], ["stock_items.id"], name=op.f("fk_stock_movements_stock_item_id_stock_items")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
    )
    op.create_index(op.f("ix_stock_movements_order_id"), "stock_movements", ["order_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_stock_item_id"), "stock_movements", ["stock_item_id"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("doc_type", sa.String(length=50), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_documents_created_by_users")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_documents_order_id_orders")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index(op.f("ix_documents_order_id"), "documents", ["order_id"], unique=False)

    op.create_table(
        "exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("export_type", sa.String(length=50), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_exports_created_by_users")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_exports_order_id_orders")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exports")),
    )
    op.create_index(op.f("ix_exports_order_id"), "exports", ["order_id"], unique=False)

    op.create_table(
        "cnc_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("part_id", sa.Uuid(), nullable=True),
        sa.Column("machine_name", sa.String(length=100), nullable=False),
        sa.Column("postprocessor", sa.String(length=100), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_cnc_jobs_created_by_users")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_cnc_jobs_order_id_orders")),
        sa.ForeignKeyConstraint(["part_id"], ["parts.id"], name=op.f("fk_cnc_jobs_part_id_parts")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cnc_jobs")),
    )
    op.create_index(op.f("ix_cnc_jobs_order_id"), "cnc_jobs", ["order_id"], unique=False)
    op.create_index(op.f("ix_cnc_jobs_part_id"), "cnc_jobs", ["part_id"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("old_value_json", sa.JSON(), nullable=True),
        sa.Column("new_value_json", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_audit_log_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_audit_log_entity_id"), "audit_log", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_log_entity_type"), "audit_log", ["entity_type"], unique=False)


def downgrade() -> None:
    for table_name in [
        "audit_log",
        "cnc_jobs",
        "exports",
        "documents",
        "stock_movements",
        "stock_items",
        "part_operations",
        "part_edges",
        "parts",
        "order_items",
        "order_status_history",
        "orders",
        "lead_attachments",
        "leads",
        "role_permissions",
        "users",
        "hardware",
        "edge_materials",
        "materials",
        "product_templates",
        "order_statuses",
        "clients",
        "permissions",
        "roles",
    ]:
        op.drop_table(table_name)

