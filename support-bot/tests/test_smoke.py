from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.config import Settings
from src.services.documents import DocumentService
from src.services.llm import LLMMessage, build_llm_service


def test_healthcheck_legal_admin_and_demo_routes(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'smoke.db'}",
        yookassa_enable_receipts=False,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        privacy = client.get("/legal/privacy_policy.md")
        assert privacy.status_code == 200
        assert "Политика конфиденциальности" in privacy.text

        admin = client.get("/admin/audit-events")
        assert admin.status_code == 401

        demo_info = client.get("/demo")
        assert demo_info.status_code == 200
        assert demo_info.json()["enabled"] is True


def test_demo_endpoint_supports_local_flow(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'demo.db'}",
        yookassa_enable_receipts=False,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        start = client.post(
            "/demo/events",
            json={"platform_user_id": "demo-1", "command": "/start"},
        )
        assert start.status_code == 200
        assert "эмоциональной поддержки" in start.json()["messages"][0]["text"]

        for action in (
            "start:free",
            "adult:yes",
            "consent:privacy:accept",
            "consent:offer:accept",
            "consent:disclaimer:accept",
            "checkin:no",
        ):
            response = client.post(
                "/demo/events",
                json={"platform_user_id": "demo-1", "action": action},
            )
            assert response.status_code == 200

        for text in ("Первое сообщение", "Второе сообщение", "Третье сообщение"):
            reply = client.post(
                "/demo/events",
                json={"platform_user_id": "demo-1", "text": text},
            )
            assert reply.status_code == 200

        paywall = reply.json()["messages"][-1]
        assert paywall["buttons"][0][0]["action"] == "pay:yookassa:week"

        checkout = client.post(
            "/demo/events",
            json={"platform_user_id": "demo-1", "action": "pay:yookassa:month"},
        )
        assert checkout.status_code == 200
        assert checkout.json()["messages"][0]["buttons"][0][0]["action"].startswith(
            "pay:mock:confirm:"
        )


@pytest.mark.asyncio
async def test_mock_llm_provider_returns_reply(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        llm_provider="mock",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'mock.db'}",
        yookassa_enable_receipts=False,
    )
    documents = DocumentService(
        settings, project_root=Path(__file__).resolve().parents[1]
    )
    llm = build_llm_service(settings, documents)

    reply = await llm.generate_reply(
        summary=None, messages=[LLMMessage(role="user", content="Мне трудно")]
    )
    await llm.close()

    assert "Слышу, что тебе сейчас непросто" in reply
