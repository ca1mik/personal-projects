"""Explicit waiting/accepted stages, recoverable deletion and durable numbering."""
import uuid
from alembic import op
import sqlalchemy as sa

revision = "0023_order_lifecycle_trash_counters"
down_revision = "0022_cnc_machines"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("orders", "leads"):
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index(f"ix_{table}_deleted_at", table, ["deleted_at"])
    op.create_table("document_counters", sa.Column("scope", sa.String(30), primary_key=True),
                    sa.Column("value", sa.BigInteger(), nullable=False))
    connection = op.get_bind()
    # Freeze number history before any user can move a record to the trash.
    from app.modules.shared.numbering import highest
    for scope, field in (("orders", "order_number"), ("leads", "lead_number")):
        value = highest(scope, connection.execute(sa.text(f"SELECT {field} FROM {scope}")).scalars())
        connection.execute(sa.text("INSERT INTO document_counters (scope,value) VALUES (:scope,:value)"),
                           {"scope": scope, "value": value})
    statuses = sa.table("order_statuses", sa.column("id", sa.Uuid()), sa.column("code", sa.String()),
                        sa.column("name", sa.String()), sa.column("sort_order", sa.Integer()),
                        sa.column("is_terminal", sa.Boolean()))
    for code, name, order in (("waiting_client", "Ждём ответа клиента", 25),
                               ("accepted", "Принят в работу", 35)):
        if not connection.scalar(sa.select(statuses.c.id).where(statuses.c.code == code)):
            connection.execute(statuses.insert().values(id=uuid.uuid4(), code=code, name=name,
                                                        sort_order=order, is_terminal=False))


def downgrade():
    # Keep statuses already referenced by real orders; downgrading must not orphan history.
    for table in ("leads", "orders"):
        op.drop_index(f"ix_{table}_deleted_at", table_name=table)
        op.drop_column(table, "deleted_at")
    op.drop_table("document_counters")
