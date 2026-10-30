from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.config.settings import Settings
from src.models import Subscription, SubscriptionPlan, SubscriptionStatus
from src.repositories.subscriptions import SubscriptionRepository
from src.services.subscriptions.plans import PlanDefinition, build_plan_map
from src.services.utils import utcnow


class SubscriptionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.plan_map = build_plan_map(settings)

    def get_plan(self, plan_code: SubscriptionPlan | str) -> PlanDefinition:
        return self.plan_map[SubscriptionPlan(plan_code)]

    def list_plans(self) -> list[PlanDefinition]:
        return list(self.plan_map.values())

    def format_pricing_text(self) -> str:
        parts = []
        for plan in self.list_plans():
            auto_renew_text = (
                "с автопродлением" if plan.auto_renew else "без автопродления"
            )
            parts.append(
                f"<b>{plan.title}</b>\n"
                f"{plan.amount:.0f} ₽\n"
                f"{plan.days} дней\n"
                f"{auto_renew_text}"
            )
        return "\n\n".join(parts)

    async def activate_from_payment(
        self,
        repository: SubscriptionRepository,
        *,
        user_id: int,
        plan_code: SubscriptionPlan | str,
        payment_method_id: str | None = None,
        force_auto_renew: bool | None = None,
    ) -> Subscription:
        now = utcnow()
        plan = self.get_plan(plan_code)
        current = await repository.get_latest_for_user(user_id)

        if current and current.status == SubscriptionStatus.ACTIVE:
            current.plan = plan.code
            current.status = SubscriptionStatus.ACTIVE
            current.started_at = current.started_at or now
            current_expires_at = (
                self._normalize_datetime(current.expires_at)
                if current.expires_at
                else None
            )
            base = (
                current_expires_at
                if current_expires_at and current_expires_at > now
                else now
            )
            current.expires_at = base + timedelta(days=plan.days)
            current.auto_renew = (
                force_auto_renew if force_auto_renew is not None else plan.auto_renew
            )
            current.cancelled_at = None
            if payment_method_id:
                current.payment_method_id = payment_method_id
            return current

        subscription = Subscription(
            user_id=user_id,
            plan=plan.code,
            status=SubscriptionStatus.ACTIVE,
            started_at=now,
            expires_at=now + timedelta(days=plan.days),
            auto_renew=(
                force_auto_renew if force_auto_renew is not None else plan.auto_renew
            ),
            payment_method_id=payment_method_id,
            cancelled_at=None,
        )
        return await repository.create(subscription)

    async def mark_expired_if_needed(
        self, repository: SubscriptionRepository, user_id: int
    ) -> Subscription | None:
        subscription = await repository.get_latest_for_user(user_id)
        if not subscription or not subscription.expires_at:
            return subscription

        expires_at = self._normalize_datetime(subscription.expires_at)
        if subscription.status == SubscriptionStatus.ACTIVE and expires_at <= utcnow():
            subscription.status = SubscriptionStatus.EXPIRED
        return subscription

    def is_active(self, subscription: Subscription | None) -> bool:
        return bool(
            subscription
            and subscription.status == SubscriptionStatus.ACTIVE
            and subscription.expires_at
            and self._normalize_datetime(subscription.expires_at) > utcnow()
        )

    def format_subscription(self, subscription: Subscription | None) -> str:
        if not subscription:
            return "Подписка пока не активна."

        next_charge = (
            subscription.expires_at.strftime("%d.%m.%Y %H:%M")
            if subscription.auto_renew and subscription.expires_at
            else "не запланировано"
        )
        return (
            f"Тариф: <b>{self.get_plan(subscription.plan).title}</b>\n"
            f"Статус: <b>{subscription.status}</b>\n"
            f"Дата окончания: <b>{subscription.expires_at.strftime('%d.%m.%Y %H:%M') if subscription.expires_at else '—'}</b>\n"
            f"Дата следующего списания: <b>{next_charge}</b>"
        )

    def disable_auto_renew(self, subscription: Subscription | None) -> bool:
        if not subscription:
            return False
        subscription.auto_renew = False
        subscription.cancelled_at = utcnow()
        return True

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
