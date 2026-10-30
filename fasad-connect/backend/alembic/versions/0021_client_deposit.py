"""Independent client deposits and allocations to orders."""

from alembic import op
import sqlalchemy as sa

revision = "0021_client_deposit"
down_revision = "0020_order_no_rotation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_deposit_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("method", sa.String(30), nullable=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("payment_id", sa.Uuid(), sa.ForeignKey("order_payments.id"), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_client_deposit_movements_client_id", "client_deposit_movements", ["client_id"])
    op.create_index("ix_client_deposit_movements_payment_id", "client_deposit_movements", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_client_deposit_movements_payment_id", "client_deposit_movements")
    op.drop_index("ix_client_deposit_movements_client_id", "client_deposit_movements")
    op.drop_table("client_deposit_movements")
