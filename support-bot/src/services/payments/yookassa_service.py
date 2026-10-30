from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import uuid4

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

try:  # pragma: no cover - import guard for local test environments
    from yookassa import Configuration
    from yookassa import Payment as YooKassaPayment
except (
    ModuleNotFoundError
):  # pragma: no cover - handled at runtime when SDK is required
    Configuration = None
    YooKassaPayment = None

from src.config.settings import Settings
from src.services.subscriptions.plans import PlanDefinition


@dataclass(slots=True, frozen=True)
class CheckoutResult:
    payment_id: str
    payment_url: str
    status: str
    idempotence_key: str


class YooKassaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if Configuration and settings.yookassa_shop_id and settings.yookassa_secret_key:
            Configuration.account_id = settings.yookassa_shop_id
            Configuration.secret_key = settings.yookassa_secret_key

    def is_configured(self) -> bool:
        return bool(
            Configuration
            and YooKassaPayment
            and self.settings.yookassa_shop_id
            and self.settings.yookassa_secret_key
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def create_payment(
        self,
        *,
        user_id: int,
        plan: PlanDefinition,
        description: str,
        customer_email: str | None,
        idempotence_key: str | None = None,
    ) -> CheckoutResult:
        request_id = idempotence_key or uuid4().hex
        if self.settings.use_mock_yookassa:
            return CheckoutResult(
                payment_id=request_id,
                payment_url=f"mock://payment/{request_id}",
                status="pending",
                idempotence_key=request_id,
            )
        if not self.is_configured():
            raise RuntimeError("YooKassa is not configured")

        payload: dict[str, Any] = {
            "amount": {"value": f"{plan.amount:.2f}", "currency": "RUB"},
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": self.settings.yookassa_return_url,
            },
            "description": description[:128],
            "save_payment_method": plan.auto_renew,
            "metadata": {
                "user_id": str(user_id),
                "plan": plan.code,
            },
        }
        receipt = self._build_receipt(plan=plan, customer_email=customer_email)
        if receipt:
            payload["receipt"] = receipt
        payment = YooKassaPayment.create(payload, request_id)
        confirmation = getattr(payment, "confirmation", None)
        payment_url = getattr(confirmation, "confirmation_url", None)
        if not payment_url:
            raise RuntimeError("YooKassa did not return confirmation URL")
        return CheckoutResult(
            payment_id=payment.id,
            payment_url=payment_url,
            status=payment.status,
            idempotence_key=request_id,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def charge_saved_payment_method(
        self,
        *,
        user_id: int,
        payment_method_id: str,
        plan: PlanDefinition,
        customer_email: str | None,
        idempotence_key: str | None = None,
    ) -> dict[str, Any]:
        request_id = idempotence_key or uuid4().hex
        if self.settings.use_mock_yookassa:
            return {
                "id": request_id,
                "status": "succeeded",
                "amount": {"value": f"{plan.amount:.2f}", "currency": "RUB"},
                "payment_method": {"id": payment_method_id},
                "metadata": {
                    "user_id": str(user_id),
                    "plan": str(plan.code),
                    "renewal": "true",
                },
            }
        if not self.is_configured():
            raise RuntimeError("YooKassa is not configured")

        payload: dict[str, Any] = {
            "amount": {"value": f"{plan.amount:.2f}", "currency": "RUB"},
            "capture": True,
            "payment_method_id": payment_method_id,
            "description": f"{plan.title} для пользователя {user_id}"[:128],
            "metadata": {
                "user_id": str(user_id),
                "plan": plan.code,
                "renewal": "true",
            },
        }
        receipt = self._build_receipt(plan=plan, customer_email=customer_email)
        if receipt:
            payload["receipt"] = receipt
        payment = YooKassaPayment.create(payload, request_id)
        return payment.json()

    def _build_receipt(
        self, *, plan: PlanDefinition, customer_email: str | None
    ) -> dict[str, Any] | None:
        if not self.settings.yookassa_enable_receipts:
            return None

        email = customer_email or self.settings.yookassa_receipt_default_email
        if not email:
            raise RuntimeError("Receipt email is required for YooKassa receipts")

        receipt: dict[str, Any] = {
            "customer": {"email": email},
            "items": [
                {
                    "description": plan.title[:128],
                    "quantity": "1.00",
                    "amount": {"value": f"{plan.amount:.2f}", "currency": "RUB"},
                    "vat_code": self.settings.yookassa_receipt_vat_code,
                    "payment_mode": "full_payment",
                    "payment_subject": "service",
                }
            ],
        }
        if self.settings.yookassa_receipt_tax_system_code is not None:
            receipt["tax_system_code"] = self.settings.yookassa_receipt_tax_system_code
        return receipt

    @staticmethod
    def map_status(status: str) -> str:
        mapping = {
            "pending": "pending",
            "succeeded": "succeeded",
            "canceled": "canceled",
            "waiting_for_capture": "pending",
        }
        return mapping.get(status, "failed")

    @staticmethod
    def extract_payment_method_id(payment_object: dict[str, Any]) -> str | None:
        return payment_object.get("payment_method", {}).get("id")

    @staticmethod
    def extract_amount(payment_object: dict[str, Any]) -> Decimal:
        return Decimal(str(payment_object["amount"]["value"]))

    @staticmethod
    def extract_error_message(payment_object: dict[str, Any]) -> str | None:
        cancellation = payment_object.get("cancellation_details") or {}
        party = cancellation.get("party")
        reason = cancellation.get("reason")
        if not party and not reason:
            return None
        return f"{party or 'unknown'}:{reason or 'unknown'}"
