from __future__ import annotations

from datetime import timedelta

import pytest

from src.models import Platform, SubscriptionPlan, User
from src.repositories.subscriptions import SubscriptionRepository
from src.services.subscriptions import SubscriptionService


def test_subscription_plan_defaults_match_spec(test_settings) -> None:
    service = SubscriptionService(test_settings)

    week = service.get_plan(SubscriptionPlan.WEEK)
    month = service.get_plan(SubscriptionPlan.MONTH)
    quarter = service.get_plan(SubscriptionPlan.QUARTER)

    assert week.amount == 390
    assert week.days == 7
    assert week.auto_renew is False

    assert month.amount == 990
    assert month.days == 30
    assert month.auto_renew is True

    assert quarter.amount == 2490
    assert quarter.days == 90
    assert quarter.auto_renew is True


@pytest.mark.asyncio
async def test_activate_from_payment_calculates_started_at_and_expires_at(
    db_session_factory, test_settings
) -> None:
    service = SubscriptionService(test_settings)

    async with db_session_factory() as session:
        repository = SubscriptionRepository(session)
        deltas: dict[SubscriptionPlan, timedelta] = {}
        for idx, plan_code in enumerate(
            (SubscriptionPlan.WEEK, SubscriptionPlan.MONTH, SubscriptionPlan.QUARTER),
            start=1,
        ):
            user = User(
                platform=Platform.TELEGRAM,
                platform_user_id=f"55{idx}",
                username=f"mom55{idx}",
                first_name="Lena",
            )
            session.add(user)
            await session.flush()
            subscription = await service.activate_from_payment(
                repository, user_id=user.id, plan_code=plan_code
            )
            deltas[plan_code] = subscription.expires_at - subscription.started_at

        assert deltas[SubscriptionPlan.WEEK] == timedelta(days=7)
        assert deltas[SubscriptionPlan.MONTH] == timedelta(days=30)
        assert deltas[SubscriptionPlan.QUARTER] == timedelta(days=90)


@pytest.mark.asyncio
async def test_disable_auto_renew_sets_cancelled_at(
    db_session_factory, test_settings
) -> None:
    service = SubscriptionService(test_settings)

    async with db_session_factory() as session:
        user = User(
            platform=Platform.TELEGRAM,
            platform_user_id="66",
            username="mom66",
            first_name="Mira",
        )
        session.add(user)
        await session.flush()

        repository = SubscriptionRepository(session)
        subscription = await service.activate_from_payment(
            repository,
            user_id=user.id,
            plan_code=SubscriptionPlan.MONTH,
            payment_method_id="pm_saved",
        )

        changed = service.disable_auto_renew(subscription)

        assert changed is True
        assert subscription.auto_renew is False
        assert subscription.cancelled_at is not None
