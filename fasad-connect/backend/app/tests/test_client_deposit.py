from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.modules.clients.models import ClientDepositMovement
from app.modules.users.models import User


def _create_client(client, auth_headers):
    response = client.post("/api/v1/clients", json={"full_name": "Депозитный клиент"}, headers=auth_headers)
    assert response.status_code == 200
    return response.json()["data"]["id"]


def _create_order(client, auth_headers, client_id, db_session):
    manager_id = str(db_session.scalar(select(User).where(User.login == "admin")).id)
    response = client.post(
        "/api/v1/orders",
        json={"client_id": client_id, "manager_id": manager_id},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_deposit_is_independent_and_can_pay_an_order(client, auth_headers, db_session):
    client_id = _create_client(client, auth_headers)
    topup = client.post(
        f"/api/v1/clients/{client_id}/deposit",
        json={"amount": "1500.00", "method": "cash", "comment": "На будущие заказы"},
        headers=auth_headers,
    )
    assert topup.status_code == 200, topup.text
    assert topup.json()["data"]["balance"] == "1500.00"
    assert topup.json()["data"]["movements"][0]["order_id"] is None
    methods = client.get("/api/v1/orders/payment-methods", headers=auth_headers).json()["data"]
    assert any(item["code"] == "deposit" for item in methods)
    listed = client.get("/api/v1/clients?page=1&size=20", headers=auth_headers).json()["data"]
    assert next(item for item in listed if item["id"] == client_id)["balance_status"] == "Аванс"

    order_id = _create_order(client, auth_headers, client_id, db_session)
    payment = client.post(
        f"/api/v1/orders/{order_id}/payments",
        json={"amount": "600.00", "method": "deposit"},
        headers=auth_headers,
    )
    assert payment.status_code == 200, payment.text
    detail = client.get(f"/api/v1/clients/{client_id}", headers=auth_headers).json()["data"]
    assert detail["deposit"]["balance"] == "900.00"
    assert detail["statement"]["balance"]["paid"] == "1500.00"

    rejected = client.post(
        f"/api/v1/orders/{order_id}/payments",
        json={"amount": "1000.00", "method": "deposit"}, headers=auth_headers,
    )
    assert rejected.status_code == 422
    assert client.get(f"/api/v1/clients/{client_id}", headers=auth_headers).json()["data"]["deposit"]["balance"] == "900.00"

    deleted = client.delete(
        f"/api/v1/orders/{order_id}/payments/{payment.json()['data']['id']}",
        headers=auth_headers,
    )
    assert deleted.status_code == 200, deleted.text
    detail = client.get(f"/api/v1/clients/{client_id}", headers=auth_headers).json()["data"]
    assert detail["deposit"]["balance"] == "1500.00"
    assert Decimal(detail["statement"]["balance"]["paid"]) == Decimal("1500.00")
    assert db_session.query(ClientDepositMovement).count() == 3


def test_order_can_be_created_without_payment(client, auth_headers, db_session):
    client_id = _create_client(client, auth_headers)
    order_id = _create_order(client, auth_headers, client_id, db_session)
    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert order["payments"] == []
    assert order["balance"]["paid_amount"] == "0.00"


def test_deposit_correction_requires_reason_and_available_balance(client, auth_headers):
    client_id = _create_client(client, auth_headers)
    client.post(
        f"/api/v1/clients/{client_id}/deposit",
        json={"amount": "1000.00", "method": "cash"},
        headers=auth_headers,
    )
    path = f"/api/v1/clients/{client_id}/deposit/withdraw"

    assert client.post(path, json={"amount": "100.00", "comment": " "}, headers=auth_headers).status_code == 422
    assert client.post(path, json={"amount": "1001.00", "comment": "Ошибка"}, headers=auth_headers).status_code == 422

    response = client.post(
        path,
        json={"amount": "250.00", "method": "cash", "comment": "Исправление ошибочного пополнения"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["balance"] == "750.00"
    assert response.json()["data"]["movements"][0]["kind"] == "withdrawal"

    detail = client.get(f"/api/v1/clients/{client_id}", headers=auth_headers).json()["data"]
    assert detail["statement"]["balance"]["paid"] == "750.00"
    assert detail["statement"]["ledger"][0]["paid"] == "-250.00"
    listed = client.get("/api/v1/clients?page=1&size=20", headers=auth_headers).json()["data"]
    assert next(item for item in listed if item["id"] == client_id)["balance_status"] == "Аванс"
