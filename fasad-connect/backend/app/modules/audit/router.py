from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, get_page_params
from app.core.responses import envelope
from app.db.session import get_db
from app.modules.audit.schemas import AuditLogRead
from app.modules.audit.service import AuditService
from app.modules.auth.dependencies import require_permissions
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter(tags=["audit"])


@router.get("/admin/audit", response_model=Envelope[list[AuditLogRead]])
def list_audit_log(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("audit.read"))],
    params: Annotated[PageParams, Depends(get_page_params)],
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
) -> dict[str, object]:
    items, meta = AuditService.list_events(db, params, entity_type=entity_type, action=action)
    return envelope([AuditLogRead.model_validate(item) for item in items], meta)
