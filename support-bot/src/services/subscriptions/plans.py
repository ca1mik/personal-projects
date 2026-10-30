from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.config.settings import Settings
from src.models import SubscriptionPlan


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    code: SubscriptionPlan
    title: str
    amount: Decimal
    days: int
    auto_renew: bool
    description: str


def build_plan_map(settings: Settings) -> dict[SubscriptionPlan, PlanDefinition]:
    return {
        SubscriptionPlan.WEEK: PlanDefinition(
            code=SubscriptionPlan.WEEK,
            title=settings.plan_week_title,
            amount=Decimal(str(settings.plan_week_price_rub)),
            days=settings.plan_week_days,
            auto_renew=settings.plan_week_auto_renew,
            description=settings.plan_week_description,
        ),
        SubscriptionPlan.MONTH: PlanDefinition(
            code=SubscriptionPlan.MONTH,
            title=settings.plan_month_title,
            amount=Decimal(str(settings.plan_month_price_rub)),
            days=settings.plan_month_days,
            auto_renew=settings.plan_month_auto_renew,
            description=settings.plan_month_description,
        ),
        SubscriptionPlan.QUARTER: PlanDefinition(
            code=SubscriptionPlan.QUARTER,
            title=settings.plan_quarter_title,
            amount=Decimal(str(settings.plan_quarter_price_rub)),
            days=settings.plan_quarter_days,
            auto_renew=settings.plan_quarter_auto_renew,
            description=settings.plan_quarter_description,
        ),
    }
