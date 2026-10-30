from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.bot.max import MaxClient, MaxGateway
from src.bot.telegram import TelegramBotRuntime
from src.config.logging import configure_logging
from src.config.settings import Settings
from src.database import Base, create_session_factory
from src.handlers import MaxWebhookHandler
from src.services.crisis import CrisisService
from src.services.documents import DocumentService
from src.services.llm import LLMService, build_llm_service
from src.services.notifications import NotificationService
from src.services.onboarding import OnboardingService
from src.services.payments import (
    PaymentApplicationService,
    TelegramInvoiceService,
    YooKassaService,
)
from src.services.subscriptions import SubscriptionService
from src.services.workflow import SupportBotWorkflow


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    documents: DocumentService
    llm: LLMService
    crisis: CrisisService
    onboarding: OnboardingService
    subscriptions: SubscriptionService
    yookassa: YooKassaService
    telegram_invoice: TelegramInvoiceService
    payments: PaymentApplicationService
    notifications: NotificationService
    workflow: SupportBotWorkflow
    telegram_runtime: TelegramBotRuntime
    max_client: MaxClient
    max_gateway: MaxGateway
    max_handler: MaxWebhookHandler

    async def startup(self) -> None:
        if not self.settings.is_production and self.settings.database_url.startswith(
            "sqlite"
        ):
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        await self.telegram_runtime.configure_webhook()
        await self.max_client.configure_webhook()

    async def shutdown(self) -> None:
        await self.telegram_runtime.close()
        await self.max_client.close()
        await self.llm.close()
        await self.engine.dispose()


def build_container(settings: Settings) -> AppContainer:
    configure_logging(settings)
    settings.validate_runtime()
    engine, session_factory = create_session_factory(settings)
    documents = DocumentService(settings)
    llm = build_llm_service(settings, documents)
    crisis = CrisisService()
    onboarding = OnboardingService()
    subscriptions = SubscriptionService(settings)
    yookassa = YooKassaService(settings)
    telegram_invoice = TelegramInvoiceService(settings)
    payments = PaymentApplicationService(
        settings=settings, yookassa=yookassa, subscriptions=subscriptions
    )
    notifications = NotificationService(settings=settings)
    workflow = SupportBotWorkflow(
        settings=settings,
        session_factory=session_factory,
        documents=documents,
        onboarding=onboarding,
        crisis=crisis,
        llm=llm,
        subscriptions=subscriptions,
        payments=payments,
        notifications=notifications,
    )
    telegram_runtime = TelegramBotRuntime(
        settings=settings,
        workflow=workflow,
        payment_service=payments,
        invoice_service=telegram_invoice,
    )
    max_client = MaxClient(settings)
    max_gateway = MaxGateway(max_client)
    notifications.telegram_gateway = telegram_runtime.gateway
    notifications.max_gateway = max_gateway
    max_handler = MaxWebhookHandler(
        workflow=workflow, gateway=max_gateway, client=max_client
    )
    return AppContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        documents=documents,
        llm=llm,
        crisis=crisis,
        onboarding=onboarding,
        subscriptions=subscriptions,
        yookassa=yookassa,
        telegram_invoice=telegram_invoice,
        payments=payments,
        notifications=notifications,
        workflow=workflow,
        telegram_runtime=telegram_runtime,
        max_client=max_client,
        max_gateway=max_gateway,
        max_handler=max_handler,
    )
