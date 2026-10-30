from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.dependencies import get_container
from src.bot.max import MaxUpdate
from src.services.container import AppContainer

router = APIRouter(tags=["max"])


@router.post("/webhooks/max")
async def max_webhook(
    update: MaxUpdate,
    container: AppContainer = Depends(get_container),
    x_max_bot_api_secret: str | None = Header(default=None),
) -> dict:
    if (
        container.settings.max_webhook_secret
        and x_max_bot_api_secret != container.settings.max_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid MAX webhook secret")
    await container.max_handler.handle(update)
    return {"ok": True}
