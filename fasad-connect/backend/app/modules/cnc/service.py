from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.audit.service import AuditService
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.modules.cnc.models import CncJob, CncMachine
from app.modules.cnc.schemas import CncMachineCreate, CncMachineUpdate
from app.modules.orders.models import Order
from app.modules.parts_generator.models import Part
from app.storage.factory import get_storage_backend


class CncService:
    @staticmethod
    def list_machines(db: Session) -> list[CncMachine]:
        return db.scalars(select(CncMachine).order_by(CncMachine.name)).all()

    @staticmethod
    def create_machine(db: Session, payload: CncMachineCreate, user_id: uuid.UUID) -> CncMachine:
        name = payload.name.strip()
        if db.scalar(select(CncMachine.id).where(CncMachine.name == name)):
            raise ConflictError("Станок с таким названием уже есть")
        machine = CncMachine(name=name, controller=(payload.controller or "").strip() or None,
                             is_active=True)
        db.add(machine)
        db.flush()
        AuditService.log_event(db, entity_type="cnc_machine", entity_id=str(machine.id),
                               action="create_machine", user_id=user_id,
                               new_value={"name": machine.name, "controller": machine.controller})
        db.commit()
        db.refresh(machine)
        return machine

    @staticmethod
    def update_machine(db: Session, machine_id: uuid.UUID, payload: CncMachineUpdate,
                       user_id: uuid.UUID) -> CncMachine:
        machine = db.get(CncMachine, machine_id)
        if not machine:
            raise NotFoundError("Станок не найден")
        if payload.name is not None:
            name = payload.name.strip()
            taken = db.scalar(select(CncMachine.id).where(CncMachine.name == name,
                                                           CncMachine.id != machine.id))
            if taken:
                raise ConflictError("Станок с таким названием уже есть")
            machine.name = name
        if payload.controller is not None:
            machine.controller = payload.controller.strip() or None
        if payload.is_active is not None:
            machine.is_active = payload.is_active
        AuditService.log_event(db, entity_type="cnc_machine", entity_id=str(machine.id),
                               action="update_machine", user_id=user_id,
                               new_value={"name": machine.name, "controller": machine.controller,
                                          "is_active": machine.is_active})
        db.commit()
        db.refresh(machine)
        return machine

    @staticmethod
    def generate_jobs(db: Session, order: Order, acting_user_id: uuid.UUID | None = None,
                      machine_id: uuid.UUID | None = None) -> list[CncJob]:
        order = (
            db.scalar(
                select(Order)
                .options(selectinload(Order.parts).selectinload(Part.operations),
                         selectinload(Order.positions))
                .where(Order.id == order.id)
            )
            or order
        )
        if not order.parts and not order.positions:
            raise AppError("В заказе нет деталей или фасадных позиций для черновика ЧПУ", 422)
        if order.parts and order.positions:
            raise AppError("В заказе смешаны детали и фасадные позиции; выберите один состав", 422)

        machine = db.get(CncMachine, machine_id) if machine_id else None
        if machine_id and (machine is None or not machine.is_active):
            raise AppError("Выбранный станок не найден или отключён", 422)

        storage = get_storage_backend()
        version = (
            db.scalar(select(func.count()).select_from(CncJob).where(CncJob.order_id == order.id))
            or 0
        ) + 1
        created_jobs: list[CncJob] = []

        for part in order.parts:
            controller_label = (machine.controller or "not configured") if machine else "not configured"
            lines = [
                "; PREVIEW ONLY - NOT A MACHINE PROGRAM",
                f"; Selected machine: {machine.name if machine else 'Demo preview'}",
                f"; Controller: {controller_label}",
                f"; Part: {part.part_code}",
                f"; Part size: {part.length} x {part.width} x {part.thickness}",
            ]
            for operation in part.operations:
                lines.append(
                    f"{operation.operation_type.upper()} X={operation.x or 0} Y={operation.y or 0} D={operation.diameter or 0} DEPTH={operation.depth or 0}"
                )
            machine_tag = machine.id.hex[:8] if machine else "demo"
            file_name = f"{part.part_code}-{machine_tag}-v{version}.preview.txt"
            file_path = storage.save_text(f"cnc/{order.id}/{file_name}", "\n".join(lines))
            job = CncJob(
                order_id=order.id,
                part_id=part.id,
                machine_id=machine.id if machine else None,
                machine_name=machine.name if machine else "Демо-черновик",
                postprocessor="mock_text_v1",
                file_name=file_name,
                file_path=file_path,
                version=version,
                created_by=acting_user_id,
            )
            db.add(job)
            created_jobs.append(job)

        for position in order.positions:
            machine_tag = machine.id.hex[:8] if machine else "demo"
            file_name = f"facade-{position.line_no}-{machine_tag}-v{version}.preview.txt"
            lines = [
                "; PREVIEW ONLY - NOT A MACHINE PROGRAM",
                f"; Selected machine: {machine.name if machine else 'Demo preview'}",
                f"; Controller: {(machine.controller or 'not configured') if machine else 'not configured'}",
                f"; Facade line: {position.line_no} / {position.name}",
                f"; Article: {position.article or 'not specified'}",
                f"; Milling: {position.milling or 'not specified'}",
                f"; Color: {position.color or 'not specified'}",
                f"; Size mm: {position.width} x {position.height} x {position.thickness or 'unspecified'}",
                f"; Quantity: {position.quantity}",
            ]
            file_path = storage.save_text(f"cnc/{order.id}/{file_name}", "\n".join(lines))
            job = CncJob(order_id=order.id, part_id=None,
                         machine_id=machine.id if machine else None,
                         machine_name=machine.name if machine else "Демо-черновик",
                         postprocessor="mock_text_v1", file_name=file_name,
                         file_path=file_path, version=version, created_by=acting_user_id)
            db.add(job)
            created_jobs.append(job)

        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="generate_cnc",
            user_id=acting_user_id,
            new_value={"jobs_count": len(created_jobs), "version": version,
                       "machine_id": str(machine.id) if machine else None},
        )
        db.commit()
        return created_jobs
