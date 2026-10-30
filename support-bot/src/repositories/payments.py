from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from src.models import Payment, PaymentProvider, PaymentStatus, SubscriptionPlan
from src.repositories.base import SQLAlchemyRepository


class PaymentRepository(SQLAlchemyRepository):
    async def create_pending(
        self,
        *,
        user_id: int,
        provider: PaymentProvider | str,
        plan: SubscriptionPlan | str,
        amount: Decimal,
        currency: str,
        provider_payment_id: str | None = None,
        payment_method_id: str | None = None,
        idempotence_key: str | None = None,
        confirmation_url: str | None = None,
        description: str | None = None,
        error_message: str | None = None,
        is_recurrent: bool = False,
    ) -> Payment:
        payment = Payment(
            user_id=user_id,
            provider=str(provider),
            plan=str(plan),
            amount=amount,
            currency=currency,
            status=PaymentStatus.PENDING,
            provider_payment_id=provider_payment_id,
            payment_method_id=payment_method_id,
            idempotence_key=idempotence_key,
            confirmation_url=confirmation_url,
            description=description,
            error_message=error_message,
            is_recurrent=is_recurrent,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_by_provider_payment_id(
        self, provider_payment_id: str
    ) -> Payment | None:
        query = select(Payment).where(
            Payment.provider_payment_id == provider_payment_id
        )
        return await self.session.scalar(query)

    async def get_by_idempotence_key(self, idempotence_key: str) -> Payment | None:
        query = select(Payment).where(Payment.idempotence_key == idempotence_key)
        return await self.session.scalar(query)

    async def get_pending_checkout(
        self, user_id: int, plan: SubscriptionPlan | str
    ) -> Payment | None:
        query = (
            select(Payment)
            .where(
                Payment.user_id == user_id,
                Payment.plan == str(plan),
                Payment.provider == str(PaymentProvider.YOOKASSA),
                Payment.status == str(PaymentStatus.PENDING),
                Payment.confirmation_url.is_not(None),
            )
            .order_by(Payment.id.desc())
            .limit(1)
        )
        return await self.session.scalar(query)

    async def list_recent(self, limit: int = 100) -> list[Payment]:
        query = select(Payment).order_by(Payment.id.desc()).limit(limit)
        return list(await self.session.scalars(query))

    async def get_latest_for_user(self, user_id: int) -> Payment | None:
        query = (
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.id.desc())
            .limit(1)
        )
        return await self.session.scalar(query)
