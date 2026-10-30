from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.dependencies import get_container
from src.services.container import AppContainer

router = APIRouter(tags=["payments"])


@router.post("/webhooks/payments/yookassa")
async def yookassa_webhook(
    request: Request,
    container: AppContainer = Depends(get_container),
    secret: str | None = Query(default=None),
) -> dict:
    if (
        container.settings.yookassa_webhook_secret
        and secret != container.settings.yookassa_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid YooKassa webhook secret")
    payload = await request.json()
    async with container.session_factory() as session:
        await container.payments.handle_yookassa_webhook(session, payload)
        await session.commit()
    return {"ok": True}
