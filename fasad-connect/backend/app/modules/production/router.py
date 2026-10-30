from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, get_page_params
from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.cnc.schemas import CncGenerateRequest, CncJobRead
from app.modules.cutting_export.schemas import ExportRead
from app.modules.orders.service import OrderService
from app.modules.parts_generator.schemas import PartRead
from app.modules.production.schemas import (
    EdgeMaterialCreate,
    EdgeMaterialRead,
    HardwareCreate,
    HardwareRead,
    MaterialCreate,
    MaterialRead,
    OrderStageRead,
    ProductionWorkerDetailRead,
    ProductionWorkflowRead,
    StageActionRequest,
    StageAssignRequest,
    StageBlockRequest,
    StageEvidenceRead,
    StagePartProgressRead,
    StagePartReportRead,
    WorkflowBootstrapRequest,
)
from app.modules.production.service import (
    ProductionCatalogService,
    ProductionWorkerService,
    ProductionWorkflowService,
)
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter()

# Справочники материалов, кромки и фурнитуры.
#
# Читать их нужно всем, кто работает с изделием, — в том числе в цехе, там по
# ним сверяются. Но не «любому вошедшему»: у роли, заведённой без единой
# галочки, доступа не должно быть ни к чему, иначе новая роль сразу открывает
# то, чего ей не давали.
CATALOG_READ = (
    "orders.manage",
    "templates.manage",
    "production.read",
    "production.manage",
    "production.execute",
)
# Заводить новую позицию — работа того, кто ведёт справочники и производство:
# справочник определяет, из чего считается заказ, и случайная строка в нём
# портит расчёт. Раньше запись стояла на голом «вошёл в систему».
CATALOG_WRITE = ("templates.manage", "production.manage")

# Подготовка производства по заказу: выгрузка раскроя и программы для станка.
# Это запись — она создаёт файлы и задания. Работа технолога и менеджера.
ORDER_PRODUCTION_WRITE = ("orders.manage", "production.manage")
# Детали, выгрузки и задания ЧПУ по заказу: цех их смотрит, поэтому шире.
ORDER_PRODUCTION_READ = (
    "orders.manage",
    "production.read",
    "production.manage",
    "production.execute",
)


@router.get("/materials", response_model=Envelope[list[MaterialRead]], tags=["materials"])
def list_materials(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CATALOG_READ))],
    params: Annotated[PageParams, Depends(get_page_params)],
) -> dict[str, object]:
    items, meta = ProductionCatalogService.list_materials(db, params)
    return envelope([MaterialRead.model_validate(item) for item in items], meta)


@router.post("/materials", response_model=Envelope[MaterialRead], tags=["materials"])
def create_material(
    payload: MaterialCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CATALOG_WRITE))],
) -> dict[str, object]:
    item = ProductionCatalogService.create_material(db, payload)
    return envelope(MaterialRead.model_validate(item))


@router.get("/edge-materials", response_model=Envelope[list[EdgeMaterialRead]], tags=["materials"])
def list_edge_materials(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CATALOG_READ))],
    params: Annotated[PageParams, Depends(get_page_params)],
) -> dict[str, object]:
    items, meta = ProductionCatalogService.list_edge_materials(db, params)
    return envelope([EdgeMaterialRead.model_validate(item) for item in items], meta)


@router.post("/edge-materials", response_model=Envelope[EdgeMaterialRead], tags=["materials"])
def create_edge_material(
    payload: EdgeMaterialCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CATALOG_WRITE))],
) -> dict[str, object]:
    item = ProductionCatalogService.create_edge_material(db, payload)
    return envelope(EdgeMaterialRead.model_validate(item))


@router.get("/hardware", response_model=Envelope[list[HardwareRead]], tags=["materials"])
def list_hardware(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CATALOG_READ))],
    params: Annotated[PageParams, Depends(get_page_params)],
) -> dict[str, object]:
    items, meta = ProductionCatalogService.list_hardware(db, params)
    return envelope([HardwareRead.model_validate(item) for item in items], meta)


@router.post("/hardware", response_model=Envelope[HardwareRead], tags=["materials"])
def create_hardware(
    payload: HardwareCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CATALOG_WRITE))],
) -> dict[str, object]:
    item = ProductionCatalogService.create_hardware(db, payload)
    return envelope(HardwareRead.model_validate(item))


@router.post(
    "/orders/{order_id}/export-cutting", response_model=Envelope[ExportRead], tags=["production"]
)
def export_cutting(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDER_PRODUCTION_WRITE))],
) -> dict[str, object]:
    export = OrderService.export_cutting(db, order_id, current_user)
    return envelope(ExportRead.model_validate(export))


@router.post(
    "/orders/{order_id}/generate-cnc",
    response_model=Envelope[list[CncJobRead]],
    tags=["production"],
)
def generate_cnc(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDER_PRODUCTION_WRITE))],
    payload: CncGenerateRequest | None = None,
) -> dict[str, object]:
    jobs = OrderService.generate_cnc(db, order_id, current_user,
                                     machine_id=payload.machine_id if payload else None)
    return envelope([CncJobRead.model_validate(item) for item in jobs])


@router.get(
    "/orders/{order_id}/parts", response_model=Envelope[list[PartRead]], tags=["production"]
)
def list_parts(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*ORDER_PRODUCTION_READ))],
) -> dict[str, object]:
    parts = OrderService.list_parts(db, order_id)
    return envelope([PartRead.model_validate(item) for item in parts])


@router.get(
    "/orders/{order_id}/exports", response_model=Envelope[list[ExportRead]], tags=["production"]
)
def list_exports(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*ORDER_PRODUCTION_READ))],
) -> dict[str, object]:
    exports = OrderService.list_exports(db, order_id)
    return envelope([ExportRead.model_validate(item) for item in exports])


@router.get(
    "/orders/{order_id}/cnc-jobs", response_model=Envelope[list[CncJobRead]], tags=["production"]
)
def list_cnc_jobs(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*ORDER_PRODUCTION_READ))],
) -> dict[str, object]:
    jobs = OrderService.list_cnc_jobs(db, order_id)
    return envelope([CncJobRead.model_validate(item) for item in jobs])


@router.get(
    "/production/workflows",
    response_model=Envelope[list[ProductionWorkflowRead]],
    tags=["production-workflow"],
)
def list_production_workflows(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[
        User,
        Depends(require_permissions("production.read", "production.manage", "production.execute")),
    ],
    params: Annotated[PageParams, Depends(get_page_params)],
) -> dict[str, object]:
    items, meta = ProductionWorkflowService.list_workflows(db, params)
    return envelope([ProductionWorkflowRead.model_validate(item) for item in items], meta)


@router.get(
    "/production/queue", response_model=Envelope[list[OrderStageRead]], tags=["production-workflow"]
)
def list_production_queue(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[
        User,
        Depends(require_permissions("production.read", "production.manage", "production.execute")),
    ],
    params: Annotated[PageParams, Depends(get_page_params)],
    status: str | None = Query(default=None),
    work_center_code: str | None = Query(default=None),
    assigned_user_id: uuid.UUID | None = Query(default=None),
) -> dict[str, object]:
    items, meta = ProductionWorkflowService.list_queue(
        db,
        params,
        status=status,
        work_center_code=work_center_code,
        assigned_user_id=assigned_user_id,
    )
    return envelope([OrderStageRead.model_validate(item) for item in items], meta)


@router.get(
    "/orders/{order_id}/stages",
    response_model=Envelope[list[OrderStageRead]],
    tags=["production-workflow"],
)
def list_order_stages(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[
        User,
        Depends(require_permissions("production.read", "production.manage", "production.execute")),
    ],
) -> dict[str, object]:
    items = ProductionWorkflowService.list_order_stages(db, order_id)
    return envelope([OrderStageRead.model_validate(item) for item in items])


@router.post(
    "/orders/{order_id}/workflow/bootstrap",
    response_model=Envelope[OrderStageRead],
    tags=["production-workflow"],
)
def bootstrap_order_workflow(
    order_id: uuid.UUID,
    payload: WorkflowBootstrapRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_permissions("production.manage", "production.execute", "orders.manage")),
    ],
) -> dict[str, object]:
    stage = ProductionWorkflowService.bootstrap_order_workflow(
        db, order_id, payload, current_user.id
    )
    return envelope(OrderStageRead.model_validate(stage))


@router.get(
    "/production/stages/{stage_instance_id}",
    response_model=Envelope[OrderStageRead],
    tags=["production-workflow"],
)
def get_stage_details(
    stage_instance_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[
        User,
        Depends(require_permissions("production.read", "production.manage", "production.execute")),
    ],
) -> dict[str, object]:
    stage = ProductionWorkflowService.get_stage(db, stage_instance_id)
    return envelope(OrderStageRead.model_validate(stage))


@router.post(
    "/production/stages/{stage_instance_id}/assign",
    response_model=Envelope[OrderStageRead],
    tags=["production-workflow"],
)
def assign_stage(
    stage_instance_id: uuid.UUID,
    payload: StageAssignRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_permissions("production.manage", "production.execute"))
    ],
) -> dict[str, object]:
    stage = ProductionWorkflowService.assign_stage(db, stage_instance_id, payload, current_user.id)
    return envelope(OrderStageRead.model_validate(stage))


@router.post(
    "/production/stages/{stage_instance_id}/start",
    response_model=Envelope[OrderStageRead],
    tags=["production-workflow"],
)
def start_stage(
    stage_instance_id: uuid.UUID,
    payload: StageActionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_permissions("production.manage", "production.execute"))
    ],
) -> dict[str, object]:
    stage = ProductionWorkflowService.start_stage(db, stage_instance_id, payload, current_user.id)
    return envelope(OrderStageRead.model_validate(stage))


@router.post(
    "/production/stages/{stage_instance_id}/complete",
    response_model=Envelope[OrderStageRead],
    tags=["production-workflow"],
)
def complete_stage(
    stage_instance_id: uuid.UUID,
    payload: StageActionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_permissions("production.manage", "production.execute"))
    ],
) -> dict[str, object]:
    stage = ProductionWorkflowService.complete_stage(
        db, stage_instance_id, payload, current_user.id
    )
    return envelope(OrderStageRead.model_validate(stage))


@router.post(
    "/production/stages/{stage_instance_id}/block",
    response_model=Envelope[OrderStageRead],
    tags=["production-workflow"],
)
def block_stage(
    stage_instance_id: uuid.UUID,
    payload: StageBlockRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_permissions("production.manage", "production.execute"))
    ],
) -> dict[str, object]:
    stage = ProductionWorkflowService.block_stage(db, stage_instance_id, payload, current_user.id)
    return envelope(OrderStageRead.model_validate(stage))


@router.post(
    "/production/stages/{stage_instance_id}/evidence",
    response_model=Envelope[StageEvidenceRead],
    tags=["production-workflow"],
)
async def upload_stage_evidence(
    stage_instance_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_permissions("production.manage", "production.execute"))
    ],
    evidence_type: str = Form(default="photo"),
    comment: str | None = Form(default=None),
) -> dict[str, object]:
    evidence = await ProductionWorkflowService.add_stage_evidence(
        db,
        stage_instance_id,
        file,
        evidence_type=evidence_type,
        comment=comment,
        acting_user_id=current_user.id,
    )
    return envelope(StageEvidenceRead.model_validate(evidence))


@router.get(
    "/production/stages/{stage_instance_id}/part-progress",
    response_model=Envelope[list[StagePartProgressRead]],
    tags=["production-workflow"],
)
def list_stage_part_progress(
    stage_instance_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[
        User,
        Depends(require_permissions("production.read", "production.manage", "production.execute")),
    ],
) -> dict[str, object]:
    items = ProductionWorkflowService.list_stage_part_progress(db, stage_instance_id)
    return envelope(items)


@router.get(
    "/production/stages/{stage_instance_id}/part-reports",
    response_model=Envelope[list[StagePartReportRead]],
    tags=["production-workflow"],
)
def list_stage_part_reports(
    stage_instance_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[
        User,
        Depends(require_permissions("production.read", "production.manage", "production.execute")),
    ],
) -> dict[str, object]:
    items = ProductionWorkflowService.list_stage_part_reports(db, stage_instance_id)
    return envelope([StagePartReportRead.model_validate(item) for item in items])


@router.post(
    "/production/stages/{stage_instance_id}/part-reports",
    response_model=Envelope[StagePartReportRead],
    tags=["production-workflow"],
)
async def create_stage_part_report(
    stage_instance_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_permissions("production.manage", "production.execute"))
    ],
    part_id: Annotated[uuid.UUID, Form(...)],
    quantity_done: Annotated[int, Form()] = 0,
    quantity_defect: Annotated[int, Form()] = 0,
    report_status: Annotated[str, Form()] = "done",
    comment: Annotated[str | None, Form()] = None,
    worker_id: Annotated[uuid.UUID | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> dict[str, object]:
    report = await ProductionWorkflowService.create_part_report(
        db,
        stage_instance_id,
        part_id=part_id,
        quantity_done=quantity_done,
        quantity_defect=quantity_defect,
        report_status=report_status,
        comment=comment,
        acting_user_id=current_user.id,
        worker_id=worker_id,
        file=file,
    )
    return envelope(StagePartReportRead.model_validate(report))


@router.get("/workers", response_model=Envelope[list[ProductionWorkerDetailRead]], tags=["workers"])
def list_workers(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[
        User,
        Depends(require_permissions("production.read", "production.manage", "production.execute")),
    ],
    params: Annotated[PageParams, Depends(get_page_params)],
) -> dict[str, object]:
    items, meta = ProductionWorkerService.list_workers(db, params)
    return envelope(items, meta)


@router.get("/workers/me", response_model=Envelope[ProductionWorkerDetailRead], tags=["workers"])
def get_my_worker_card(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_permissions("production.read", "production.manage", "production.execute")),
    ],
) -> dict[str, object]:
    worker = ProductionWorkerService.get_worker(db, current_user.id)
    return envelope(worker)


@router.get(
    "/workers/{worker_id}", response_model=Envelope[ProductionWorkerDetailRead], tags=["workers"]
)
def get_worker(
    worker_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[
        User,
        Depends(require_permissions("production.read", "production.manage", "production.execute")),
    ],
) -> dict[str, object]:
    worker = ProductionWorkerService.get_worker(db, worker_id)
    return envelope(worker)
