"""Round agreed order sums to whole roubles; leave payments and item prices intact."""
from decimal import Decimal, ROUND_HALF_DOWN
from alembic import op
import sqlalchemy as sa

revision = "0024_order_whole_roubles"
down_revision = "0023_order_lifecycle_trash_counters"
branch_labels = None
depends_on = None


def upgrade():
    orders = sa.table("orders", sa.column("id", sa.String), sa.column("final_amount", sa.Numeric(12, 2)))
    connection = op.get_bind()
    for row in connection.execute(sa.select(orders.c.id, orders.c.final_amount)):
        previous = Decimal(str(row.final_amount or 0))
        rounded = previous.quantize(Decimal("1"), rounding=ROUND_HALF_DOWN)
        if previous != rounded:
            connection.execute(orders.update().where(orders.c.id == row.id).values(final_amount=rounded))


def downgrade():
    # Original kopecks can only be recovered from the pre-update database backup.
    pass
