from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.dashboard.schemas import DashboardSummary
from app.modules.dashboard.service import DashboardService
from app.modules.production.schemas import ProductionDashboardRead
from app.modules.production.service import ProductionAnalyticsService
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter()

DASHBOARD_READ = ("dashboard.read",)
# Сводка по цеху — без денег: этапы, отчёты, брак. Её видят и те, кто в цехе.
PRODUCTION_DASHBOARD_READ = ("dashboard.read", "production.read", "production.manage")
#: Кому в сводке показываем выручку. Право на саму сводку деньгами не заведует:
#: цеху сводка нужна ради этапов и брака, а выручка студии — нет.
MONEY_IN_SUMMARY = {"orders.manage"}


@router.get("/summary", response_model=Envelope[DashboardSummary])
def summary(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*DASHBOARD_READ))],
) -> dict[str, object]:
    data = DashboardService.get_summary(db)
    granted = {item.code for item in current_user.role.permissions}
    if current_user.role.code != "admin" and not (granted & MONEY_IN_SUMMARY):
        # Не ноль, а «нет значения»: ноль читался бы как «выручки нет».
        data.mock_revenue = None
    return envelope(data)


@router.get("/production", response_model=Envelope[ProductionDashboardRead])
def production_summary(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*PRODUCTION_DASHBOARD_READ))],
) -> dict[str, object]:
    return envelope(ProductionAnalyticsService.get_dashboard(db))
