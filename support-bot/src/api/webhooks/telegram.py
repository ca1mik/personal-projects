from __future__ import annotations

from aiogram.types import Update
from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import get_container
from src.services.container import AppContainer

router = APIRouter(tags=["telegram"])


@router.post("/webhooks/telegram")
async def telegram_webhook(
    request: Request, container: AppContainer = Depends(get_container)
) -> dict:
    runtime = container.telegram_runtime
    if not runtime.bot:
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")

    payload = await request.json()
    update = Update.model_validate(payload, context={"bot": runtime.bot})
    await runtime.dispatcher.feed_webhook_update(runtime.bot, update)
    return {"ok": True}
