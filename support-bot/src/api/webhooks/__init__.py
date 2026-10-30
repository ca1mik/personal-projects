from src.api.webhooks.max import router as max_webhook_router
from src.api.webhooks.payments import router as payments_webhook_router
from src.api.webhooks.telegram import router as telegram_webhook_router

__all__ = ["max_webhook_router", "payments_webhook_router", "telegram_webhook_router"]
