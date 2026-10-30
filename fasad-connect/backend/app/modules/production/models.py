from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base_class import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Material(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "materials"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100))
    thickness: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    length: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    width: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[str] = mapped_column(String(20))
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    texture_direction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EdgeMaterial(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "edge_materials"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    thickness: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str] = mapped_column(String(20))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Hardware(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "hardware"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str] = mapped_column(String(20))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkCenter(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "work_centers"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    workflow_stages: Mapped[list[WorkflowStage]] = relationship(back_populates="work_center")


class ProductionWorkflow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "production_workflows"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    stages: Mapped[list[WorkflowStage]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStage.sort_order",
    )
    stage_instances: Mapped[list[OrderStageInstance]] = relationship(back_populates="workflow")


class WorkflowStage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workflow_stages"
    __table_args__ = (
        UniqueConstraint("workflow_id", "code", name="uq_workflow_stages_workflow_code"),
    )

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("production_workflows.id"), index=True
    )
    work_center_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_centers.id"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer)
    auto_start_next: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_comment: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    workflow: Mapped[ProductionWorkflow] = relationship(back_populates="stages")
    work_center: Mapped[WorkCenter | None] = relationship(back_populates="workflow_stages")
    stage_instances: Mapped[list[OrderStageInstance]] = relationship(
        back_populates="workflow_stage"
    )


class OrderStageInstance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_stage_instances"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("production_workflows.id"), index=True
    )
    workflow_stage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_stages.id"), index=True
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order] = relationship(back_populates="stage_instances")
    workflow: Mapped[ProductionWorkflow] = relationship(back_populates="stage_instances")
    workflow_stage: Mapped[WorkflowStage] = relationship(back_populates="stage_instances")
    assigned_user: Mapped[User | None] = relationship(foreign_keys=[assigned_user_id])
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])
    completer: Mapped[User | None] = relationship(foreign_keys=[completed_by])
    assignments: Mapped[list[StageAssignment]] = relationship(
        back_populates="stage_instance",
        cascade="all, delete-orphan",
        order_by="StageAssignment.assigned_at.desc()",
    )
    evidence: Mapped[list[StageEvidence]] = relationship(
        back_populates="stage_instance",
        cascade="all, delete-orphan",
        order_by="StageEvidence.created_at.desc()",
    )
    part_reports: Mapped[list[StagePartReport]] = relationship(
        back_populates="stage_instance",
        cascade="all, delete-orphan",
        order_by="StagePartReport.created_at.desc()",
    )


class StageAssignment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stage_assignments"

    order_stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("order_stage_instances.id"),
        index=True,
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    stage_instance: Mapped[OrderStageInstance] = relationship(back_populates="assignments")
    assigned_user: Mapped[User | None] = relationship(foreign_keys=[assigned_user_id])
    assigned_by_user: Mapped[User | None] = relationship(foreign_keys=[assigned_by])


class StageEvidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stage_evidence"

    order_stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("order_stage_instances.id"),
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    evidence_type: Mapped[str] = mapped_column(String(50), default="photo")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    stage_instance: Mapped[OrderStageInstance] = relationship(back_populates="evidence")
    uploaded_by_user: Mapped[User | None] = relationship(foreign_keys=[uploaded_by])


class StagePartReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage_part_reports"

    order_stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("order_stage_instances.id"),
        index=True,
    )
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"), index=True)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    report_status: Mapped[str] = mapped_column(String(50), default="done")
    quantity_done: Mapped[int] = mapped_column(Integer, default=0)
    quantity_defect: Mapped[int] = mapped_column(Integer, default=0)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    photo_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    photo_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    stage_instance: Mapped[OrderStageInstance] = relationship(back_populates="part_reports")
    part: Mapped[Part] = relationship()
    worker: Mapped[User | None] = relationship(foreign_keys=[worker_id])
