from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings
from src.models import (
    PaymentProvider,
    PaymentStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from src.repositories import (
    AuditEventRepository,
    PaymentRepository,
    SubscriptionRepository,
    UserRepository,
)
from src.services.payments.yookassa_service import CheckoutResult
from src.services.subscriptions import SubscriptionService
from src.services.utils import utcnow

logger = logging.getLogger(__name__)


class YooKassaGateway(Protocol):
    def create_payment(
        self,
        *,
        user_id: int,
        plan,
        description: str,
        customer_email: str | None,
        idempotence_key: str | None = None,
    ) -> CheckoutResult: ...

    def charge_saved_payment_method(
        self,
        *,
        user_id: int,
        payment_method_id: str,
        plan,
        customer_email: str | None,
        idempotence_key: str | None = None,
    ) -> dict[str, Any]: ...

    @staticmethod
    def map_status(status: str) -> str: ...

    @staticmethod
    def extract_payment_method_id(payment_object: dict[str, Any]) -> str | None: ...

    @staticmethod
    def extract_amount(payment_object: dict[str, Any]) -> Decimal: ...

    @staticmethod
    def extract_error_message(payment_object: dict[str, Any]) -> str | None: ...


class PaymentApplicationService:
    def __init__(
        self,
        *,
        settings: Settings,
        yookassa: YooKassaGateway,
        subscriptions: SubscriptionService,
    ) -> None:
        self.settings = settings
        self.yookassa = yookassa
        self.subscriptions = subscriptions

    async def start_yookassa_checkout(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        plan_code: SubscriptionPlan | str,
        customer_email: str | None,
    ) -> CheckoutResult:
        plan = self.subscriptions.get_plan(plan_code)
        payments = PaymentRepository(session)
        audits = AuditEventRepository(session)

        existing = await payments.get_pending_checkout(user_id, plan.code)
        if existing and existing.provider_payment_id and existing.confirmation_url:
            return CheckoutResult(
                payment_id=existing.provider_payment_id,
                payment_url=existing.confirmation_url,
                status=existing.status,
                idempotence_key=existing.idempotence_key or "",
            )

        result = self.yookassa.create_payment(
            user_id=user_id,
            plan=plan,
            description=f"{plan.title} для бота поддержки",
            customer_email=customer_email,
        )
        await payments.create_pending(
            user_id=user_id,
            provider=PaymentProvider.YOOKASSA,
            plan=plan.code,
            amount=plan.amount,
            currency="RUB",
            provider_payment_id=result.payment_id,
            idempotence_key=result.idempotence_key,
            confirmation_url=result.payment_url,
            description=plan.description,
        )
        await audits.create(
            user_id=user_id,
            category="payments",
            action="checkout_created",
            payload={
                "provider": "yookassa",
                "plan": plan.code,
                "payment_id": result.payment_id,
            },
        )
        logger.info(
            "payment.created provider=yookassa user_id=%s plan=%s payment_id=%s",
            user_id,
            plan.code,
            result.payment_id,
        )
        return result

    async def handle_yookassa_webhook(
        self, session: AsyncSession, payload: dict[str, Any]
    ) -> bool:
        payment_object = payload.get("object", {})
        provider_payment_id = payment_object.get("id")
        if not provider_payment_id:
            return False

        payments = PaymentRepository(session)
        subscriptions = SubscriptionRepository(session)
        users = UserRepository(session)
        audits = AuditEventRepository(session)

        payment = await payments.get_by_provider_payment_id(provider_payment_id)

        metadata = payment_object.get("metadata", {})
        user_id = int(metadata.get("user_id", payment.user_id if payment else 0))
        plan_code = metadata.get("plan", payment.plan if payment else None)
        if not user_id or not plan_code:
            logger.warning(
                "payment.webhook.skipped missing metadata payment_id=%s",
                provider_payment_id,
            )
            return False

        if payment is None:
            payment = await payments.create_pending(
                user_id=user_id,
                provider=PaymentProvider.YOOKASSA,
                plan=plan_code,
                amount=self.yookassa.extract_amount(payment_object),
                currency=payment_object["amount"]["currency"],
                provider_payment_id=provider_payment_id,
                description=self.subscriptions.get_plan(plan_code).description,
            )

        previous_status = payment.status
        payment.status = self.yookassa.map_status(
            payment_object.get("status", "failed")
        )
        payment.payment_method_id = (
            self.yookassa.extract_payment_method_id(payment_object)
            or payment.payment_method_id
        )
        payment.error_message = self.yookassa.extract_error_message(payment_object)

        if (
            payment.status == PaymentStatus.SUCCEEDED
            and previous_status != PaymentStatus.SUCCEEDED
        ):
            await self.subscriptions.activate_from_payment(
                subscriptions,
                user_id=user_id,
                plan_code=plan_code,
                payment_method_id=payment.payment_method_id,
            )
            user = await users.get_by_id(user_id)
            if user:
                self._mark_preview_exhausted(user)
            await audits.create(
                user_id=user_id,
                category="payments",
                action="payment_succeeded",
                payload={
                    "provider": "yookassa",
                    "plan": plan_code,
                    "payment_id": provider_payment_id,
                },
            )
            logger.info(
                "payment.succeeded provider=yookassa user_id=%s plan=%s payment_id=%s",
                user_id,
                plan_code,
                provider_payment_id,
            )
        elif payment.status in {PaymentStatus.CANCELED, PaymentStatus.FAILED}:
            await audits.create(
                user_id=user_id,
                category="payments",
                action="payment_failed",
                payload={
                    "provider": "yookassa",
                    "plan": plan_code,
                    "payment_id": provider_payment_id,
                    "status": payment.status,
                    "error": payment.error_message,
                },
            )
        return True

    async def confirm_mock_payment(
        self, session: AsyncSession, *, provider_payment_id: str
    ) -> Subscription | None:
        payments = PaymentRepository(session)
        subscriptions = SubscriptionRepository(session)
        users = UserRepository(session)
        audits = AuditEventRepository(session)

        payment = await payments.get_by_provider_payment_id(provider_payment_id)
        if payment is None:
            return None
        if payment.status == PaymentStatus.SUCCEEDED:
            return await subscriptions.get_latest_for_user(payment.user_id)

        plan_code = payment.plan or SubscriptionPlan.MONTH
        plan = self.subscriptions.get_plan(plan_code)
        payment.status = PaymentStatus.SUCCEEDED
        if plan.auto_renew and not payment.payment_method_id:
            payment.payment_method_id = f"mock_pm_{payment.user_id}_{plan.code}"

        subscription = await self.subscriptions.activate_from_payment(
            subscriptions,
            user_id=payment.user_id,
            plan_code=plan.code,
            payment_method_id=payment.payment_method_id,
        )
        user = await users.get_by_id(payment.user_id)
        if user:
            self._mark_preview_exhausted(user)

        provider_name = (
            "yookassa_mock" if self.settings.use_mock_yookassa else "yookassa"
        )
        await audits.create(
            user_id=payment.user_id,
            category="payments",
            action="payment_succeeded",
            payload={
                "provider": provider_name,
                "plan": str(plan.code),
                "payment_id": provider_payment_id,
            },
        )
        logger.info(
            "payment.succeeded provider=%s user_id=%s plan=%s payment_id=%s",
            provider_name,
            payment.user_id,
            plan.code,
            provider_payment_id,
        )
        return subscription

    async def apply_telegram_success(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        plan_code: SubscriptionPlan | str,
        provider_payment_id: str,
        amount_rub: Decimal,
    ) -> None:
        payments = PaymentRepository(session)
        subscriptions = SubscriptionRepository(session)
        users = UserRepository(session)
        audits = AuditEventRepository(session)

        payment = await payments.get_by_provider_payment_id(provider_payment_id)
        if payment is None:
            payment = await payments.create_pending(
                user_id=user_id,
                provider=PaymentProvider.TELEGRAM,
                plan=plan_code,
                amount=amount_rub,
                currency="RUB",
                provider_payment_id=provider_payment_id,
                description=self.subscriptions.get_plan(plan_code).description,
            )
        if payment.status == PaymentStatus.SUCCEEDED:
            return

        payment.status = PaymentStatus.SUCCEEDED
        await self.subscriptions.activate_from_payment(
            subscriptions,
            user_id=user_id,
            plan_code=plan_code,
            force_auto_renew=False,
        )
        user = await users.get_by_id(user_id)
        if user:
            self._mark_preview_exhausted(user)
        await audits.create(
            user_id=user_id,
            category="payments",
            action="payment_succeeded",
            payload={
                "provider": "telegram",
                "plan": str(plan_code),
                "payment_id": provider_payment_id,
            },
        )
        logger.info(
            "payment.succeeded provider=telegram user_id=%s plan=%s payment_id=%s",
            user_id,
            plan_code,
            provider_payment_id,
        )

    async def renew_due_subscriptions(self, session: AsyncSession) -> list[int]:
        repository = SubscriptionRepository(session)
        due_subscriptions = await repository.list_due_for_renewal(utcnow())
        users = UserRepository(session)
        payments = PaymentRepository(session)
        audits = AuditEventRepository(session)
        renewed_user_ids: list[int] = []
        for subscription in due_subscriptions:
            plan = self.subscriptions.get_plan(subscription.plan)
            user = await users.get_by_id(subscription.user_id)
            try:
                response = self.yookassa.charge_saved_payment_method(
                    user_id=subscription.user_id,
                    payment_method_id=subscription.payment_method_id or "",
                    plan=plan,
                    customer_email=user.email if user else None,
                )
            except Exception as exc:  # pragma: no cover - provider/network branch
                subscription.status = SubscriptionStatus.PAST_DUE
                await audits.create(
                    user_id=subscription.user_id,
                    category="subscriptions",
                    action="renewal_failed",
                    payload={"plan": plan.code, "error": str(exc)},
                )
                logger.exception(
                    "subscription.renewal_failed user_id=%s error=%s",
                    subscription.user_id,
                    exc,
                )
                continue

            payment_id = response["id"]
            payment_status = self.yookassa.map_status(response["status"])
            payment = await payments.create_pending(
                user_id=subscription.user_id,
                provider=PaymentProvider.YOOKASSA,
                plan=plan.code,
                amount=Decimal(str(response["amount"]["value"])),
                currency=response["amount"]["currency"],
                provider_payment_id=payment_id,
                payment_method_id=subscription.payment_method_id,
                description=plan.description,
                is_recurrent=True,
            )
            payment.status = payment_status
            payment.error_message = self.yookassa.extract_error_message(response)
            if payment_status == PaymentStatus.SUCCEEDED:
                await self.subscriptions.activate_from_payment(
                    repository,
                    user_id=subscription.user_id,
                    plan_code=plan.code,
                    payment_method_id=subscription.payment_method_id,
                )
                renewed_user_ids.append(subscription.user_id)
                await audits.create(
                    user_id=subscription.user_id,
                    category="subscriptions",
                    action="renewal_succeeded",
                    payload={"plan": plan.code, "payment_id": payment_id},
                )
            else:
                subscription.status = SubscriptionStatus.PAST_DUE
                await audits.create(
                    user_id=subscription.user_id,
                    category="subscriptions",
                    action="renewal_failed",
                    payload={
                        "plan": plan.code,
                        "payment_id": payment_id,
                        "status": payment_status,
                    },
                )
        return renewed_user_ids

    def _mark_preview_exhausted(self, user) -> None:
        user.preview_exhausted = True
        user.free_preview_messages_used = max(
            user.free_preview_messages_used, self.settings.preview_user_messages
        )
        user.preview_completed_at = user.preview_completed_at or utcnow()
