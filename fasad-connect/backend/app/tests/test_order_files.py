"""Файлы к заказу: приложить, скачать, прокомментировать, удалить."""

from __future__ import annotations

import io

from app.core.config import get_settings


def _create_order(client, auth_headers) -> str:
    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "website_form",
            "text": "Name: Файлы Тест, phone +79990000000, email files@example.com",
            "raw_payload": {"form_id": "files-1"},
        },
    ).json()["data"]
    return client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]["id"]


def _upload(client, auth_headers, order_id, *, name="Эскиз.pdf", content=b"%PDF-1.4 test", **form):
    return client.post(
        f"/api/v1/orders/{order_id}/files",
        files={"file": (name, io.BytesIO(content), "application/pdf")},
        data=form,
        headers=auth_headers,
    )


def test_upload_then_list_and_download(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    uploaded = _upload(client, auth_headers, order_id, comment="Эскиз от клиента")

    assert uploaded.status_code == 200
    data = uploaded.json()["data"]
    assert data["file_name"] == "Эскиз.pdf"
    assert data["comment"] == "Эскиз от клиента"
    assert data["size_bytes"] == len(b"%PDF-1.4 test")
    assert data["author_name"] == "Admin User"

    listed = client.get(f"/api/v1/orders/{order_id}/files", headers=auth_headers).json()["data"]
    assert [item["id"] for item in listed] == [data["id"]]

    downloaded = client.get(f"/api/v1/documents/{data['id']}/download", headers=auth_headers)
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.4 test"
    # Кириллица в имени файла едет в filename* по RFC 5987.
    assert "filename*=UTF-8''" in downloaded.headers["content-disposition"]


def test_file_name_with_path_is_stripped(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = _upload(client, auth_headers, order_id, name="../../etc/passwd")

    assert response.status_code == 200
    # Путь отброшен, остался только последний сегмент.
    assert response.json()["data"]["file_name"] == "passwd"


def test_two_files_with_same_name_do_not_overwrite(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    first = _upload(client, auth_headers, order_id, name="фото.jpg", content=b"first")
    second = _upload(client, auth_headers, order_id, name="фото.jpg", content=b"second")

    first_content = client.get(
        f"/api/v1/documents/{first.json()['data']['id']}/download", headers=auth_headers
    ).content
    second_content = client.get(
        f"/api/v1/documents/{second.json()['data']['id']}/download", headers=auth_headers
    ).content
    assert first_content == b"first"
    assert second_content == b"second"


def test_empty_file_is_rejected(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = _upload(client, auth_headers, order_id, content=b"")

    assert response.status_code == 422
    assert "пустой" in response.json()["error"]["message"]


def test_file_above_limit_is_rejected(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    limit = get_settings().order_file_max_mb * 1024 * 1024

    response = _upload(client, auth_headers, order_id, content=b"x" * (limit + 1))

    assert response.status_code == 413
    assert "МБ" in response.json()["error"]["message"]


def test_upload_to_missing_order_is_404(client, auth_headers):
    response = _upload(client, auth_headers, "00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404


def test_comment_can_be_edited_and_file_deleted(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    document_id = _upload(client, auth_headers, order_id).json()["data"]["id"]

    updated = client.patch(
        f"/api/v1/documents/{document_id}",
        json={"comment": "Согласовано с клиентом"},
        headers=auth_headers,
    )
    assert updated.json()["data"]["comment"] == "Согласовано с клиентом"

    deleted = client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers)
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/orders/{order_id}/files", headers=auth_headers).json()["data"] == []


def test_system_export_cannot_be_deleted(client, auth_headers, db_session):
    """Выгрузку системы удалять нельзя — на неё ссылается история заказа."""
    import uuid

    from app.modules.documents.models import Document

    order_id = _create_order(client, auth_headers)
    document = Document(
        order_id=uuid.UUID(order_id),
        doc_type="quote",
        file_name="quote.md",
        file_path=f"documents/{order_id}/quote.md",
    )
    db_session.add(document)
    db_session.commit()

    response = client.delete(f"/api/v1/documents/{document.id}", headers=auth_headers)

    assert response.status_code == 422
    assert "Системные выгрузки" in response.json()["error"]["message"]


def test_files_require_authorization(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    assert client.get(f"/api/v1/orders/{order_id}/files").status_code == 401
