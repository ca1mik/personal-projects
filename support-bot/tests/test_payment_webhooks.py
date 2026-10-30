from __future__ import annotations

from datetime import timedelta

import pytest

from src.models import PaymentStatus, Platform, SubscriptionStatus, User
from src.repositories.payments import PaymentRepository
from src.repositories.subscriptions import SubscriptionRepository
from src.services.payments.service import PaymentApplicationService
from src.services.subscriptions import SubscriptionService
from src.services.utils import utcnow


class StubYooKassa:
    def __init__(self) -> None:
        self.counter = 0

    def create_payment(
        self,
        *,
        user_id: int,
        plan,
        description: str,
        customer_email: str | None,
        idempotence_key: str | None = None,
    ):
        raise AssertionError("create_payment is not used in webhook tests")

    def charge_saved_payment_method(
        self,
        *,
        user_id: int,
        payment_method_id: str,
        plan,
        customer_email: str | None,
        idempotence_key: str | None = None,
    ) -> dict:
        self.counter += 1
        return {
            "id": f"renew_{self.counter}",
            "status": "succeeded",
            "amount": {"value": f"{plan.amount:.2f}", "currency": "RUB"},
            "payment_method": {"id": payment_method_id},
            "metadata": {
                "user_id": str(user_id),
                "plan": str(plan.code),
                "renewal": "true",
            },
        }

    @staticmethod
    def map_status(status: str) -> str:
        return {
            "pending": "pending",
            "succeeded": "succeeded",
            "canceled": "canceled",
            "waiting_for_capture": "pending",
        }.get(status, "failed")

    @staticmethod
    def extract_payment_method_id(payment_object: dict) -> str | None:
        return payment_object.get("payment_method", {}).get("id")

    @staticmethod
    def extract_amount(payment_object: dict):
        from decimal import Decimal

        return Decimal(str(payment_object["amount"]["value"]))

    @staticmethod
    def extract_error_message(payment_object: dict) -> str | None:
        return None


@pytest.mark.asyncio
async def test_yookassa_webhook_is_idempotent(
    db_session_factory, test_settings
) -> None:
    service = PaymentApplicationService(
        settings=test_settings,
        yookassa=StubYooKassa(),
        subscriptions=SubscriptionService(test_settings),
    )

    async with db_session_factory() as session:
        user = User(
            platform=Platform.TELEGRAM,
            platform_user_id="42",
            username="mom",
            first_name="Anna",
            email="mom@example.com",
        )
        session.add(user)
        await session.flush()

        payload = {
            "object": {
                "id": "yk_1",
                "status": "succeeded",
                "amount": {"value": "990.00", "currency": "RUB"},
                "payment_method": {"id": "pm_1"},
                "metadata": {"user_id": str(user.id), "plan": "month"},
            }
        }

        handled = await service.handle_yookassa_webhook(session, payload)
        subscription = await SubscriptionRepository(session).get_latest_for_user(
            user.id
        )
        first_expiry = subscription.expires_at
        await service.handle_yookassa_webhook(session, payload)
        await session.commit()

        payment = await PaymentRepository(session).get_by_provider_payment_id("yk_1")
        subscription = await SubscriptionRepository(session).get_latest_for_user(
            user.id
        )

        assert handled is True
        assert payment is not None
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.payment_method_id == "pm_1"
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.expires_at == first_expiry


@pytest.mark.asyncio
async def test_recurring_payment_renews_due_subscription(
    db_session_factory, test_settings
) -> None:
    service = PaymentApplicationService(
        settings=test_settings,
        yookassa=StubYooKassa(),
        subscriptions=SubscriptionService(test_settings),
    )

    async with db_session_factory() as session:
        user = User(
            platform=Platform.TELEGRAM,
            platform_user_id="42",
            username="mom",
            first_name="Anna",
            email="mom@example.com",
        )
        session.add(user)
        await session.flush()

        subscriptions = SubscriptionRepository(session)
        subscription = await service.subscriptions.activate_from_payment(
            subscriptions,
            user_id=user.id,
            plan_code="month",
            payment_method_id="pm_saved",
        )
        subscription.expires_at = utcnow() - timedelta(minutes=1)
        subscription.auto_renew = True
        await session.commit()

        renewed = await service.renew_due_subscriptions(session)
        await session.commit()

        payment = await PaymentRepository(session).get_latest_for_user(user.id)
        updated_subscription = await subscriptions.get_latest_for_user(user.id)

        assert renewed == [user.id]
        assert payment is not None
        assert payment.is_recurrent is True
        assert updated_subscription.status == SubscriptionStatus.ACTIVE
        assert updated_subscription.expires_at > utcnow()


class FailingYooKassa(StubYooKassa):
    def charge_saved_payment_method(
        self,
        *,
        user_id: int,
        payment_method_id: str,
        plan,
        customer_email: str | None,
        idempotence_key: str | None = None,
    ) -> dict:
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_recurring_payment_failure_marks_subscription_past_due(
    db_session_factory, test_settings
) -> None:
    service = PaymentApplicationService(
        settings=test_settings,
        yookassa=FailingYooKassa(),
        subscriptions=SubscriptionService(test_settings),
    )

    async with db_session_factory() as session:
        user = User(
            platform=Platform.TELEGRAM,
            platform_user_id="90",
            username="mom",
            first_name="Anna",
            email="mom@example.com",
        )
        session.add(user)
        await session.flush()

        subscriptions = SubscriptionRepository(session)
        subscription = await service.subscriptions.activate_from_payment(
            subscriptions,
            user_id=user.id,
            plan_code="month",
            payment_method_id="pm_saved",
        )
        subscription.expires_at = utcnow() - timedelta(minutes=1)
        subscription.auto_renew = True
        await session.commit()

        renewed = await service.renew_due_subscriptions(session)
        await session.commit()

        updated_subscription = await subscriptions.get_latest_for_user(user.id)

        assert renewed == []
        assert updated_subscription.status == SubscriptionStatus.PAST_DUE
