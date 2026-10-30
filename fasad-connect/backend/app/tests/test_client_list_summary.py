"""Список клиентов: дата последнего заказа и статус баланса одной строкой.

Заказчик: «по клиентам больше инфы дай — когда заказ был последний, баланс».
Считается одним запросом на всю страницу списка, не по клиенту — см.
`ClientService._batch_order_summaries`.
"""

from __future__ import annotations


def _client_with_order(client, auth_headers, *, email, phone, amount="1000.00", paid=None):
    item = client.post(
        "/api/v1/price-book",
        json={
            "article": f"СВ-{phone[-4:]}",
            "name": "Позиция для списка клиентов",
            "kind": "milling",
            "unit": "pcs",
            "price": amount,
        },
        headers=auth_headers,
    ).json()["data"]

    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Заявка для списка клиентов",
            "sender": {"full_name": "Список Клиентов Тест", "phone": phone, "email": email},
            "raw_payload": {"quantity": 1},
        },
    ).json()["data"]
    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]
    client.put(
        f"/api/v1/orders/{order['id']}/positions",
        json={
            "positions": [
                {"price_item_id": item["id"], "name": "Позиция", "unit": "pcs", "quantity": "1"}
            ]
        },
        headers=auth_headers,
    )
    if paid is not None:
        client.post(
            f"/api/v1/orders/{order['id']}/payments",
            json={"amount": paid, "method": "cash"},
            headers=auth_headers,
        )
    return lead["client_id"], order


def _find(rows, client_id):
    return next(item for item in rows if item["id"] == client_id)


def test_list_shows_last_order_date_and_debt(client, auth_headers):
    client_id, order = _client_with_order(
        client, auth_headers, email="listsummary-debt@example.com", phone="+79990004001"
    )

    rows = client.get("/api/v1/clients?page=1&size=50", headers=auth_headers).json()["data"]
    row = _find(rows, client_id)

    assert row["last_order_at"] is not None
    assert row["last_order_at"][:10] == order["created_at"][:10]
    assert row["balance_status"] == "Долг"


def test_list_shows_advance_when_overpaid(client, auth_headers):
    client_id, _ = _client_with_order(
        client,
        auth_headers,
        email="listsummary-advance@example.com",
        phone="+79990004002",
        amount="500.00",
        paid="700.00",
    )

    rows = client.get("/api/v1/clients?page=1&size=50", headers=auth_headers).json()["data"]
    row = _find(rows, client_id)

    assert row["balance_status"] == "Аванс"


def test_list_shows_closed_when_paid_in_full(client, auth_headers):
    client_id, _ = _client_with_order(
        client,
        auth_headers,
        email="listsummary-closed@example.com",
        phone="+79990004003",
        amount="500.00",
        paid="500.00",
    )

    rows = client.get("/api/v1/clients?page=1&size=50", headers=auth_headers).json()["data"]
    row = _find(rows, client_id)

    assert row["balance_status"] == "Расчёты закрыты"


def test_client_without_orders_has_no_summary(client, auth_headers):
    created = client.post(
        "/api/v1/clients",
        json={"full_name": "Клиент без заказов"},
        headers=auth_headers,
    ).json()["data"]

    rows = client.get("/api/v1/clients?page=1&size=50", headers=auth_headers).json()["data"]
    row = _find(rows, created["id"])

    assert row["last_order_at"] is None
    assert row["balance_status"] is None


def test_client_list_requires_auth(client):
    response = client.get("/api/v1/clients?page=1&size=50")

    assert response.status_code == 401
