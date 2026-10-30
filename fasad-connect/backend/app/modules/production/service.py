from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.pagination import PageParams, pagination_meta
from app.modules.audit.service import AuditService
from app.modules.order_statuses.models import OrderStatusHistory
from app.modules.order_statuses.service import OrderStatusService
from app.modules.orders.models import Order
from app.modules.parts_generator.models import Part
from app.modules.production.models import (
    EdgeMaterial,
    Hardware,
    Material,
    OrderStageInstance,
    ProductionWorkflow,
    StageAssignment,
    StageEvidence,
    StagePartReport,
    WorkCenter,
    WorkflowStage,
)
from app.modules.production.schemas import (
    EdgeMaterialCreate,
    HardwareCreate,
    MaterialCreate,
    ProductionDashboardRead,
    ProductionStatsBucket,
    ProductionWorkerDetailRead,
    ProductionWorkerStatRead,
    StageActionRequest,
    StageAssignRequest,
    StageBlockRequest,
    StagePartProgressRead,
    WorkflowBootstrapRequest,
)
from app.modules.users.models import Permission, Role, User
from app.storage.factory import get_storage_backend

ACTIVE_STAGE_STATUSES = ("pending", "in_progress", "blocked")


class ProductionCatalogService:
    @staticmethod
    def list_materials(db: Session, params: PageParams) -> tuple[list[Material], dict]:
        stmt = select(Material).order_by(Material.name.asc())
        total = db.scalar(select(func.count()).select_from(Material)) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return items, pagination_meta(total, params)

    @staticmethod
    def create_material(db: Session, payload: MaterialCreate) -> Material:
        item = Material(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def list_edge_materials(db: Session, params: PageParams) -> tuple[list[EdgeMaterial], dict]:
        stmt = select(EdgeMaterial).order_by(EdgeMaterial.name.asc())
        total = db.scalar(select(func.count()).select_from(EdgeMaterial)) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return items, pagination_meta(total, params)

    @staticmethod
    def create_edge_material(db: Session, payload: EdgeMaterialCreate) -> EdgeMaterial:
        item = EdgeMaterial(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def list_hardware(db: Session, params: PageParams) -> tuple[list[Hardware], dict]:
        stmt = select(Hardware).order_by(Hardware.name.asc())
        total = db.scalar(select(func.count()).select_from(Hardware)) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return items, pagination_meta(total, params)

    @staticmethod
    def create_hardware(db: Session, payload: HardwareCreate) -> Hardware:
        item = Hardware(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item


class ProductionWorkflowService:
    @staticmethod
    def _workflow_load_options():
        return (selectinload(ProductionWorkflow.stages).selectinload(WorkflowStage.work_center),)

    @staticmethod
    def _stage_load_options():
        return (
            selectinload(OrderStageInstance.workflow),
            selectinload(OrderStageInstance.workflow_stage).selectinload(WorkflowStage.work_center),
            selectinload(OrderStageInstance.order).selectinload(Order.client),
            selectinload(OrderStageInstance.order).selectinload(Order.status),
            selectinload(OrderStageInstance.order)
            .selectinload(Order.parts)
            .selectinload(Part.edges),
            selectinload(OrderStageInstance.order)
            .selectinload(Order.parts)
            .selectinload(Part.operations),
            selectinload(OrderStageInstance.assigned_user),
            selectinload(OrderStageInstance.creator),
            selectinload(OrderStageInstance.completer),
            selectinload(OrderStageInstance.evidence).selectinload(StageEvidence.uploaded_by_user),
            selectinload(OrderStageInstance.assignments).selectinload(
                StageAssignment.assigned_user
            ),
            selectinload(OrderStageInstance.assignments).selectinload(
                StageAssignment.assigned_by_user
            ),
            selectinload(OrderStageInstance.part_reports).selectinload(StagePartReport.part),
            selectinload(OrderStageInstance.part_reports).selectinload(StagePartReport.worker),
        )

    @staticmethod
    def _part_report_load_options():
        return (
            selectinload(StagePartReport.part).selectinload(Part.edges),
            selectinload(StagePartReport.part).selectinload(Part.operations),
            selectinload(StagePartReport.worker),
        )

    @staticmethod
    def list_workflows(db: Session, params: PageParams) -> tuple[list[ProductionWorkflow], dict]:
        stmt = (
            select(ProductionWorkflow)
            .options(*ProductionWorkflowService._workflow_load_options())
            .order_by(ProductionWorkflow.is_default.desc(), ProductionWorkflow.name.asc())
        )
        total = db.scalar(select(func.count()).select_from(ProductionWorkflow)) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return items, pagination_meta(total, params)

    @staticmethod
    def _get_workflow_by_code(db: Session, workflow_code: str) -> ProductionWorkflow:
        workflow = db.scalar(
            select(ProductionWorkflow)
            .options(*ProductionWorkflowService._workflow_load_options())
            .where(ProductionWorkflow.code == workflow_code, ProductionWorkflow.is_active.is_(True))
        )
        if not workflow:
            raise NotFoundError(f"Production workflow '{workflow_code}' not found")
        return workflow

    @staticmethod
    def _get_default_workflow(db: Session) -> ProductionWorkflow:
        workflow = db.scalar(
            select(ProductionWorkflow)
            .options(*ProductionWorkflowService._workflow_load_options())
            .where(ProductionWorkflow.is_active.is_(True))
            .order_by(ProductionWorkflow.is_default.desc(), ProductionWorkflow.created_at.asc())
        )
        if not workflow:
            raise NotFoundError("No active production workflow configured")
        return workflow

    @staticmethod
    def _get_order(db: Session, order_id: uuid.UUID) -> Order:
        order = db.scalar(
            select(Order)
            .options(selectinload(Order.client), selectinload(Order.status))
            .where(Order.id == order_id, Order.deleted_at.is_(None))
        )
        if not order:
            raise NotFoundError("Order not found")
        return order

    @staticmethod
    def _get_user_or_none(db: Session, user_id: uuid.UUID | None) -> User | None:
        if not user_id:
            return None
        user = db.get(User, user_id)
        if not user:
            raise NotFoundError("User not found")
        return user

    @staticmethod
    def _get_stage_instance(db: Session, stage_instance_id: uuid.UUID) -> OrderStageInstance:
        stage = db.scalar(
            select(OrderStageInstance)
            .options(*ProductionWorkflowService._stage_load_options())
            .where(OrderStageInstance.id == stage_instance_id)
        )
        if not stage:
            raise NotFoundError("Production stage not found")
        return stage

    @staticmethod
    def _get_stage_part(stage: OrderStageInstance, part_id: uuid.UUID) -> Part:
        part = next((item for item in stage.order.parts if item.id == part_id), None)
        if not part:
            raise NotFoundError("Part not found in this order")
        return part

    @staticmethod
    def _ensure_stage_started(
        db: Session,
        stage: OrderStageInstance,
        acting_user_id: uuid.UUID | None,
        *,
        comment: str | None = None,
    ) -> None:
        if stage.status == "done":
            raise ConflictError("Stage already completed")

        now = datetime.now(UTC)
        if stage.assigned_user_id is None and acting_user_id is not None:
            stage.assigned_user_id = acting_user_id
            db.add(
                StageAssignment(
                    order_stage_instance_id=stage.id,
                    assigned_user_id=acting_user_id,
                    assigned_by=acting_user_id,
                    comment="Auto-assigned during stage execution",
                )
            )

        if stage.status in {"pending", "blocked"}:
            stage.status = "in_progress"
        stage.started_at = stage.started_at or now
        stage.blocked_at = None
        stage.blocked_reason = None
        if comment:
            stage.comment = comment

    @staticmethod
    def _has_completion_photo(stage: OrderStageInstance) -> bool:
        if any(item.evidence_type == "photo" for item in stage.evidence):
            return True
        return any(report.photo_file_path for report in stage.part_reports)

    @staticmethod
    def _build_stage_progress(stage: OrderStageInstance) -> list[StagePartProgressRead]:
        reports_by_part: dict[uuid.UUID, list[StagePartReport]] = {}
        for report in stage.part_reports:
            reports_by_part.setdefault(report.part_id, []).append(report)

        progress: list[StagePartProgressRead] = []
        for part in sorted(stage.order.parts, key=lambda item: item.part_code):
            part_reports = reports_by_part.get(part.id, [])
            done_quantity = sum(item.quantity_done for item in part_reports)
            defect_quantity = sum(item.quantity_defect for item in part_reports)
            reported_quantity = done_quantity + defect_quantity
            last_report = max(part_reports, key=lambda item: item.created_at, default=None)
            progress.append(
                StagePartProgressRead(
                    part=part,
                    required_quantity=part.quantity,
                    reported_quantity=reported_quantity,
                    done_quantity=done_quantity,
                    defect_quantity=defect_quantity,
                    remaining_quantity=max(part.quantity - reported_quantity, 0),
                    reports_count=len(part_reports),
                    last_report_at=last_report.created_at if last_report else None,
                    last_worker=last_report.worker if last_report else None,
                    reports=part_reports,
                )
            )
        return progress

    @staticmethod
    def _ensure_stage_reporting_complete(stage: OrderStageInstance) -> None:
        if not stage.order.parts:
            return

        incomplete_parts = [
            item.part.part_code
            for item in ProductionWorkflowService._build_stage_progress(stage)
            if item.remaining_quantity > 0
        ]
        if incomplete_parts:
            part_codes = ", ".join(incomplete_parts[:5])
            raise AppError(
                f"Part reports are incomplete for this stage. Remaining parts: {part_codes}"
            )

    @staticmethod
    def _sorted_stages(workflow: ProductionWorkflow) -> list[WorkflowStage]:
        return sorted(
            (stage for stage in workflow.stages if stage.is_active),
            key=lambda item: item.sort_order,
        )

    @staticmethod
    def _sync_order_status(
        db: Session,
        order: Order,
        status_code: str,
        acting_user_id: uuid.UUID | None,
        comment: str,
    ) -> None:
        try:
            new_status = OrderStatusService.get_by_code(db, status_code)
        except NotFoundError:
            return

        if order.status_id == new_status.id:
            return

        old_status_id = order.status_id
        order.status_id = new_status.id
        order.status = new_status
        now = datetime.now(UTC)
        if status_code in {"manufacturing", "cutting"} and order.production_start_at is None:
            order.production_start_at = now
        if status_code == "ready":
            order.production_start_at = order.production_start_at or now

        db.add(
            OrderStatusHistory(
                order_id=order.id,
                old_status_id=old_status_id,
                new_status_id=new_status.id,
                changed_by=acting_user_id,
                comment=comment,
            )
        )
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="change_status",
            user_id=acting_user_id,
            old_value={"status_id": str(old_status_id) if old_status_id else None},
            new_value={"status_id": str(new_status.id), "status_code": new_status.code},
        )

    @staticmethod
    def list_order_stages(db: Session, order_id: uuid.UUID) -> list[OrderStageInstance]:
        ProductionWorkflowService._get_order(db, order_id)
        stmt = (
            select(OrderStageInstance)
            .join(OrderStageInstance.workflow_stage)
            .options(*ProductionWorkflowService._stage_load_options())
            .where(OrderStageInstance.order_id == order_id)
            .order_by(WorkflowStage.sort_order.asc(), OrderStageInstance.created_at.asc())
        )
        return db.scalars(stmt).all()

    @staticmethod
    def list_queue(
        db: Session,
        params: PageParams,
        *,
        status: str | None = None,
        work_center_code: str | None = None,
        assigned_user_id: uuid.UUID | None = None,
    ) -> tuple[list[OrderStageInstance], dict]:
        stmt = (
            select(OrderStageInstance)
            .join(OrderStageInstance.workflow_stage)
            .options(*ProductionWorkflowService._stage_load_options())
        )

        if status:
            stmt = stmt.where(OrderStageInstance.status == status)
        else:
            stmt = stmt.where(OrderStageInstance.status.in_(ACTIVE_STAGE_STATUSES))

        if assigned_user_id:
            stmt = stmt.where(OrderStageInstance.assigned_user_id == assigned_user_id)

        if work_center_code:
            stmt = stmt.where(WorkflowStage.work_center.has(code=work_center_code))

        stmt = stmt.order_by(WorkflowStage.sort_order.asc(), OrderStageInstance.created_at.asc())
        total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return items, pagination_meta(total, params)

    @staticmethod
    def bootstrap_order_workflow(
        db: Session,
        order_id: uuid.UUID,
        payload: WorkflowBootstrapRequest,
        acting_user_id: uuid.UUID | None,
    ) -> OrderStageInstance:
        existing = ProductionWorkflowService.list_order_stages(db, order_id)
        if existing:
            active_stage = next((item for item in existing if item.status != "done"), None)
            return active_stage or existing[-1]

        order = ProductionWorkflowService._get_order(db, order_id)
        workflow = (
            ProductionWorkflowService._get_workflow_by_code(db, payload.workflow_code)
            if payload.workflow_code
            else ProductionWorkflowService._get_default_workflow(db)
        )
        stages = ProductionWorkflowService._sorted_stages(workflow)
        if not stages:
            raise ConflictError("Workflow has no active stages")

        first_stage = stages[0]
        stage_instance = OrderStageInstance(
            order_id=order.id,
            workflow_id=workflow.id,
            workflow_stage_id=first_stage.id,
            assigned_user_id=payload.assigned_user_id,
            created_by=acting_user_id,
            status="pending",
            comment=payload.comment,
        )
        db.add(stage_instance)
        db.flush()

        if payload.assigned_user_id:
            ProductionWorkflowService._get_user_or_none(db, payload.assigned_user_id)
            db.add(
                StageAssignment(
                    order_stage_instance_id=stage_instance.id,
                    assigned_user_id=payload.assigned_user_id,
                    assigned_by=acting_user_id,
                    comment=payload.comment or "Initial assignment during workflow bootstrap",
                )
            )

        ProductionWorkflowService._sync_order_status(
            db,
            order,
            "manufacturing",
            acting_user_id,
            "Workflow bootstrap",
        )
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="bootstrap_workflow",
            user_id=acting_user_id,
            new_value={
                "workflow_code": workflow.code,
                "stage_code": first_stage.code,
                "stage_instance_id": str(stage_instance.id),
            },
        )
        db.commit()
        return ProductionWorkflowService._get_stage_instance(db, stage_instance.id)

    @staticmethod
    def get_stage(db: Session, stage_instance_id: uuid.UUID) -> OrderStageInstance:
        return ProductionWorkflowService._get_stage_instance(db, stage_instance_id)

    @staticmethod
    def assign_stage(
        db: Session,
        stage_instance_id: uuid.UUID,
        payload: StageAssignRequest,
        acting_user_id: uuid.UUID | None,
    ) -> OrderStageInstance:
        stage = ProductionWorkflowService._get_stage_instance(db, stage_instance_id)
        if stage.status == "done":
            raise ConflictError("Cannot assign completed stage")
        ProductionWorkflowService._get_user_or_none(db, payload.assigned_user_id)
        stage.assigned_user_id = payload.assigned_user_id
        db.add(
            StageAssignment(
                order_stage_instance_id=stage.id,
                assigned_user_id=payload.assigned_user_id,
                assigned_by=acting_user_id,
                comment=payload.comment,
            )
        )
        AuditService.log_event(
            db,
            entity_type="order_stage",
            entity_id=str(stage.id),
            action="assign_stage",
            user_id=acting_user_id,
            new_value={
                "assigned_user_id": (
                    str(payload.assigned_user_id) if payload.assigned_user_id else None
                )
            },
        )
        db.commit()
        return ProductionWorkflowService._get_stage_instance(db, stage.id)

    @staticmethod
    def start_stage(
        db: Session,
        stage_instance_id: uuid.UUID,
        payload: StageActionRequest,
        acting_user_id: uuid.UUID | None,
    ) -> OrderStageInstance:
        stage = ProductionWorkflowService._get_stage_instance(db, stage_instance_id)
        ProductionWorkflowService._ensure_stage_started(
            db, stage, acting_user_id, comment=payload.comment
        )

        ProductionWorkflowService._sync_order_status(
            db,
            stage.order,
            "manufacturing",
            acting_user_id,
            f"Stage '{stage.workflow_stage.code}' started",
        )
        AuditService.log_event(
            db,
            entity_type="order_stage",
            entity_id=str(stage.id),
            action="start_stage",
            user_id=acting_user_id,
            new_value={"status": stage.status, "stage_code": stage.workflow_stage.code},
        )
        db.commit()
        return ProductionWorkflowService._get_stage_instance(db, stage.id)

    @staticmethod
    def complete_stage(
        db: Session,
        stage_instance_id: uuid.UUID,
        payload: StageActionRequest,
        acting_user_id: uuid.UUID | None,
    ) -> OrderStageInstance:
        stage = ProductionWorkflowService._get_stage_instance(db, stage_instance_id)
        if stage.status == "done":
            raise ConflictError("Stage already completed")

        if stage.workflow_stage.requires_comment and not payload.comment:
            raise AppError("Comment is required to complete this stage")

        ProductionWorkflowService._ensure_stage_reporting_complete(stage)

        if (
            stage.workflow_stage.requires_photo
            and not ProductionWorkflowService._has_completion_photo(stage)
        ):
            raise AppError("Photo evidence is required before completing this stage")

        now = datetime.now(UTC)
        stage.status = "done"
        stage.started_at = stage.started_at or now
        stage.completed_at = now
        stage.completed_by = acting_user_id
        stage.blocked_at = None
        stage.blocked_reason = None
        if payload.comment:
            stage.comment = payload.comment

        workflow_stages = ProductionWorkflowService._sorted_stages(stage.workflow)
        current_index = next(
            (
                index
                for index, workflow_stage in enumerate(workflow_stages)
                if workflow_stage.id == stage.workflow_stage_id
            ),
            None,
        )
        if current_index is None:
            raise ConflictError("Workflow stage definition not found")

        next_stage_def = (
            workflow_stages[current_index + 1] if current_index + 1 < len(workflow_stages) else None
        )
        if next_stage_def:
            next_stage = OrderStageInstance(
                order_id=stage.order_id,
                workflow_id=stage.workflow_id,
                workflow_stage_id=next_stage_def.id,
                created_by=acting_user_id,
                status="in_progress" if stage.workflow_stage.auto_start_next else "pending",
                started_at=now if stage.workflow_stage.auto_start_next else None,
                assigned_user_id=acting_user_id if stage.workflow_stage.auto_start_next else None,
            )
            db.add(next_stage)
            db.flush()
            if stage.workflow_stage.auto_start_next and acting_user_id is not None:
                db.add(
                    StageAssignment(
                        order_stage_instance_id=next_stage.id,
                        assigned_user_id=acting_user_id,
                        assigned_by=acting_user_id,
                        comment="Auto-assigned during stage transition",
                    )
                )
        else:
            ProductionWorkflowService._sync_order_status(
                db,
                stage.order,
                "ready",
                acting_user_id,
                "Production workflow completed",
            )

        AuditService.log_event(
            db,
            entity_type="order_stage",
            entity_id=str(stage.id),
            action="complete_stage",
            user_id=acting_user_id,
            new_value={
                "status": stage.status,
                "stage_code": stage.workflow_stage.code,
                "next_stage_code": next_stage_def.code if next_stage_def else None,
            },
        )
        db.commit()
        return ProductionWorkflowService._get_stage_instance(db, stage.id)

    @staticmethod
    def block_stage(
        db: Session,
        stage_instance_id: uuid.UUID,
        payload: StageBlockRequest,
        acting_user_id: uuid.UUID | None,
    ) -> OrderStageInstance:
        stage = ProductionWorkflowService._get_stage_instance(db, stage_instance_id)
        if stage.status == "done":
            raise ConflictError("Completed stage cannot be blocked")

        now = datetime.now(UTC)
        stage.status = "blocked"
        stage.started_at = stage.started_at or now
        stage.blocked_at = now
        stage.blocked_reason = payload.reason
        stage.comment = payload.comment or stage.comment

        AuditService.log_event(
            db,
            entity_type="order_stage",
            entity_id=str(stage.id),
            action="block_stage",
            user_id=acting_user_id,
            new_value={"status": stage.status, "reason": payload.reason},
        )
        db.commit()
        return ProductionWorkflowService._get_stage_instance(db, stage.id)

    @staticmethod
    def list_stage_part_progress(
        db: Session, stage_instance_id: uuid.UUID
    ) -> list[StagePartProgressRead]:
        stage = ProductionWorkflowService._get_stage_instance(db, stage_instance_id)
        return ProductionWorkflowService._build_stage_progress(stage)

    @staticmethod
    def list_stage_part_reports(db: Session, stage_instance_id: uuid.UUID) -> list[StagePartReport]:
        ProductionWorkflowService._get_stage_instance(db, stage_instance_id)
        stmt = (
            select(StagePartReport)
            .options(*ProductionWorkflowService._part_report_load_options())
            .where(StagePartReport.order_stage_instance_id == stage_instance_id)
            .order_by(StagePartReport.created_at.desc())
        )
        return db.scalars(stmt).all()

    @staticmethod
    async def create_part_report(
        db: Session,
        stage_instance_id: uuid.UUID,
        *,
        part_id: uuid.UUID,
        quantity_done: int,
        quantity_defect: int,
        report_status: str,
        comment: str | None,
        acting_user_id: uuid.UUID | None,
        worker_id: uuid.UUID | None = None,
        file: UploadFile | None = None,
    ) -> StagePartReport:
        stage = ProductionWorkflowService._get_stage_instance(db, stage_instance_id)
        if quantity_done < 0 or quantity_defect < 0:
            raise AppError("Report quantities must be positive")
        if quantity_done == 0 and quantity_defect == 0:
            raise AppError("At least one quantity must be greater than zero")

        part = ProductionWorkflowService._get_stage_part(stage, part_id)
        worker = ProductionWorkflowService._get_user_or_none(db, worker_id or acting_user_id)
        existing_quantity = sum(
            item.quantity_done + item.quantity_defect
            for item in stage.part_reports
            if item.part_id == part.id
        )
        incoming_quantity = quantity_done + quantity_defect
        if existing_quantity + incoming_quantity > part.quantity:
            raise AppError(
                f"Reported quantity exceeds required quantity for part '{part.part_code}'"
            )
        ProductionWorkflowService._ensure_stage_started(
            db, stage, worker.id if worker else acting_user_id
        )

        photo_payload: dict[str, object | None] = {
            "photo_file_name": None,
            "photo_file_path": None,
            "photo_mime_type": None,
            "photo_size_bytes": None,
        }
        if file is not None:
            content = await file.read()
            if not content:
                raise AppError("Uploaded file is empty")
            original_name = Path(file.filename or "report-photo.bin").name
            suffix = Path(original_name).suffix
            stored_name = f"{uuid.uuid4().hex}{suffix}"
            storage = get_storage_backend()
            file_path = storage.save_bytes(
                f"production/{stage.order_id}/{stage.id}/part-reports/{stored_name}",
                content,
            )
            photo_payload = {
                "photo_file_name": original_name,
                "photo_file_path": file_path,
                "photo_mime_type": file.content_type,
                "photo_size_bytes": len(content),
            }

        report = StagePartReport(
            order_stage_instance_id=stage.id,
            part_id=part.id,
            worker_id=worker.id if worker else None,
            report_status=report_status,
            quantity_done=quantity_done,
            quantity_defect=quantity_defect,
            comment=comment,
            **photo_payload,
        )
        db.add(report)
        AuditService.log_event(
            db,
            entity_type="stage_part_report",
            entity_id=str(report.id),
            action="create_part_report",
            user_id=acting_user_id,
            new_value={
                "stage_id": str(stage.id),
                "part_id": str(part.id),
                "worker_id": str(worker.id) if worker else None,
                "quantity_done": quantity_done,
                "quantity_defect": quantity_defect,
                "report_status": report_status,
            },
        )
        db.commit()
        return (
            db.scalar(
                select(StagePartReport)
                .options(*ProductionWorkflowService._part_report_load_options())
                .where(StagePartReport.id == report.id)
            )
            or report
        )

    @staticmethod
    async def add_stage_evidence(
        db: Session,
        stage_instance_id: uuid.UUID,
        file: UploadFile,
        *,
        evidence_type: str,
        comment: str | None,
        acting_user_id: uuid.UUID | None,
    ) -> StageEvidence:
        stage = ProductionWorkflowService._get_stage_instance(db, stage_instance_id)
        content = await file.read()
        if not content:
            raise AppError("Uploaded file is empty")

        original_name = Path(file.filename or "evidence.bin").name
        suffix = Path(original_name).suffix
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        storage = get_storage_backend()
        file_path = storage.save_bytes(
            f"production/{stage.order_id}/{stage.id}/{stored_name}",
            content,
        )
        evidence = StageEvidence(
            order_stage_instance_id=stage.id,
            file_name=original_name,
            file_path=file_path,
            mime_type=file.content_type,
            size_bytes=len(content),
            evidence_type=evidence_type,
            comment=comment,
            uploaded_by=acting_user_id,
        )
        db.add(evidence)
        AuditService.log_event(
            db,
            entity_type="order_stage",
            entity_id=str(stage.id),
            action="add_stage_evidence",
            user_id=acting_user_id,
            new_value={
                "file_name": original_name,
                "evidence_type": evidence_type,
                "size_bytes": len(content),
            },
        )
        db.commit()
        db.refresh(evidence)
        return evidence


class ProductionWorkerService:
    @staticmethod
    def _worker_stmt():
        return (
            select(User)
            .join(User.role)
            .join(Role.permissions, isouter=True)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(
                User.is_active.is_(True),
                (Role.code == "admin") | (Permission.code == "production.execute"),
            )
            .distinct()
            .order_by(User.full_name.asc())
        )

    @staticmethod
    def _build_worker_summary(
        db: Session,
        users: list[User],
    ) -> list[ProductionWorkerDetailRead]:
        if not users:
            return []

        user_ids = [user.id for user in users]
        active_stage_rows = db.execute(
            select(OrderStageInstance.assigned_user_id, func.count(OrderStageInstance.id))
            .where(
                OrderStageInstance.assigned_user_id.in_(user_ids),
                OrderStageInstance.status.in_(ACTIVE_STAGE_STATUSES),
            )
            .group_by(OrderStageInstance.assigned_user_id)
        ).all()
        active_stage_map = {user_id: int(count) for user_id, count in active_stage_rows}

        report_rows = db.execute(
            select(
                StagePartReport.worker_id,
                func.count(StagePartReport.id),
                func.coalesce(func.sum(StagePartReport.quantity_done), 0),
                func.coalesce(func.sum(StagePartReport.quantity_defect), 0),
                func.max(StagePartReport.created_at),
            )
            .where(StagePartReport.worker_id.in_(user_ids))
            .group_by(StagePartReport.worker_id)
        ).all()
        report_map = {
            worker_id: {
                "completed_reports_count": int(count),
                "done_quantity": int(done_quantity or 0),
                "defect_quantity": int(defect_quantity or 0),
                "last_report_at": last_report_at,
            }
            for worker_id, count, done_quantity, defect_quantity, last_report_at in report_rows
        }

        active_stage_stmt = (
            select(OrderStageInstance)
            .options(*ProductionWorkflowService._stage_load_options())
            .where(
                OrderStageInstance.assigned_user_id.in_(user_ids),
                OrderStageInstance.status.in_(ACTIVE_STAGE_STATUSES),
            )
            .order_by(OrderStageInstance.created_at.desc())
        )
        active_stages = db.scalars(active_stage_stmt).all()
        stages_by_user: dict[uuid.UUID, list[OrderStageInstance]] = {}
        for stage in active_stages:
            if stage.assigned_user_id:
                stages_by_user.setdefault(stage.assigned_user_id, []).append(stage)

        recent_reports_stmt = (
            select(StagePartReport)
            .options(*ProductionWorkflowService._part_report_load_options())
            .where(StagePartReport.worker_id.in_(user_ids))
            .order_by(StagePartReport.created_at.desc())
        )
        recent_reports = db.scalars(recent_reports_stmt).all()
        reports_by_user: dict[uuid.UUID, list[StagePartReport]] = {}
        for report in recent_reports:
            if report.worker_id:
                reports_by_user.setdefault(report.worker_id, []).append(report)

        result: list[ProductionWorkerDetailRead] = []
        for user in users:
            report_data = report_map.get(user.id, {})
            result.append(
                ProductionWorkerDetailRead(
                    id=user.id,
                    full_name=user.full_name,
                    login=user.login,
                    role_code=user.role.code,
                    role_name=user.role.name,
                    active_stage_count=active_stage_map.get(user.id, 0),
                    completed_reports_count=report_data.get("completed_reports_count", 0),
                    done_quantity=report_data.get("done_quantity", 0),
                    defect_quantity=report_data.get("defect_quantity", 0),
                    last_report_at=report_data.get("last_report_at"),
                    active_stages=stages_by_user.get(user.id, []),
                    recent_reports=reports_by_user.get(user.id, [])[:10],
                )
            )
        return result

    @staticmethod
    def list_workers(
        db: Session, params: PageParams
    ) -> tuple[list[ProductionWorkerDetailRead], dict]:
        stmt = ProductionWorkerService._worker_stmt()
        total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        users = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return ProductionWorkerService._build_worker_summary(db, users), pagination_meta(
            total, params
        )

    @staticmethod
    def get_worker(db: Session, worker_id: uuid.UUID) -> ProductionWorkerDetailRead:
        user = db.scalar(ProductionWorkerService._worker_stmt().where(User.id == worker_id))
        if not user:
            raise NotFoundError("Worker not found")
        return ProductionWorkerService._build_worker_summary(db, [user])[0]

    @staticmethod
    def get_worker_by_login(db: Session, login: str) -> ProductionWorkerDetailRead:
        user = db.scalar(ProductionWorkerService._worker_stmt().where(User.login == login))
        if not user:
            raise NotFoundError("Worker not found")
        return ProductionWorkerService._build_worker_summary(db, [user])[0]


class ProductionAnalyticsService:
    @staticmethod
    def get_dashboard(db: Session) -> ProductionDashboardRead:
        active_stages = int(
            db.scalar(
                select(func.count())
                .select_from(OrderStageInstance)
                .where(OrderStageInstance.status.in_(ACTIVE_STAGE_STATUSES))
            )
            or 0
        )
        in_progress_stages = int(
            db.scalar(
                select(func.count())
                .select_from(OrderStageInstance)
                .where(OrderStageInstance.status == "in_progress")
            )
            or 0
        )
        blocked_stages = int(
            db.scalar(
                select(func.count())
                .select_from(OrderStageInstance)
                .where(OrderStageInstance.status == "blocked")
            )
            or 0
        )

        report_totals = db.execute(
            select(
                func.count(StagePartReport.id),
                func.coalesce(func.sum(StagePartReport.quantity_done), 0),
                func.coalesce(func.sum(StagePartReport.quantity_defect), 0),
            )
        ).one()
        completed_reports = int(report_totals[0] or 0)
        done_quantity = int(report_totals[1] or 0)
        defect_quantity = int(report_totals[2] or 0)

        stage_status_rows = db.execute(
            select(OrderStageInstance.status, func.count(OrderStageInstance.id))
            .group_by(OrderStageInstance.status)
            .order_by(OrderStageInstance.status.asc())
        ).all()
        work_center_rows = db.execute(
            select(
                func.coalesce(WorkCenter.code, "unassigned"),
                func.coalesce(WorkCenter.name, "Unassigned"),
                func.count(StagePartReport.id),
            )
            .select_from(StagePartReport)
            .join(StagePartReport.stage_instance)
            .join(OrderStageInstance.workflow_stage)
            .join(WorkflowStage.work_center, isouter=True)
            .group_by(WorkCenter.code, WorkCenter.name)
            .order_by(func.count(StagePartReport.id).desc(), WorkCenter.name.asc())
        ).all()
        worker_rows = db.execute(
            select(
                User.id,
                User.full_name,
                func.count(StagePartReport.id),
                func.coalesce(func.sum(StagePartReport.quantity_done), 0),
                func.coalesce(func.sum(StagePartReport.quantity_defect), 0),
            )
            .select_from(StagePartReport)
            .join(StagePartReport.worker, isouter=True)
            .group_by(User.id, User.full_name)
            .order_by(func.count(StagePartReport.id).desc(), User.full_name.asc())
            .limit(5)
        ).all()

        return ProductionDashboardRead(
            active_stages=active_stages,
            in_progress_stages=in_progress_stages,
            blocked_stages=blocked_stages,
            completed_reports=completed_reports,
            done_quantity=done_quantity,
            defect_quantity=defect_quantity,
            stages_by_status=[
                ProductionStatsBucket(
                    code=status, name=status.replace("_", " ").title(), count=int(count)
                )
                for status, count in stage_status_rows
            ],
            reports_by_work_center=[
                ProductionStatsBucket(code=code, name=name, count=int(count))
                for code, name, count in work_center_rows
            ],
            top_workers=[
                ProductionWorkerStatRead(
                    worker_id=worker_id,
                    worker_name=worker_name or "Unassigned",
                    reports_count=int(reports_count),
                    done_quantity=int(done_qty or 0),
                    defect_quantity=int(defect_qty or 0),
                )
                for worker_id, worker_name, reports_count, done_qty, defect_qty in worker_rows
            ],
        )
