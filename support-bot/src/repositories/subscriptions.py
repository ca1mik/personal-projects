from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from src.models import Subscription, SubscriptionStatus
from src.repositories.base import SQLAlchemyRepository


class SubscriptionRepository(SQLAlchemyRepository):
    async def get_latest_for_user(self, user_id: int) -> Subscription | None:
        query = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.id.desc())
            .limit(1)
        )
        return await self.session.scalar(query)

    async def get_active_for_user(self, user_id: int) -> Subscription | None:
        query = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(Subscription.id.desc())
            .limit(1)
        )
        return await self.session.scalar(query)

    async def list_due_for_renewal(self, now: datetime) -> list[Subscription]:
        query = select(Subscription).where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.auto_renew.is_(True),
            Subscription.payment_method_id.is_not(None),
            Subscription.expires_at.is_not(None),
            Subscription.expires_at <= now,
        )
        return list(await self.session.scalars(query))

    async def create(self, subscription: Subscription) -> Subscription:
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def list_recent(self, limit: int = 100) -> list[Subscription]:
        query = select(Subscription).order_by(Subscription.id.desc()).limit(limit)
        return list(await self.session.scalars(query))
