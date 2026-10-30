from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.admin import router as admin_router
from src.api.demo import router as demo_router
from src.api.webhooks import (
    max_webhook_router,
    payments_webhook_router,
    telegram_webhook_router,
)
from src.config import Settings, get_settings
from src.services.container import build_container


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    project_root = Path(__file__).resolve().parents[2]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = build_container(resolved_settings)
        app.state.container = container
        await container.startup()
        try:
            yield
        finally:
            await container.shutdown()

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    app.mount("/legal", StaticFiles(directory=project_root / "legal"), name="legal")

    @app.get("/health")
    async def healthcheck() -> dict:
        return {"status": "ok"}

    app.include_router(telegram_webhook_router)
    app.include_router(max_webhook_router)
    app.include_router(payments_webhook_router)
    if resolved_settings.effective_admin_api_token:
        app.include_router(admin_router)
    if not resolved_settings.is_production:
        app.include_router(demo_router)
    return app
