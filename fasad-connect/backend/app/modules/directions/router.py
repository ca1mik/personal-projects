from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permissions
from app.modules.directions.schemas import DirectionCreate, DirectionRead, DirectionUpdate
from app.modules.directions.service import DirectionService
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter()


@router.get("/directions", response_model=Envelope[list[DirectionRead]])
def list_directions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    only_active: bool = Query(default=False),
) -> dict[str, object]:
    directions = DirectionService.list_directions(db, only_active=only_active)
    return envelope([DirectionRead.model_validate(item) for item in directions])


@router.post("/directions", response_model=Envelope[DirectionRead])
def create_direction(
    payload: DirectionCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("orders.manage"))],
) -> dict[str, object]:
    direction = DirectionService.create_direction(db, payload, current_user.id)
    return envelope(DirectionRead.model_validate(direction))


@router.patch("/directions/{direction_id}", response_model=Envelope[DirectionRead])
def update_direction(
    direction_id: uuid.UUID,
    payload: DirectionUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("orders.manage"))],
) -> dict[str, object]:
    direction = DirectionService.update_direction(db, direction_id, payload, current_user.id)
    return envelope(DirectionRead.model_validate(direction))
