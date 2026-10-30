"""Selectable CNC machine profiles; generated files remain previews."""

from alembic import op
import sqlalchemy as sa

revision = "0022_cnc_machines"
down_revision = "0021_client_deposit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cnc_machines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("controller", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cnc_machines_name", "cnc_machines", ["name"], unique=True)
    with op.batch_alter_table("cnc_jobs") as batch:
        batch.add_column(sa.Column("machine_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_cnc_jobs_machine_id_cnc_machines", "cnc_machines", ["machine_id"], ["id"])
        batch.create_index("ix_cnc_jobs_machine_id", ["machine_id"])


def downgrade() -> None:
    with op.batch_alter_table("cnc_jobs") as batch:
        batch.drop_index("ix_cnc_jobs_machine_id")
        batch.drop_constraint("fk_cnc_jobs_machine_id_cnc_machines", type_="foreignkey")
        batch.drop_column("machine_id")
    op.drop_index("ix_cnc_machines_name", "cnc_machines")
    op.drop_table("cnc_machines")
