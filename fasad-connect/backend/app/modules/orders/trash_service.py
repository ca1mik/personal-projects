"""Permanently remove only discarded orders, keeping clients and financial history."""
import logging
import uuid

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.audit.service import AuditService
from app.modules.clients.models import ClientDepositMovement
from app.modules.cnc.models import CncJob
from app.modules.cutting_export.models import Export
from app.modules.documents.models import Document
from app.modules.order_statuses.models import OrderStatusHistory
from app.modules.orders.models import Order, OrderItem, OrderPayment, OrderPosition
from app.modules.parts_generator.models import Part, PartEdge, PartOperation
from app.modules.production.models import OrderStageInstance, StagePartReport
from app.modules.stock.models import StockMovement
from app.storage.factory import get_storage_backend

logger = logging.getLogger(__name__)


def purge_orders(db: Session, identifier: uuid.UUID | None, user_id) -> int:
    query = select(Order).with_for_update().order_by(Order.id)
    query = query.where(Order.deleted_at.is_not(None)) if identifier is None else query.where(Order.id == identifier)
    orders = list(db.scalars(query))
    if identifier is not None:
        if not orders:
            raise NotFoundError("Заказ не найден")
        if orders[0].deleted_at is None:
            raise ConflictError("Сначала переместите заказ в корзину.")
    if not orders:
        return 0
    ids = [order.id for order in orders]
    if db.scalar(select(Order.id).where(Order.parent_order_id.in_(ids), Order.id.not_in(ids)).limit(1)):
        raise ConflictError("Сначала удалите доп. заказы из корзины. Действующие доп. заказы удалять вместе с основным нельзя.")
    for related in (OrderPayment, ClientDepositMovement, StockMovement, OrderStageInstance):
        if db.scalar(select(related.id).where(related.order_id.in_(ids)).limit(1)):
            raise ConflictError("В корзине есть заказ с оплатами, движениями денег/материала или производственными заданиями. Удаление отменено.")
    if any(order.production_start_at or order.shipped_at or order.status.code in {"cutting", "cnc", "manufacturing", "ready", "shipped"} for order in orders):
        raise ConflictError("Заказ уже запускался в производство. Удаление навсегда недоступно.")
    part_ids = select(Part.id).where(Part.order_id.in_(ids))
    if (db.scalar(select(CncJob.id).where(or_(CncJob.order_id.in_(ids), CncJob.part_id.in_(part_ids))).limit(1))
            or db.scalar(select(StagePartReport.id).where(StagePartReport.part_id.in_(part_ids)).limit(1))):
        raise ConflictError("Детали заказа используются в производственных заданиях. Удаление отменено.")
    paths = set(db.scalars(select(Document.file_path).where(Document.order_id.in_(ids))))
    paths.update(db.scalars(select(Export.file_path).where(Export.order_id.in_(ids))))
    try:
        for order in orders:
            AuditService.log_event(db, entity_type="order", entity_id=str(order.id), action="purge_order",
                                  user_id=user_id, old_value={"order_number": order.order_number, "deleted_at": order.deleted_at})
        # Core deletes avoid ORM attempts to null non-null part and item foreign keys.
        for related in (PartEdge, PartOperation):
            db.execute(delete(related).where(related.part_id.in_(part_ids)), execution_options={"synchronize_session": False})
        for related in (Part, Document, Export, OrderStatusHistory, OrderPosition, OrderItem):
            db.execute(delete(related).where(related.order_id.in_(ids)), execution_options={"synchronize_session": False})
        db.execute(update(Order).where(Order.id.in_(ids)).values(parent_order_id=None), execution_options={"synchronize_session": False})
        deleted = db.execute(delete(Order).where(Order.id.in_(ids), Order.deleted_at.is_not(None)),
                             execution_options={"synchronize_session": False})
        if deleted.rowcount != len(ids):
            raise ConflictError("Состав корзины изменился. Обновите страницу и повторите удаление.")
        db.commit()
        db.expire_all()
    except Exception:
        db.rollback()
        raise
    # Files are removed after the transaction succeeds, through the bounded storage API.
    for file_path in paths:
        shared = any(db.scalar(select(model.id).where(model.file_path == file_path).limit(1))
                     for model in (Document, Export, CncJob))
        if not shared:
            try:
                get_storage_backend().delete(file_path)
            except (OSError, ValueError):
                logger.warning("Could not remove an unused file after order purge", exc_info=True)
    return len(ids)
