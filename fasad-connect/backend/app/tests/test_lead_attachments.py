"""Скачивание вложений заявки.

Раньше карточка заявки печатала вложение как сырой служебный `file_path`
текстом — открыть файл из интерфейса было нельзя в принципе, эндпоинта
скачивания не было вовсе. У заказов (`documents/{id}/download`) он есть уже
давно, у заявок — нет. Здесь — тот же контракт для заявок.
"""

from __future__ import annotations

import base64
import uuid
from urllib.parse import quote


def _intake_with_attachment(client, *, content: bytes = b"%PDF-1.4 fake scan"):
    payload = {
        "source_channel": "email",
        "text": "Заявка со сканом",
        "sender": {"full_name": "Вложение Тест", "phone": "+79170009100"},
        "attachments": [
            {
                "file_name": "скан.pdf",
                "mime_type": "application/pdf",
                "size_bytes": len(content),
                "content_base64": base64.b64encode(content).decode("ascii"),
            }
        ],
    }
    return client.post("/api/v1/leads/intake", json=payload).json()["data"]


def test_download_lead_attachment_returns_original_bytes(client, auth_headers):
    content = b"%PDF-1.4 fake scan"
    lead = _intake_with_attachment(client, content=content)
    attachment_id = lead["attachments"][0]["id"]

    response = client.get(
        f"/api/v1/leads/attachments/{attachment_id}/download", headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.content == content
    assert response.headers["content-type"].startswith("application/pdf")


def test_download_lead_attachment_names_the_file(client, auth_headers):
    lead = _intake_with_attachment(client)
    attachment_id = lead["attachments"][0]["id"]

    response = client.get(
        f"/api/v1/leads/attachments/{attachment_id}/download", headers=auth_headers
    )

    # Кириллица в заголовке уходит RFC 5987-кодировкой (как и у файлов заказа) —
    # обычная filename="" на не-ASCII именах превращается в "????.pdf".
    assert quote("скан.pdf") in response.headers["content-disposition"]


def test_download_missing_lead_attachment_returns_404(client, auth_headers):
    response = client.get(
        f"/api/v1/leads/attachments/{uuid.uuid4()}/download", headers=auth_headers
    )

    assert response.status_code == 404


def test_download_lead_attachment_requires_auth(client):
    lead = _intake_with_attachment(client)
    attachment_id = lead["attachments"][0]["id"]

    response = client.get(f"/api/v1/leads/attachments/{attachment_id}/download")

    assert response.status_code == 401
