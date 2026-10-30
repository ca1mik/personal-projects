from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.audit.service import AuditService
from app.modules.orders.models import Order, OrderItem
from app.modules.parts_generator.models import Part, PartEdge, PartOperation
from app.modules.parts_generator.strategies import build_blueprint
from app.modules.production.models import EdgeMaterial, Material


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


class PartsGeneratorService:
    @staticmethod
    def _resolve_material(db: Session, item: OrderItem) -> Material:
        if item.material:
            return item.material
        material = db.scalar(
            select(Material).where(Material.is_active.is_(True)).order_by(Material.name.asc())
        )
        if not material:
            raise ValueError("No active materials configured")
        return material

    @staticmethod
    def _resolve_edge_material(db: Session) -> EdgeMaterial:
        edge = db.scalar(
            select(EdgeMaterial)
            .where(EdgeMaterial.is_active.is_(True))
            .order_by(EdgeMaterial.name.asc())
        )
        if not edge:
            raise ValueError("No active edge materials configured")
        return edge

    @staticmethod
    def _clear_existing_parts(db: Session, order: Order) -> None:
        parts = db.scalars(select(Part).where(Part.order_id == order.id)).all()
        for part in parts:
            db.delete(part)
        db.flush()

    @staticmethod
    def _template_code(item: OrderItem) -> str:
        if item.template and item.template.code:
            return item.template.code
        return item.item_type

    @staticmethod
    def list_parts(db: Session, order_id) -> list[Part]:
        stmt = (
            select(Part)
            .options(selectinload(Part.edges), selectinload(Part.operations))
            .where(Part.order_id == order_id)
            .order_by(Part.part_code.asc())
        )
        return db.scalars(stmt).all()

    @staticmethod
    def estimate_accessories(order: Order) -> tuple[dict[str, Decimal], Decimal]:
        hardware: dict[str, Decimal] = {}
        base_work = Decimal("0")
        for item in order.items:
            blueprint = build_blueprint(
                PartsGeneratorService._template_code(item),
                width=item.width,
                height=item.height,
                depth=item.depth,
                quantity=item.quantity,
                thickness=item.thickness,
            )
            base_work += blueprint.base_work_cost
            for code, qty in blueprint.hardware_requirements.items():
                hardware[code] = hardware.get(code, Decimal("0")) + qty
        return hardware, base_work

    @staticmethod
    def generate_parts(db: Session, order: Order, acting_user_id: str | None = None) -> list[Part]:
        order = (
            db.scalar(
                select(Order)
                .options(
                    selectinload(Order.items).selectinload(OrderItem.template),
                    selectinload(Order.items).selectinload(OrderItem.material),
                )
                .where(Order.id == order.id)
            )
            or order
        )
        edge_material = PartsGeneratorService._resolve_edge_material(db)
        PartsGeneratorService._clear_existing_parts(db, order)

        generated_parts: list[Part] = []
        for item in order.items:
            material = PartsGeneratorService._resolve_material(db, item)
            blueprint = build_blueprint(
                PartsGeneratorService._template_code(item),
                width=item.width,
                height=item.height,
                depth=item.depth,
                quantity=item.quantity,
                thickness=item.thickness or material.thickness or Decimal("18"),
            )
            item_slug = _slugify(item.name or item.item_type)
            for index, spec in enumerate(blueprint.parts, start=1):
                part = Part(
                    order_id=order.id,
                    order_item_id=item.id,
                    part_code=f"{item_slug}-{spec.code.lower()}",
                    name=spec.name,
                    length=spec.length,
                    width=spec.width,
                    thickness=spec.thickness,
                    quantity=spec.quantity,
                    material_id=material.id,
                    grain_direction=spec.grain_direction,
                    rotation_allowed=spec.rotation_allowed,
                    barcode=f"{order.order_number}-{item_slug}-{index:02d}",
                    label_text=f"{order.order_number} | {item.name} | {spec.name}",
                )
                db.add(part)
                db.flush()
                for edge in spec.edges:
                    db.add(
                        PartEdge(
                            part_id=part.id,
                            side=edge.side,
                            edge_material_id=edge_material.id,
                            thickness=edge_material.thickness,
                            color=edge_material.color,
                            length_mm=edge.length_mm,
                        )
                    )
                for operation in spec.operations:
                    db.add(
                        PartOperation(
                            part_id=part.id,
                            operation_type=operation.operation_type,
                            x=operation.x,
                            y=operation.y,
                            z=operation.z,
                            diameter=operation.diameter,
                            depth=operation.depth,
                            width=operation.width,
                            height=operation.height,
                            angle=operation.angle,
                            params_json=operation.params_json,
                        )
                    )
                generated_parts.append(part)

        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="generate_parts",
            user_id=acting_user_id,
            new_value={"parts_count": len(generated_parts)},
        )
        db.commit()
        return PartsGeneratorService.list_parts(db, order.id)
