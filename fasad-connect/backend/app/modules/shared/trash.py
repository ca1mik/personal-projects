"""Move documents to a recoverable trash; never cascade through business records."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.audit.service import AuditService
from app.modules.clients.models import ClientDepositMovement
from app.modules.cnc.models import CncJob
from app.modules.leads.models import Lead
from app.modules.orders.models import Order, OrderPayment
from app.modules.production.models import OrderStageInstance
from app.modules.stock.models import StockMovement


def set_deleted(db: Session, kind: str, identifier: uuid.UUID, deleted: bool, user_id):
    model = Order if kind == "order" else Lead
    document = db.scalar(select(model).where(model.id == identifier).with_for_update())
    if document is None:
        raise NotFoundError("Документ не найден")
    if bool(document.deleted_at) == deleted:
        return document
    if kind == "order":
        if deleted:
            if db.scalar(select(Order.id).where(Order.parent_order_id == identifier, Order.deleted_at.is_(None)).limit(1)):
                raise ConflictError("Сначала удалите доп. заказы или оставьте основной заказ в списке.")
            for related in (OrderPayment, ClientDepositMovement, StockMovement):
                if db.scalar(select(related.id).where(related.order_id == identifier).limit(1)):
                    raise ConflictError("У заказа есть оплаты или движения денег/материала. Для закрытия используйте статус «Отменён».")
            if document.production_start_at or document.shipped_at or document.status.code in {"cutting", "cnc", "manufacturing", "ready", "shipped"}:
                raise ConflictError("Заказ уже запускался в производство. Для закрытия используйте статус «Отменён».")
            for related in (OrderStageInstance, CncJob):
                if db.scalar(select(related.id).where(related.order_id == identifier).limit(1)):
                    raise ConflictError("У заказа есть производственные задания. Для закрытия используйте статус «Отменён».")
        elif document.parent_order_id:
            parent = db.get(Order, document.parent_order_id)
            if parent and parent.deleted_at:
                raise ConflictError("Сначала восстановите основной заказ.")
    previous = document.deleted_at
    document.deleted_at = datetime.now(UTC) if deleted else None
    AuditService.log_event(db, entity_type=kind, entity_id=str(identifier),
                          action=f"{'delete' if deleted else 'restore'}_{kind}", user_id=user_id,
                          old_value={"deleted_at": previous.isoformat() if previous else None},
                          new_value={"deleted_at": document.deleted_at.isoformat() if deleted else None})
    db.commit()
    return document
