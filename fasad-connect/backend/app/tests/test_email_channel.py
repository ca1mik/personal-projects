from __future__ import annotations

import base64
import os
import uuid
from email.message import EmailMessage
from pathlib import Path

import pytest

from app.core.crypto import SECRET_PREFIX, decrypt_secret, encrypt_secret
from app.modules.messaging import email_transport
from app.modules.messaging.email_parser import html_to_text, parse_email_bytes
from app.modules.messaging.schemas import (
    ChannelHealthCheckResult,
    ChannelHealthCheckStep,
    EmailChannelConfig,
)

EMAIL_ACCOUNT_CONFIG = {
    "imap": {
        "host": "imap.example.com",
        "port": 993,
        "ssl": True,
        "login": "sales@example.com",
        "folder": "INBOX",
    },
    "smtp": {
        "host": "smtp.example.com",
        "port": 465,
        "security": "ssl",
        "login": "sales@example.com",
        "from_email": "sales@example.com",
        "from_name": "Фасад Производство",
    },
    "poll_interval_seconds": 60,
}


def build_raw_email(
    *,
    message_id: str = "<mail-001@example.com>",
    subject: str = "Запрос на шкаф-купе",
    from_header: str = "Иван Петров <ivan@example.com>",
    body: str = "Нужен шкаф 1800x2400x600, телефон +79991234567",
    html_body: str | None = None,
    attachments: list[tuple[str, str, bytes]] | None = None,
) -> bytes:
    message = EmailMessage()
    message["Message-ID"] = message_id
    message["Subject"] = subject
    message["From"] = from_header
    message["To"] = "sales@example.com"
    message["Date"] = "Mon, 03 Aug 2026 10:00:00 +0300"
    message.set_content(body, charset="utf-8")
    if html_body:
        message.add_alternative(html_body, subtype="html", charset="utf-8")
    for file_name, mime_type, content in attachments or []:
        maintype, subtype = mime_type.split("/", 1)
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=file_name)
    return message.as_bytes()


def create_email_channel(client, auth_headers, *, code: str = "email_main", **overrides):
    payload = {
        "code": code,
        "channel_type": "email",
        "name": "Почта отдела продаж",
        "inbound_mode": "polling",
        "is_active": True,
        "config_json": EMAIL_ACCOUNT_CONFIG,
        "secrets": {"imap_password": "imap-secret", "smtp_password": "smtp-secret"},
    }
    payload.update(overrides)
    response = client.post("/api/v1/messaging/channel-accounts", headers=auth_headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"]


# --- crypto ----------------------------------------------------------------


def test_secret_roundtrip_is_encrypted_at_rest():
    encrypted = encrypt_secret("хитрый-пароль")

    assert encrypted.startswith(SECRET_PREFIX)
    assert "хитрый-пароль" not in encrypted
    assert decrypt_secret(encrypted) == "хитрый-пароль"


def test_decrypt_passes_through_plaintext_and_empty_values():
    assert decrypt_secret("plain-value") == "plain-value"
    assert decrypt_secret(None) == ""
    assert decrypt_secret("") == ""


# --- parser ----------------------------------------------------------------


def test_parse_plain_cyrillic_email():
    payload = parse_email_bytes(build_raw_email())

    assert payload.message_id == "<mail-001@example.com>"
    assert payload.subject == "Запрос на шкаф-купе"
    assert payload.from_name == "Иван Петров"
    assert payload.from_email == "ivan@example.com"
    assert "1800x2400x600" in payload.body_text
    assert payload.attachments == []


def test_parse_multipart_email_with_attachment():
    raw = build_raw_email(
        message_id="<mail-002@example.com>",
        body="Во вложении эскиз",
        attachments=[("эскиз.pdf", "application/pdf", b"%PDF-1.4 fake content")],
    )

    payload = parse_email_bytes(raw)

    assert len(payload.attachments) == 1
    attachment = payload.attachments[0]
    assert attachment.file_name == "эскиз.pdf"
    assert attachment.mime_type == "application/pdf"
    assert attachment.size_bytes == len(b"%PDF-1.4 fake content")
    assert base64.b64decode(attachment.content_base64) == b"%PDF-1.4 fake content"


def test_parse_html_only_email_falls_back_to_text():
    message = EmailMessage()
    message["Message-ID"] = "<mail-html@example.com>"
    message["Subject"] = "HTML заявка"
    message["From"] = "client@example.com"
    message.set_content(
        "<html><head><style>p{color:red}</style></head>"
        "<body><p>Кухня 2000x900</p><p>Телефон +79990001122</p></body></html>",
        subtype="html",
        charset="utf-8",
    )

    payload = parse_email_bytes(message.as_bytes())

    assert "Кухня 2000x900" in payload.body_text
    assert "+79990001122" in payload.body_text
    assert "color:red" not in payload.body_text


def test_oversized_attachment_keeps_metadata_without_content():
    raw = build_raw_email(
        message_id="<mail-big@example.com>",
        attachments=[("huge.bin", "application/octet-stream", b"x" * 5000)],
    )

    payload = parse_email_bytes(raw, max_attachment_bytes=1000)

    assert payload.attachments[0].size_bytes == 5000
    assert payload.attachments[0].content_base64 is None


def test_parse_email_without_message_id_uses_fallback():
    message = EmailMessage()
    message["Subject"] = "Без Message-ID"
    message["From"] = "client@example.com"
    message.set_content("Тестовое письмо")

    payload = parse_email_bytes(message.as_bytes(), fallback_message_id="imap:email_main:42")

    assert payload.message_id == "imap:email_main:42"


def test_parse_email_with_broken_from_header_does_not_raise():
    payload = parse_email_bytes(build_raw_email(from_header="not-an-address"))

    assert payload.from_email is None
    assert payload.body_text


def test_attachment_file_name_is_stripped_of_path_traversal():
    raw = build_raw_email(
        message_id="<mail-traversal@example.com>",
        attachments=[("../../etc/passwd", "text/plain", b"root:x:0:0")],
    )

    payload = parse_email_bytes(raw)

    assert payload.attachments[0].file_name == "passwd"


def test_html_to_text_keeps_block_structure():
    text = html_to_text("<div>Первая</div><div>Вторая</div>")

    assert [line for line in text.splitlines() if line] == ["Первая", "Вторая"]


# --- channel account API ---------------------------------------------------


def test_create_email_channel_never_exposes_secrets(client, auth_headers):
    account = create_email_channel(client, auth_headers)

    assert account["configured_secrets"] == ["imap_password", "smtp_password"]
    assert "secrets_json" not in account
    assert (
        "imap-secret"
        not in client.get(
            "/api/v1/messaging/channel-accounts?page=1&size=20", headers=auth_headers
        ).text
    )


def test_update_channel_without_secrets_keeps_stored_credentials(client, auth_headers, db_session):
    from app.modules.messaging.channel_config import get_secret
    from app.modules.messaging.models import ChannelAccount

    account = create_email_channel(client, auth_headers, code="email_keep")

    response = client.patch(
        f"/api/v1/messaging/channel-accounts/{account['id']}",
        headers=auth_headers,
        json={"name": "Почта продаж (обновлено)"},
    )

    assert response.status_code == 200
    stored = db_session.get(ChannelAccount, uuid.UUID(account["id"]))
    db_session.refresh(stored)
    assert get_secret(stored, "imap_password") == "imap-secret"


def test_health_check_reports_per_transport_status(client, auth_headers, monkeypatch):
    account = create_email_channel(client, auth_headers, code="email_health")

    def fake_check(config, *, imap_password, smtp_password):
        assert imap_password == "imap-secret"
        assert smtp_password == "smtp-secret"
        return ChannelHealthCheckResult(
            ok=False,
            imap=ChannelHealthCheckStep(ok=True, detail="Подключение к папке INBOX успешно"),
            smtp=ChannelHealthCheckStep(ok=False, detail="Ошибка SMTP: auth failed"),
        )

    monkeypatch.setattr(email_transport, "check_connection", fake_check)

    response = client.post(
        f"/api/v1/messaging/channel-accounts/{account['id']}/health-check",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["ok"] is False
    assert data["imap"]["ok"] is True
    assert data["smtp"]["ok"] is False

    listed = client.get(
        "/api/v1/messaging/channel-accounts?page=1&size=20", headers=auth_headers
    ).json()["data"]
    stored = next(item for item in listed if item["id"] == account["id"])
    assert "auth failed" in stored["last_error"]


def test_health_check_rejects_non_email_channel(client, auth_headers):
    response = client.post(
        "/api/v1/messaging/channel-accounts",
        headers=auth_headers,
        json={
            "code": "webhook_partner",
            "channel_type": "webhook",
            "name": "Партнёрский вебхук",
        },
    )
    account_id = response.json()["data"]["id"]

    health = client.post(
        f"/api/v1/messaging/channel-accounts/{account_id}/health-check",
        headers=auth_headers,
    )

    assert health.status_code == 400
    assert "не является email" in health.json()["error"]["message"]


def test_health_check_requires_existing_account(client, auth_headers):
    response = client.post(
        "/api/v1/messaging/channel-accounts/00000000-0000-0000-0000-000000000000/health-check",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_poll_requires_channels_manage_permission(client, auth_headers, operator_auth_headers):
    account = create_email_channel(client, auth_headers, code="email_rbac")

    response = client.post(
        f"/api/v1/messaging/channel-accounts/{account['id']}/poll",
        headers=operator_auth_headers,
    )

    # 403, а не 401: человек вошёл, просто настройка каналов не его работа.
    assert response.status_code == 403


# --- polling ---------------------------------------------------------------


def test_poll_creates_lead_conversation_and_attachment(client, auth_headers, monkeypatch):
    account = create_email_channel(client, auth_headers, code="email_poll")

    monkeypatch.setattr(
        email_transport,
        "fetch_messages",
        lambda config, password, *, limit: [
            email_transport.FetchedEmail(
                uid="11",
                raw=build_raw_email(
                    attachments=[("эскиз.pdf", "application/pdf", b"%PDF-1.4 sketch")]
                ),
            )
        ],
    )

    response = client.post(
        f"/api/v1/messaging/channel-accounts/{account['id']}/poll", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["created"] == 1

    conversations = client.get(
        "/api/v1/messaging/conversations?page=1&size=20", headers=auth_headers
    ).json()["data"]
    assert len(conversations) == 1
    assert conversations[0]["channel_account"]["channel_type"] == "email"
    assert conversations[0]["participant_email"] == "ivan@example.com"

    detail = client.get(
        f"/api/v1/messaging/conversations/{conversations[0]['id']}", headers=auth_headers
    ).json()["data"]
    assert detail["messages"][0]["external_message_id"] == "<mail-001@example.com>"
    assert detail["messages"][0]["attachments"][0]["file_name"] == "эскиз.pdf"


def test_poll_deduplicates_by_message_id(client, auth_headers, monkeypatch):
    account = create_email_channel(client, auth_headers, code="email_dedupe")

    monkeypatch.setattr(
        email_transport,
        "fetch_messages",
        lambda config, password, *, limit: [
            email_transport.FetchedEmail(uid="11", raw=build_raw_email())
        ],
    )

    first = client.post(
        f"/api/v1/messaging/channel-accounts/{account['id']}/poll", headers=auth_headers
    ).json()["data"]
    second = client.post(
        f"/api/v1/messaging/channel-accounts/{account['id']}/poll", headers=auth_headers
    ).json()["data"]

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["skipped"] == 1

    conversations = client.get(
        "/api/v1/messaging/conversations?page=1&size=20", headers=auth_headers
    ).json()["data"]
    detail = client.get(
        f"/api/v1/messaging/conversations/{conversations[0]['id']}", headers=auth_headers
    ).json()["data"]
    assert len(detail["messages"]) == 1


def test_poll_attaches_conversation_to_the_polling_account(client, auth_headers, monkeypatch):
    """With two mailboxes, mail must land on the account that fetched it."""
    first = create_email_channel(client, auth_headers, code="email_first")
    second = create_email_channel(client, auth_headers, code="email_second")

    monkeypatch.setattr(
        email_transport,
        "fetch_messages",
        lambda config, password, *, limit: [
            email_transport.FetchedEmail(uid="7", raw=build_raw_email())
        ],
    )

    client.post(f"/api/v1/messaging/channel-accounts/{second['id']}/poll", headers=auth_headers)

    conversations = client.get(
        "/api/v1/messaging/conversations?page=1&size=20", headers=auth_headers
    ).json()["data"]

    assert len(conversations) == 1
    assert conversations[0]["channel_account"]["code"] == "email_second"
    assert conversations[0]["channel_account_id"] == second["id"]
    assert conversations[0]["channel_account_id"] != first["id"]


def test_poll_records_transport_failure_without_raising(client, auth_headers, monkeypatch):
    account = create_email_channel(client, auth_headers, code="email_fail")

    def explode(config, password, *, limit):
        raise OSError("imap unreachable")

    monkeypatch.setattr(email_transport, "fetch_messages", explode)

    response = client.post(
        f"/api/v1/messaging/channel-accounts/{account['id']}/poll", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["error"] == "imap unreachable"

    listed = client.get(
        "/api/v1/messaging/channel-accounts?page=1&size=20", headers=auth_headers
    ).json()["data"]
    stored = next(item for item in listed if item["id"] == account["id"])
    assert stored["last_error"] == "imap unreachable"
    assert stored["next_poll_at"] is not None


def test_poll_without_imap_password_is_rejected(client, auth_headers):
    account = create_email_channel(
        client, auth_headers, code="email_nopass", secrets={"smtp_password": "smtp-secret"}
    )

    response = client.post(
        f"/api/v1/messaging/channel-accounts/{account['id']}/poll", headers=auth_headers
    )

    assert response.status_code == 400
    assert "пароль IMAP" in response.json()["error"]["message"]


def test_poll_rejects_account_without_imap_host(client, auth_headers):
    account = create_email_channel(
        client,
        auth_headers,
        code="email_nohost",
        config_json={"smtp": EMAIL_ACCOUNT_CONFIG["smtp"]},
    )

    response = client.post(
        f"/api/v1/messaging/channel-accounts/{account['id']}/poll", headers=auth_headers
    )

    assert response.status_code == 400
    assert "IMAP host" in response.json()["error"]["message"]


def test_one_broken_message_does_not_block_the_batch(client, auth_headers, monkeypatch):
    account = create_email_channel(client, auth_headers, code="email_partial")

    monkeypatch.setattr(
        email_transport,
        "fetch_messages",
        lambda config, password, *, limit: [
            email_transport.FetchedEmail(uid="1", raw=b"this is not a valid mime message at all"),
            email_transport.FetchedEmail(
                uid="2", raw=build_raw_email(message_id="<mail-ok@example.com>")
            ),
        ],
    )

    result = client.post(
        f"/api/v1/messaging/channel-accounts/{account['id']}/poll", headers=auth_headers
    ).json()["data"]

    # The malformed blob has no Message-ID and no sender, so it is skipped by the
    # fallback id rule only if parsing fails; either way the valid mail lands.
    assert result["fetched"] == 2
    assert result["created"] >= 1


# --- outbound --------------------------------------------------------------


def test_reply_over_configured_smtp_sends_and_marks_message_sent(client, auth_headers, monkeypatch):
    account = create_email_channel(client, auth_headers, code="email_send")
    sent: dict[str, object] = {}

    monkeypatch.setattr(
        email_transport,
        "fetch_messages",
        lambda config, password, *, limit: [
            email_transport.FetchedEmail(uid="11", raw=build_raw_email())
        ],
    )

    def fake_send(config, password, *, to_email, subject, body_text, in_reply_to=None):
        sent.update(
            {
                "to": to_email,
                "subject": subject,
                "body": body_text,
                "in_reply_to": in_reply_to,
                "password": password,
            }
        )
        return "<outbound-1@example.com>"

    monkeypatch.setattr(email_transport, "send_message", fake_send)

    client.post(f"/api/v1/messaging/channel-accounts/{account['id']}/poll", headers=auth_headers)
    conversations = client.get(
        "/api/v1/messaging/conversations?page=1&size=20", headers=auth_headers
    ).json()["data"]

    reply = client.post(
        f"/api/v1/messaging/conversations/{conversations[0]['id']}/messages",
        headers=auth_headers,
        json={"body_text": "Здравствуйте! Подготовили расчёт, отправляем во вложении."},
    )

    assert reply.status_code == 200
    data = reply.json()["data"]
    assert data["status"] == "waiting_client"
    assert data["messages"][-1]["status"] == "sent"
    assert data["messages"][-1]["external_message_id"] == "<outbound-1@example.com>"
    assert data["messages"][-1]["delivered_at"] is not None

    assert sent["to"] == "ivan@example.com"
    assert sent["subject"] == "Re: Запрос на шкаф-купе"
    assert sent["in_reply_to"] == "<mail-001@example.com>"
    assert sent["password"] == "smtp-secret"


def test_smtp_failure_persists_failed_message_and_returns_error(client, auth_headers, monkeypatch):
    account = create_email_channel(client, auth_headers, code="email_send_fail")

    monkeypatch.setattr(
        email_transport,
        "fetch_messages",
        lambda config, password, *, limit: [
            email_transport.FetchedEmail(uid="11", raw=build_raw_email())
        ],
    )

    def explode(config, password, **kwargs):
        raise OSError("smtp refused connection")

    monkeypatch.setattr(email_transport, "send_message", explode)

    client.post(f"/api/v1/messaging/channel-accounts/{account['id']}/poll", headers=auth_headers)
    conversations = client.get(
        "/api/v1/messaging/conversations?page=1&size=20", headers=auth_headers
    ).json()["data"]
    conversation_id = conversations[0]["id"]

    reply = client.post(
        f"/api/v1/messaging/conversations/{conversation_id}/messages",
        headers=auth_headers,
        json={"body_text": "Проверка отправки"},
    )

    assert reply.status_code == 502
    assert "smtp refused connection" in reply.json()["error"]["message"]

    detail = client.get(
        f"/api/v1/messaging/conversations/{conversation_id}", headers=auth_headers
    ).json()["data"]
    assert detail["status"] == "needs_reply"
    assert detail["messages"][-1]["status"] == "failed"
    assert "smtp refused connection" in detail["messages"][-1]["delivery_error"]


def test_channel_without_smtp_config_keeps_mock_outbound(client, auth_headers):
    """Existing manual/demo channels must not start attempting real delivery."""
    intake = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "external_message_id": "manual-outbound-1",
            "text": "Клиент Анна, телефон +79991234567",
            "sender": {"full_name": "Анна", "phone": "+79991234567"},
        },
    )
    assert intake.status_code == 200

    conversations = client.get(
        "/api/v1/messaging/conversations?page=1&size=20", headers=auth_headers
    ).json()["data"]

    reply = client.post(
        f"/api/v1/messaging/conversations/{conversations[0]['id']}/messages",
        headers=auth_headers,
        json={"body_text": "Ответ менеджера"},
    )

    assert reply.status_code == 200
    assert reply.json()["data"]["messages"][-1]["status"] == "mock_sent"


def test_build_message_sets_threading_headers():
    config = EmailChannelConfig.model_validate(EMAIL_ACCOUNT_CONFIG)

    message = email_transport.build_message(
        config,
        to_email="ivan@example.com",
        subject="Re: Запрос",
        body_text="Текст ответа",
        in_reply_to="<mail-001@example.com>",
    )

    assert message["To"] == "ivan@example.com"
    assert message["In-Reply-To"] == "<mail-001@example.com>"
    assert message["References"] == "<mail-001@example.com>"
    assert "sales@example.com" in message["From"]
    assert "Текст ответа" in message.get_content()


# --- scheduler -------------------------------------------------------------


def test_scheduler_tick_enqueues_only_due_accounts(client, auth_headers, db_session):
    from datetime import UTC, datetime, timedelta

    from app.modules.messaging.models import ChannelAccount
    from app.workers import scheduler

    due = create_email_channel(client, auth_headers, code="email_due")
    later = create_email_channel(client, auth_headers, code="email_later")

    enqueued: list[str] = []
    now = datetime.now(UTC)
    db_session.get(ChannelAccount, uuid.UUID(due["id"])).next_poll_at = now - timedelta(seconds=5)
    db_session.get(ChannelAccount, uuid.UUID(later["id"])).next_poll_at = now + timedelta(hours=1)
    db_session.commit()

    result = scheduler.tick(db_session, now=now, enqueue=enqueued.append)

    assert result == [due["id"]]
    assert enqueued == [due["id"]]


def test_scheduler_skips_accounts_without_credentials(client, auth_headers, db_session):
    from app.workers import scheduler

    create_email_channel(
        client, auth_headers, code="email_no_creds", secrets={"smtp_password": "only-smtp"}
    )

    assert scheduler.tick(db_session, enqueue=lambda account_id: None) == []


def test_scheduler_skips_inactive_accounts(client, auth_headers, db_session):
    from app.workers import scheduler

    account = create_email_channel(client, auth_headers, code="email_inactive")
    client.patch(
        f"/api/v1/messaging/channel-accounts/{account['id']}",
        headers=auth_headers,
        json={"is_active": False},
    )

    assert scheduler.tick(db_session, enqueue=lambda account_id: None) == []


def test_scheduler_inline_mode_polls_without_rq(client, auth_headers, db_session, monkeypatch):
    """Inline mode must not import rq — it cannot even load on Windows."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy.orm import sessionmaker

    from app.core.config import get_settings
    from app.workers import email_poller, scheduler

    create_email_channel(client, auth_headers, code="email_inline")
    monkeypatch.setattr(
        email_transport,
        "fetch_messages",
        lambda config, password, *, limit: [
            email_transport.FetchedEmail(uid="9", raw=build_raw_email())
        ],
    )
    # The job normally opens its own session against the configured database;
    # bind it to the engine this test is using instead.
    monkeypatch.setattr(
        email_poller, "SessionLocal", sessionmaker(bind=db_session.get_bind(), future=True)
    )
    monkeypatch.setattr(get_settings(), "channel_poll_inline", True)

    due = datetime.now(UTC) + timedelta(minutes=5)

    assert len(scheduler.tick(db_session, now=due)) == 1

    conversations = client.get(
        "/api/v1/messaging/conversations?page=1&size=20", headers=auth_headers
    ).json()["data"]
    assert len(conversations) == 1
    assert conversations[0]["channel_account"]["code"] == "email_inline"


@pytest.mark.parametrize(
    ("interval", "expected"),
    [(10, 30), (45, 45), (None, 120)],
)
def test_poll_interval_respects_minimum_and_default(interval, expected):
    from app.modules.messaging.channel_config import poll_interval_seconds
    from app.modules.messaging.models import ChannelAccount

    config = {} if interval is None else {"poll_interval_seconds": interval}
    account = ChannelAccount(code="x", channel_type="email", name="x", config_json=config)

    assert poll_interval_seconds(account) == expected


# --- worker entrypoints ----------------------------------------------------
# These run in a fresh interpreter on purpose. Inside the test suite the
# conftest builds the FastAPI app, which imports every model module as a side
# effect and hides a missing model registry in the worker itself.


@pytest.mark.parametrize(
    "module",
    ["app.workers.scheduler", "app.workers.email_poller"],
)
def test_worker_module_configures_mappers_standalone(module, tmp_path):
    """A worker entrypoint must map its models without the FastAPI app.

    Regression: both workers imported only messaging models, so SQLAlchemy could
    not resolve the relationship declared as "User" and every mapper failed on
    the first query.
    """
    import subprocess
    import sys

    program = (
        f"import {module}\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "configure_mappers()\n"
        "print('ok')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
        env={**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'worker.db'}"},
    )

    assert completed.returncode == 0, completed.stderr
    assert "ok" in completed.stdout
