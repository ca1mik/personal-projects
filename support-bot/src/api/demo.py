from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.dependencies import get_container
from src.models import Platform
from src.services.container import AppContainer
from src.services.platforms import IncomingEvent

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoEventRequest(BaseModel):
    platform: Platform = Platform.TELEGRAM
    platform_user_id: str = Field(default="demo-user")
    chat_id: str | None = None
    username: str | None = "demo"
    first_name: str | None = "Demo"
    text: str | None = None
    command: str | None = None
    action: str | None = None


@router.get("")
async def demo_info(
    container: AppContainer = Depends(get_container),
) -> dict[str, Any]:
    return {
        "mode": "demo",
        "enabled": container.settings.demo_mode,
        "admin_token": container.settings.effective_admin_api_token or None,
        "message": (
            "Use POST /demo/events to walk through /start, consents, preview, "
            "mock payments, subscription flow, /minute and /diary without "
            "Telegram, MAX or YooKassa keys."
        ),
    }


@router.post("/events")
async def demo_event(
    payload: DemoEventRequest,
    container: AppContainer = Depends(get_container),
) -> dict[str, Any]:
    event = IncomingEvent(
        platform=payload.platform,
        platform_user_id=payload.platform_user_id,
        chat_id=payload.chat_id or payload.platform_user_id,
        username=payload.username,
        first_name=payload.first_name,
        text=payload.text,
        command=payload.command,
        action=payload.action,
    )
    result = await container.workflow.handle_event(event)
    return {
        "messages": [
            {
                "text": message.text,
                "parse_mode": message.parse_mode,
                "disable_link_preview": message.disable_link_preview,
                "buttons": [
                    [
                        {
                            "text": button.text,
                            "action": button.action,
                            "url": button.url,
                            "kind": button.kind,
                        }
                        for button in row
                    ]
                    for row in message.buttons
                ],
            }
            for message in result.messages
        ]
    }
