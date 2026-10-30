"""Commercial stage shown consistently in the list and order card."""
from sqlalchemy import and_, not_

from app.modules.orders.models import Order
from app.modules.order_statuses.models import OrderStatus

WORK_CODES = ("accepted", "cutting", "cnc", "manufacturing")
WAIT_CODES = ("waiting_client", "approved", "paid")
DONE_CODES = ("ready", "shipped")
LABELS = {
    "estimate": "Расчёт", "waiting": "Ждём клиента", "in_work": "В работе",
    "completed": "Завершён", "cancelled": "Отменён",
}


def lifecycle_criteria(stage: str):
    def status(codes):
        return Order.status_id.in_(select_statuses(codes))
    completed = Order.shipped_at.is_not(None) | status(DONE_CODES)
    cancelled = status(("cancelled",))
    return {
        "completed": completed,
        "cancelled": and_(not_(completed), cancelled),
        "in_work": and_(not_(completed), not_(cancelled), status(WORK_CODES)),
        "waiting": and_(not_(completed), not_(cancelled), status(WAIT_CODES)),
        "estimate": and_(not_(completed), not_(cancelled), not_(status((*WORK_CODES, *WAIT_CODES)))),
    }[stage]


def select_statuses(codes):
    from sqlalchemy import select
    return select(OrderStatus.id).where(OrderStatus.code.in_(codes))


def order_lifecycle(order: Order) -> str:
    code = order.status.code if order.status else "new"
    if order.shipped_at or code in DONE_CODES:
        return "completed"
    if code == "cancelled":
        return "cancelled"
    if code in WORK_CODES:
        return "in_work"
    if code in WAIT_CODES:
        return "waiting"
    return "estimate"
