from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.cnc.schemas import CncMachineCreate, CncMachineRead, CncMachineUpdate
from app.modules.cnc.service import CncService
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter(prefix="/cnc", tags=["cnc"])


@router.get("/machines", response_model=Envelope[list[CncMachineRead]])
def list_machines(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("orders.manage", "production.read", "production.manage"))],
) -> dict[str, object]:
    return envelope([CncMachineRead.model_validate(item) for item in CncService.list_machines(db)])


@router.post("/machines", response_model=Envelope[CncMachineRead])
def create_machine(
    payload: CncMachineCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("production.manage"))],
) -> dict[str, object]:
    return envelope(CncMachineRead.model_validate(CncService.create_machine(db, payload, user.id)))


@router.patch("/machines/{machine_id}", response_model=Envelope[CncMachineRead])
def update_machine(
    machine_id: uuid.UUID,
    payload: CncMachineUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("production.manage"))],
) -> dict[str, object]:
    return envelope(CncMachineRead.model_validate(CncService.update_machine(db, machine_id, payload, user.id)))
