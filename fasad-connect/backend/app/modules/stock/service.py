from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import ROUND_UP, Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError
from app.core.pagination import PageParams, pagination_meta
from app.db.mixins import utcnow
from app.modules.audit.service import AuditService
from app.modules.orders.models import Order
from app.modules.production.models import EdgeMaterial, Material
from app.modules.stock.models import StockItem, StockMovement
from app.modules.stock.schemas import StockReceiptCreate

STOCK_PRECISION = Decimal("0.001")


class StockService:
    @staticmethod
    def list_stock_items(db: Session, params: PageParams) -> tuple[list[StockItem], dict]:
        stmt = select(StockItem).order_by(StockItem.updated_at.desc())
        total = db.scalar(select(func.count()).select_from(StockItem)) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return items, pagination_meta(total, params)

    @staticmethod
    def list_movements(db: Session, params: PageParams) -> tuple[list[StockMovement], dict]:
        stmt = select(StockMovement).order_by(StockMovement.created_at.desc())
        total = db.scalar(select(func.count()).select_from(StockMovement)) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return items, pagination_meta(total, params)

    @staticmethod
    def _get_or_create_item(db: Session, *, material_type: str, material_id: uuid.UUID, unit: str) -> StockItem:
        item = db.scalar(select(StockItem).where(
            StockItem.material_type == material_type, StockItem.material_id == material_id,
        ))
        if item:
            return item
        item = StockItem(material_type=material_type, material_id=material_id,
                         quantity=Decimal("0"), reserved_quantity=Decimal("0"), unit=unit)
        db.add(item)
        db.flush()
        return item

    @staticmethod
    def _requirements(order: Order) -> dict[tuple[str, uuid.UUID, str], Decimal]:
        needs: dict[tuple[str, uuid.UUID, str], Decimal] = defaultdict(lambda: Decimal("0"))
        for part in order.parts:
            needs[("material", part.material_id, "sqm")] += (
                Decimal(part.length) * Decimal(part.width) * Decimal(part.quantity)
            ) / Decimal("1000000")
            for edge in part.edges:
                needs[("edge_material", edge.edge_material_id, "m")] += (
                    Decimal(edge.length_mm) * Decimal(part.quantity)
                ) / Decimal("1000")
        return {key: qty.quantize(STOCK_PRECISION, rounding=ROUND_UP)
                for key, qty in needs.items() if qty > 0}

    @staticmethod
    def _movement_quantities(db: Session, order_id: uuid.UUID, movement_type: str) -> dict[uuid.UUID, Decimal]:
        rows = db.scalars(select(StockMovement).where(
            StockMovement.order_id == order_id, StockMovement.movement_type == movement_type,
        )).all()
        quantities: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
        for row in rows:
            quantities[row.stock_item_id] += Decimal(row.quantity)
        return dict(quantities)

    @staticmethod
    def receive(db: Session, payload: StockReceiptCreate, acting_user_id: uuid.UUID) -> StockItem:
        model = Material if payload.material_type == "material" else EdgeMaterial
        if not db.get(model, payload.material_id):
            raise AppError("Материал не найден", 404)
        unit = "sqm" if payload.material_type == "material" else "m"
        item = StockService._get_or_create_item(db, material_type=payload.material_type,
                                                material_id=payload.material_id, unit=unit)
        qty = Decimal(payload.quantity).quantize(STOCK_PRECISION, rounding=ROUND_UP)
        db.execute(update(StockItem).where(StockItem.id == item.id).values(
            quantity=StockItem.quantity + qty, updated_at=utcnow(),
        ))
        db.add(StockMovement(stock_item_id=item.id, movement_type="receipt", quantity=qty,
                             unit=unit, created_by=acting_user_id, comment=payload.comment))
        AuditService.log_event(db, entity_type="stock_item", entity_id=str(item.id),
                               action="receive_stock", user_id=acting_user_id,
                               new_value={"quantity": str(qty), "material_type": payload.material_type})
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def reserve_for_order(db: Session, order: Order, acting_user_id: uuid.UUID | None = None) -> None:
        needs = StockService._requirements(order)
        if not needs:
            raise AppError("В заказе нет деталей для резерва материала", 422)
        existing = StockService._movement_quantities(db, order.id, "reserve")
        if existing:
            expected = {}
            for (material_type, material_id, _), qty in needs.items():
                item = db.scalar(select(StockItem).where(StockItem.material_type == material_type,
                                                          StockItem.material_id == material_id))
                if item:
                    expected[item.id] = qty
            if existing == expected:
                return
            raise ConflictError("Резерв заказа уже существует для другого состава деталей")
        for (material_type, material_id, unit), qty in needs.items():
            item = db.scalar(select(StockItem).where(StockItem.material_type == material_type,
                                                      StockItem.material_id == material_id))
            if item is None:
                db.rollback()
                raise AppError("Материала нет на складе; сначала оформите приход", 422)
            result = db.execute(update(StockItem).where(
                StockItem.id == item.id,
                StockItem.quantity - StockItem.reserved_quantity >= qty,
            ).values(reserved_quantity=StockItem.reserved_quantity + qty, updated_at=utcnow()))
            if result.rowcount != 1:
                db.rollback()
                raise AppError("Недостаточно свободного материала на складе", 422)
            db.add(StockMovement(stock_item_id=item.id, order_id=order.id, movement_type="reserve",
                                 quantity=qty, unit=unit, created_by=acting_user_id,
                                 comment=f"Резерв для заказа {order.order_number}"))
        AuditService.log_event(db, entity_type="order", entity_id=str(order.id),
                               action="reserve_stock", user_id=acting_user_id)
        db.commit()

    @staticmethod
    def writeoff_for_order(db: Session, order: Order, acting_user_id: uuid.UUID | None = None) -> None:
        needs = StockService._requirements(order)
        if not needs:
            raise AppError("В заказе нет деталей для списания материала", 422)
        if StockService._movement_quantities(db, order.id, "writeoff"):
            return
        reservations = StockService._movement_quantities(db, order.id, "reserve")
        if not reservations:
            raise ConflictError("Сначала зарезервируйте материал для заказа")
        for (material_type, material_id, unit), qty in needs.items():
            item = db.scalar(select(StockItem).where(StockItem.material_type == material_type,
                                                      StockItem.material_id == material_id))
            if item is None or reservations.get(item.id, Decimal("0")) != qty:
                db.rollback()
                raise ConflictError("Резерв не соответствует текущему составу заказа")
            result = db.execute(update(StockItem).where(
                StockItem.id == item.id, StockItem.quantity >= qty,
                StockItem.reserved_quantity >= qty,
            ).values(quantity=StockItem.quantity - qty,
                     reserved_quantity=StockItem.reserved_quantity - qty,
                     updated_at=utcnow()))
            if result.rowcount != 1:
                db.rollback()
                raise AppError("Недостаточно зарезервированного материала для списания", 422)
            db.add(StockMovement(stock_item_id=item.id, order_id=order.id, movement_type="writeoff",
                                 quantity=qty, unit=unit, created_by=acting_user_id,
                                 comment=f"Списание для заказа {order.order_number}"))
        order.production_start_at = order.production_start_at or utcnow()
        AuditService.log_event(db, entity_type="order", entity_id=str(order.id),
                               action="writeoff_stock", user_id=acting_user_id)
        db.commit()
