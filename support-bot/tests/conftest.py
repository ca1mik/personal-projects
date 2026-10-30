from __future__ import annotations

import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import Settings
from src.database import Base, create_session_factory
from src.services.crisis import CrisisService
from src.services.documents import DocumentService
from src.services.llm import LLMMessage, LLMService
from src.services.notifications import NotificationService
from src.services.onboarding import OnboardingService
from src.services.payments import (
    CheckoutResult,
    PaymentApplicationService,
    YooKassaService,
)
from src.services.subscriptions import SubscriptionService
from src.services.workflow import SupportBotWorkflow


class StubProvider:
    def __init__(self) -> None:
        self.generate_calls: list[dict[str, object]] = []
        self.summary_calls = 0

    async def generate(
        self, *, system_prompt: str, messages: list[LLMMessage], max_tokens: int = 350
    ) -> str:
        self.generate_calls.append(
            {
                "system_prompt": system_prompt,
                "messages": [(message.role, message.content) for message in messages],
                "max_tokens": max_tokens,
            }
        )
        if "Сожми диалог" in system_prompt:
            self.summary_calls += 1
            return "summary"
        return "reply"

    async def close(self) -> None:
        return None


class StubYooKassa:
    def __init__(self) -> None:
        self.counter = 0
        self.create_calls: list[dict[str, object]] = []
        self.charge_calls: list[dict[str, object]] = []

    def create_payment(
        self,
        *,
        user_id: int,
        plan,
        description: str,
        customer_email: str | None,
        idempotence_key: str | None = None,
    ) -> CheckoutResult:
        self.counter += 1
        self.create_calls.append(
            {
                "user_id": user_id,
                "plan_code": str(plan.code),
                "description": description,
                "customer_email": customer_email,
                "idempotence_key": idempotence_key,
            }
        )
        return CheckoutResult(
            payment_id=f"pay_{self.counter}",
            payment_url=f"https://pay.example/{self.counter}",
            status="pending",
            idempotence_key=idempotence_key or f"idem_{self.counter}",
        )

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
        self.charge_calls.append(
            {
                "user_id": user_id,
                "payment_method_id": payment_method_id,
                "plan_code": str(plan.code),
                "customer_email": customer_email,
                "idempotence_key": idempotence_key,
            }
        )
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


class RecordingNotificationService(NotificationService):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings=settings)
        self.user_messages: list[tuple[int, str]] = []
        self.admin_messages: list[str] = []

    async def send_to_user(self, user, message) -> None:
        self.user_messages.append((user.id, message.text))

    async def notify_admins(self, text: str) -> None:
        self.admin_messages.append(text)


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        yookassa_enable_receipts=False,
        admin_api_token="secret-token",
        admin_user_ids="100,101",
        privacy_policy_version="privacy-test-v1",
        offer_version="offer-test-v1",
        disclaimer_version="disclaimer-test-v1",
    )


@pytest_asyncio.fixture
async def db_session_factory(test_settings: Settings):
    engine, session_factory = create_session_factory(test_settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield session_factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def workflow(test_settings: Settings, db_session_factory):
    documents = DocumentService(
        test_settings, project_root=Path(__file__).resolve().parents[1]
    )
    provider = StubProvider()
    llm = LLMService(settings=test_settings, documents=documents, provider=provider)
    subscriptions = SubscriptionService(test_settings)
    payments = PaymentApplicationService(
        settings=test_settings,
        yookassa=YooKassaService(test_settings),
        subscriptions=subscriptions,
    )
    notifications = RecordingNotificationService(settings=test_settings)
    return SupportBotWorkflow(
        settings=test_settings,
        session_factory=db_session_factory,
        documents=documents,
        onboarding=OnboardingService(),
        crisis=CrisisService(),
        llm=llm,
        subscriptions=subscriptions,
        payments=payments,
        notifications=notifications,
    )


@pytest.fixture
def stub_provider() -> StubProvider:
    return StubProvider()


@pytest.fixture
def stub_yookassa() -> StubYooKassa:
    return StubYooKassa()


@pytest.fixture
def recording_notifications(test_settings: Settings) -> RecordingNotificationService:
    return RecordingNotificationService(settings=test_settings)
