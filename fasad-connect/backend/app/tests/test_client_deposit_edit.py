from __future__ import annotations

from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.users.models import User


def _create_client(client, auth_headers):
    response = client.post(
        "/api/v1/clients", json={"full_name": "Тестовый клиент"}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_topup_amount_correction_updates_balance_and_audit(client, auth_headers, db_session):
    client_id = _create_client(client, auth_headers)
    other_client_id = _create_client(client, auth_headers)
    topup = client.post(
        f"/api/v1/clients/{client_id}/deposit",
        json={"amount": "1000.00", "method": "cash"},
        headers=auth_headers,
    )
    movement_id = topup.json()["data"]["movements"][0]["id"]
    path = f"/api/v1/clients/{client_id}/deposit/{movement_id}"

    assert client.patch(path, json={"amount": "500.00", "reason": "  "}, headers=auth_headers).status_code == 422
    assert client.patch(
        f"/api/v1/clients/{other_client_id}/deposit/{movement_id}",
        json={"amount": "500.00", "reason": "Ошибка"}, headers=auth_headers,
    ).status_code == 404

    corrected = client.patch(
        path, json={"amount": "700.00", "reason": "Ошибка ввода"}, headers=auth_headers,
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["data"]["balance"] == "700.00"
    assert corrected.json()["data"]["movements"][0]["amount"] == "700.00"
    detail = client.get(f"/api/v1/clients/{client_id}", headers=auth_headers).json()["data"]
    assert detail["statement"]["balance"]["paid"] == "700.00"

    audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "deposit_topup_corrected"))
    assert audit.old_value_json["amount"] == "1000.00"
    assert audit.new_value_json["amount"] == "700.00"
    assert audit.new_value_json["reason"] == "Ошибка ввода"

    manager_id = str(db_session.scalar(select(User).where(User.login == "admin")).id)
    order = client.post(
        "/api/v1/orders",
        json={"client_id": client_id, "manager_id": manager_id},
        headers=auth_headers,
    )
    assert order.status_code == 200, order.text
    payment = client.post(
        f"/api/v1/orders/{order.json()['data']['id']}/payments",
        json={"amount": "600.00", "method": "deposit"}, headers=auth_headers,
    )
    assert payment.status_code == 200, payment.text
    rejected = client.patch(
        path, json={"amount": "500.00", "reason": "Ошибка ввода"}, headers=auth_headers,
    )
    assert rejected.status_code == 422
    assert client.get(f"/api/v1/clients/{client_id}", headers=auth_headers).json()["data"]["deposit"]["balance"] == "100.00"
