from __future__ import annotations

from app.modules.orders.money import round_order_amount

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.modules.audit.service import AuditService
from app.modules.documents.service import DocumentService
from app.modules.orders.models import Order
from app.modules.orders.schemas import OrderCalculationResult, PricingComponent
from app.modules.parts_generator.models import Part
from app.modules.parts_generator.service import PartsGeneratorService
from app.modules.production.models import EdgeMaterial, Hardware, Material

MARKUP_COEFFICIENT = Decimal("1.15")


class PricingService:
    @staticmethod
    def calculate_order(
        db: Session, order: Order, acting_user_id: str | None = None
    ) -> OrderCalculationResult:
        order = (
            db.scalar(
                select(Order)
                .options(
                    selectinload(Order.items),
                    selectinload(Order.positions),
                    selectinload(Order.parts).selectinload(Part.edges),
                )
                .where(Order.id == order.id)
            )
            or order
        )
        if order.positions and order.items:
            raise AppError("Заказ содержит одновременно строки сметы и изделия каталога; выберите один способ расчёта", 422)
        if not order.items:
            components = [
                PricingComponent(
                    code=position.article or f"position-{position.line_no}",
                    name=position.name,
                    amount=Decimal(position.amount),
                    unit=position.unit,
                    quantity=Decimal(position.quantity),
                )
                for position in order.positions
            ]
            total_amount = sum((component.amount for component in components), Decimal("0"))
            discount_amount = Decimal(order.discount_amount or 0)
            order.total_amount = total_amount
            order.final_amount = round_order_amount(total_amount - discount_amount)
            order.currency = get_settings().default_currency
            DocumentService.generate_order_documents(db, order, components, acting_user_id)
            AuditService.log_event(
                db,
                entity_type="order",
                entity_id=str(order.id),
                action="calculate_order",
                user_id=acting_user_id,
                new_value={"total_amount": str(order.total_amount), "final_amount": str(order.final_amount)},
            )
            db.commit()
            db.refresh(order)
            return OrderCalculationResult(
                total_amount=order.total_amount,
                discount_amount=order.discount_amount,
                final_amount=order.final_amount,
                currency=order.currency,
                components=components,
            )
        if not order.parts:
            try:
                PartsGeneratorService.generate_parts(db, order, acting_user_id)
            except ValueError as exc:
                raise AppError(str(exc), 422) from exc
            order = (
                db.scalar(
                    select(Order)
                    .options(
                        selectinload(Order.items),
                        selectinload(Order.parts).selectinload(Part.edges),
                    )
                    .where(Order.id == order.id)
                )
                or order
            )

        components: list[PricingComponent] = []
        material_totals: dict[str, Decimal] = {}
        edge_totals: dict[str, Decimal] = {}

        for part in order.parts:
            material = db.get(Material, part.material_id)
            if not material:
                continue
            area_sqm = (
                Decimal(part.length) * Decimal(part.width) * Decimal(part.quantity)
            ) / Decimal("1000000")
            amount = area_sqm * material.price
            material_totals[material.code] = (
                material_totals.get(material.code, Decimal("0")) + amount
            )
            for edge in part.edges:
                edge_material = db.get(EdgeMaterial, edge.edge_material_id)
                if not edge_material:
                    continue
                edge_qty = (Decimal(edge.length_mm) * Decimal(part.quantity)) / Decimal("1000")
                edge_amount = edge_qty * edge_material.price
                edge_totals[edge_material.code] = (
                    edge_totals.get(edge_material.code, Decimal("0")) + edge_amount
                )

        for code, amount in material_totals.items():
            components.append(
                PricingComponent(
                    code=code,
                    name=f"Material {code}",
                    amount=amount,
                    unit="sqm",
                    quantity=Decimal("1"),
                )
            )
        for code, amount in edge_totals.items():
            components.append(
                PricingComponent(
                    code=code, name=f"Edge {code}", amount=amount, unit="m", quantity=Decimal("1")
                )
            )

        hardware_requirements, base_work = PartsGeneratorService.estimate_accessories(order)
        for code, qty in hardware_requirements.items():
            hardware = db.scalar(select(Hardware).where(Hardware.code == code))
            if not hardware:
                continue
            amount = qty * hardware.price
            components.append(
                PricingComponent(
                    code=code, name=hardware.name, amount=amount, unit=hardware.unit, quantity=qty
                )
            )

        components.append(
            PricingComponent(
                code="base_work",
                name="Base production work",
                amount=base_work,
                unit="job",
                quantity=Decimal("1"),
            )
        )

        subtotal = sum((item.amount for item in components), Decimal("0"))
        total_amount = subtotal * MARKUP_COEFFICIENT
        discount_amount = order.discount_amount or Decimal("0")
        final_amount = round_order_amount(max(total_amount - discount_amount, Decimal("0")))

        order.total_amount = total_amount
        order.final_amount = final_amount
        order.currency = get_settings().default_currency

        DocumentService.generate_order_documents(db, order, components, acting_user_id)
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="calculate_order",
            user_id=acting_user_id,
            new_value={"total_amount": str(total_amount), "final_amount": str(final_amount)},
        )
        db.commit()
        db.refresh(order)
        return OrderCalculationResult(
            total_amount=order.total_amount,
            discount_amount=order.discount_amount,
            final_amount=order.final_amount,
            currency=order.currency,
            components=components,
        )
