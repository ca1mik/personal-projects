from __future__ import annotations

from aiogram.types import LabeledPrice

from src.config.settings import Settings
from src.models import SubscriptionPlan
from src.services.subscriptions.plans import PlanDefinition


class TelegramInvoiceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return bool(self.settings.telegram_provider_token)

    def build_invoice(self, plan: PlanDefinition) -> dict:
        return {
            "title": plan.title,
            "description": f"{plan.description}. Telegram-оплата используется как fallback-сценарий.",
            "payload": f"subscription:{plan.code}",
            "provider_token": self.settings.telegram_provider_token,
            "currency": "RUB",
            "prices": [LabeledPrice(label=plan.title, amount=int(plan.amount * 100))],
            "need_name": False,
            "need_email": False,
            "need_phone_number": False,
            "is_flexible": False,
        }

    @staticmethod
    def parse_payload(payload: str) -> SubscriptionPlan:
        _, plan = payload.split(":", maxsplit=1)
        return SubscriptionPlan(plan)
