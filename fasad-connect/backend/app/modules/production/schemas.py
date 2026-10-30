from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.modules.clients.schemas import ClientRead
from app.modules.order_statuses.schemas import OrderStatusRead
from app.modules.parts_generator.schemas import PartRead
from app.modules.shared.schemas import ORMModel


class MaterialCreate(BaseModel):
    code: str
    name: str
    category: str
    thickness: Decimal | None = None
    length: Decimal | None = None
    width: Decimal | None = None
    unit: str
    color: str | None = None
    texture_direction: str | None = None
    price: Decimal = Decimal("0")
    is_active: bool = True


class MaterialRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    thickness: Decimal | None
    length: Decimal | None
    width: Decimal | None
    unit: str
    color: str | None
    texture_direction: str | None
    price: Decimal
    is_active: bool


class EdgeMaterialCreate(BaseModel):
    code: str
    name: str
    thickness: Decimal | None = None
    color: str | None = None
    unit: str
    price: Decimal = Decimal("0")
    is_active: bool = True


class EdgeMaterialRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    thickness: Decimal | None
    color: str | None
    unit: str
    price: Decimal
    is_active: bool


class HardwareCreate(BaseModel):
    code: str
    name: str
    unit: str
    price: Decimal = Decimal("0")
    params_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class HardwareRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    unit: str
    price: Decimal
    params_json: dict[str, Any]
    is_active: bool


class WorkCenterRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool


class WorkflowStageRead(ORMModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    work_center_id: uuid.UUID | None
    code: str
    name: str
    sort_order: int
    auto_start_next: bool
    requires_photo: bool
    requires_comment: bool
    is_active: bool
    work_center: WorkCenterRead | None = None


class ProductionWorkflowLiteRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    is_default: bool


class ProductionWorkflowRead(ProductionWorkflowLiteRead):
    created_at: datetime
    updated_at: datetime
    stages: list[WorkflowStageRead] = Field(default_factory=list)


class ProductionUserSummaryRead(ORMModel):
    id: uuid.UUID
    full_name: str
    login: str


class ProductionOrderSummaryRead(ORMModel):
    id: uuid.UUID
    order_number: str
    client: ClientRead | None = None
    status: OrderStatusRead | None = None


class StageAssignmentRead(ORMModel):
    id: uuid.UUID
    order_stage_instance_id: uuid.UUID
    assigned_user_id: uuid.UUID | None
    assigned_by: uuid.UUID | None
    comment: str | None
    assigned_at: datetime
    assigned_user: ProductionUserSummaryRead | None = None
    assigned_by_user: ProductionUserSummaryRead | None = None


class StageEvidenceRead(ORMModel):
    id: uuid.UUID
    order_stage_instance_id: uuid.UUID
    file_name: str
    file_path: str
    mime_type: str | None
    size_bytes: int
    evidence_type: str
    comment: str | None
    uploaded_by: uuid.UUID | None
    created_at: datetime
    uploaded_by_user: ProductionUserSummaryRead | None = None


class StagePartReportRead(ORMModel):
    id: uuid.UUID
    order_stage_instance_id: uuid.UUID
    part_id: uuid.UUID
    worker_id: uuid.UUID | None
    report_status: str
    quantity_done: int
    quantity_defect: int
    comment: str | None
    photo_file_name: str | None
    photo_file_path: str | None
    photo_mime_type: str | None
    photo_size_bytes: int | None
    created_at: datetime
    updated_at: datetime
    part: PartRead
    worker: ProductionUserSummaryRead | None = None


class StagePartProgressRead(BaseModel):
    part: PartRead
    required_quantity: int
    reported_quantity: int
    done_quantity: int
    defect_quantity: int
    remaining_quantity: int
    reports_count: int
    last_report_at: datetime | None = None
    last_worker: ProductionUserSummaryRead | None = None
    reports: list[StagePartReportRead] = Field(default_factory=list)


class OrderStageRead(ORMModel):
    id: uuid.UUID
    order_id: uuid.UUID
    workflow_id: uuid.UUID
    workflow_stage_id: uuid.UUID
    assigned_user_id: uuid.UUID | None
    created_by: uuid.UUID | None
    completed_by: uuid.UUID | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    blocked_at: datetime | None
    blocked_reason: str | None
    comment: str | None
    created_at: datetime
    updated_at: datetime
    order: ProductionOrderSummaryRead | None = None
    workflow: ProductionWorkflowLiteRead | None = None
    workflow_stage: WorkflowStageRead
    assigned_user: ProductionUserSummaryRead | None = None
    creator: ProductionUserSummaryRead | None = None
    completer: ProductionUserSummaryRead | None = None
    assignments: list[StageAssignmentRead] = Field(default_factory=list)
    evidence: list[StageEvidenceRead] = Field(default_factory=list)


class ProductionWorkerSummaryRead(ORMModel):
    id: uuid.UUID
    full_name: str
    login: str
    role_code: str
    role_name: str
    active_stage_count: int = 0
    completed_reports_count: int = 0
    done_quantity: int = 0
    defect_quantity: int = 0
    last_report_at: datetime | None = None


class ProductionWorkerDetailRead(ProductionWorkerSummaryRead):
    active_stages: list[OrderStageRead] = Field(default_factory=list)
    recent_reports: list[StagePartReportRead] = Field(default_factory=list)


class ProductionStatsBucket(BaseModel):
    code: str
    name: str
    count: int


class ProductionWorkerStatRead(BaseModel):
    worker_id: uuid.UUID | None
    worker_name: str
    reports_count: int
    done_quantity: int
    defect_quantity: int


class ProductionDashboardRead(BaseModel):
    active_stages: int
    in_progress_stages: int
    blocked_stages: int
    completed_reports: int
    done_quantity: int
    defect_quantity: int
    stages_by_status: list[ProductionStatsBucket] = Field(default_factory=list)
    reports_by_work_center: list[ProductionStatsBucket] = Field(default_factory=list)
    top_workers: list[ProductionWorkerStatRead] = Field(default_factory=list)


class WorkflowBootstrapRequest(BaseModel):
    workflow_code: str | None = None
    assigned_user_id: uuid.UUID | None = None
    comment: str | None = None


class StageAssignRequest(BaseModel):
    assigned_user_id: uuid.UUID | None = None
    comment: str | None = None


class StageActionRequest(BaseModel):
    comment: str | None = None


class StageBlockRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
    comment: str | None = None
