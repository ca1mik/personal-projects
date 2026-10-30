from __future__ import annotations

from decimal import Decimal

import pytest

from src.models import (
    PaymentStatus,
    Platform,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
)
from src.repositories.payments import PaymentRepository
from src.repositories.subscriptions import SubscriptionRepository
from src.services.payments.service import PaymentApplicationService
from src.services.payments.yookassa_service import YooKassaService
from src.services.subscriptions import SubscriptionService


@pytest.mark.asyncio
async def test_apply_telegram_success_creates_payment_and_subscription(
    db_session_factory, test_settings
) -> None:
    service = PaymentApplicationService(
        settings=test_settings,
        yookassa=YooKassaService(test_settings),
        subscriptions=SubscriptionService(test_settings),
    )

    async with db_session_factory() as session:
        user = User(
            platform=Platform.TELEGRAM,
            platform_user_id="42",
            username="mom",
            first_name="Anna",
        )
        session.add(user)
        await session.flush()

        await service.apply_telegram_success(
            session,
            user_id=user.id,
            plan_code=SubscriptionPlan.MONTH,
            provider_payment_id="tg_charge_1",
            amount_rub=Decimal("990.00"),
        )
        await session.commit()

        payment = await PaymentRepository(session).get_latest_for_user(user.id)
        subscription = await SubscriptionRepository(session).get_latest_for_user(
            user.id
        )

        assert payment is not None
        assert payment.status == PaymentStatus.SUCCEEDED
        assert subscription is not None
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.plan == SubscriptionPlan.MONTH
        assert subscription.auto_renew is False


@pytest.mark.asyncio
async def test_start_yookassa_checkout_saves_provider_payment_id_and_url(
    db_session_factory,
    test_settings,
    stub_yookassa,
) -> None:
    service = PaymentApplicationService(
        settings=test_settings,
        yookassa=stub_yookassa,
        subscriptions=SubscriptionService(test_settings),
    )

    async with db_session_factory() as session:
        user = User(
            platform=Platform.TELEGRAM,
            platform_user_id="77",
            username="mom77",
            first_name="Olga",
            email="mom@example.com",
        )
        session.add(user)
        await session.flush()

        checkout = await service.start_yookassa_checkout(
            session,
            user_id=user.id,
            plan_code=SubscriptionPlan.WEEK,
            customer_email=user.email,
        )
        await session.commit()

        payment = await PaymentRepository(session).get_by_provider_payment_id(
            checkout.payment_id
        )

        assert checkout.payment_url == "https://pay.example/1"
        assert payment is not None
        assert payment.provider_payment_id == "pay_1"
        assert payment.confirmation_url == "https://pay.example/1"
        assert payment.idempotence_key == "idem_1"
        assert stub_yookassa.create_calls[0]["customer_email"] == "mom@example.com"


@pytest.mark.asyncio
async def test_start_yookassa_checkout_reuses_pending_checkout(
    db_session_factory,
    test_settings,
    stub_yookassa,
) -> None:
    service = PaymentApplicationService(
        settings=test_settings,
        yookassa=stub_yookassa,
        subscriptions=SubscriptionService(test_settings),
    )

    async with db_session_factory() as session:
        user = User(
            platform=Platform.TELEGRAM,
            platform_user_id="88",
            username="mom88",
            first_name="Nina",
            email="nina@example.com",
        )
        session.add(user)
        await session.flush()

        first = await service.start_yookassa_checkout(
            session,
            user_id=user.id,
            plan_code=SubscriptionPlan.MONTH,
            customer_email=user.email,
        )
        second = await service.start_yookassa_checkout(
            session,
            user_id=user.id,
            plan_code=SubscriptionPlan.MONTH,
            customer_email=user.email,
        )
        await session.commit()

        assert first.payment_id == second.payment_id
        assert len(stub_yookassa.create_calls) == 1


def test_yookassa_receipt_is_built_with_customer_email(test_settings) -> None:
    settings = test_settings.model_copy(
        update={
            "yookassa_enable_receipts": True,
            "yookassa_receipt_default_email": None,
        }
    )
    service = YooKassaService(settings)
    plan = SubscriptionService(settings).get_plan(SubscriptionPlan.MONTH)

    receipt = service._build_receipt(plan=plan, customer_email="receipt@example.com")

    assert receipt is not None
    assert receipt["customer"]["email"] == "receipt@example.com"
    assert receipt["items"][0]["payment_subject"] == "service"


@pytest.mark.asyncio
async def test_mock_yookassa_checkout_and_confirmation_work_without_keys(
    db_session_factory,
    test_settings,
) -> None:
    service = PaymentApplicationService(
        settings=test_settings,
        yookassa=YooKassaService(test_settings),
        subscriptions=SubscriptionService(test_settings),
    )

    async with db_session_factory() as session:
        user = User(
            platform=Platform.TELEGRAM,
            platform_user_id="99",
            username="mom99",
            first_name="Lena",
        )
        session.add(user)
        await session.flush()

        checkout = await service.start_yookassa_checkout(
            session,
            user_id=user.id,
            plan_code=SubscriptionPlan.MONTH,
            customer_email=None,
        )
        subscription = await service.confirm_mock_payment(
            session, provider_payment_id=checkout.payment_id
        )
        await session.commit()

        payment = await PaymentRepository(session).get_by_provider_payment_id(
            checkout.payment_id
        )

        assert checkout.payment_url.startswith("mock://payment/")
        assert payment is not None
        assert payment.status == PaymentStatus.SUCCEEDED
        assert (
            payment.payment_method_id == f"mock_pm_{user.id}_{SubscriptionPlan.MONTH}"
        )
        assert subscription is not None
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.auto_renew is True
