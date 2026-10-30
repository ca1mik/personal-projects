"""Отчёт по обработке: сколько прошло фрезеровки, шпона, мыла."""

from __future__ import annotations


def _order_with_positions(client, auth_headers, positions, *, email="kind@example.com") -> str:
    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "website_form",
            "text": f"Name: Обработка Тест, phone +79990000000, email {email}",
            "raw_payload": {"form_id": email},
        },
    ).json()["data"]
    order_id = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]["id"]
    client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={"positions": positions},
        headers=auth_headers,
    )
    return order_id


def _price_item(client, auth_headers, article, kind, price) -> str:
    return client.post(
        "/api/v1/price-book",
        json={
            "article": article,
            "name": f"Позиция {article}",
            "kind": kind,
            "unit": "sqm",
            "price": price,
        },
        headers=auth_headers,
    ).json()["data"]["id"]


def test_report_splits_by_work_kind(client, auth_headers):
    milling = _price_item(client, auth_headers, "ФР-01", "milling", "1000.00")
    veneer = _price_item(client, auth_headers, "ШП-01", "veneer", "2000.00")

    _order_with_positions(
        client,
        auth_headers,
        [
            {"price_item_id": milling, "name": "Фрезеровка", "width": "1000", "height": "1000"},
            {"price_item_id": veneer, "name": "Шпон", "width": "1000", "height": "2000"},
        ],
    )

    response = client.get("/api/v1/reports/work-kinds?period=all", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    by_kind = {row["kind"]: row for row in data["by_kind"]}

    assert by_kind["milling"]["area_sqm"] == "1.000"
    assert by_kind["milling"]["amount"] == "1000.00"
    assert by_kind["veneer"]["area_sqm"] == "2.000"
    # 2 м² по 2000 ₽ — 4000 ₽.
    assert by_kind["veneer"]["amount"] == "4000.00"
    assert data["total"]["amount"] == "5000.00"
    # Один заказ, хотя строк две.
    assert data["total"]["orders_count"] == 1


def test_two_lines_of_same_kind_count_one_order(client, auth_headers):
    milling = _price_item(client, auth_headers, "ФР-01", "milling", "1000.00")

    _order_with_positions(
        client,
        auth_headers,
        [
            {"price_item_id": milling, "name": "Фасад 1", "width": "1000", "height": "1000"},
            {"price_item_id": milling, "name": "Фасад 2", "width": "1000", "height": "1000"},
        ],
    )

    data = client.get("/api/v1/reports/work-kinds?period=all", headers=auth_headers).json()["data"]
    row = data["by_kind"][0]

    assert row["orders_count"] == 1
    assert row["positions_count"] == 2
    assert row["amount"] == "2000.00"


def test_custom_position_grouped_by_name(client, auth_headers):
    _order_with_positions(
        client,
        auth_headers,
        [
            {
                "is_custom": True,
                "name": "Гнутый фасад",
                "kind": "other",
                "unit": "pcs",
                "quantity": "2",
                "unit_price": "3000.00",
            }
        ],
    )

    data = client.get("/api/v1/reports/work-kinds?period=all", headers=auth_headers).json()["data"]
    row = data["by_article"][0]

    assert row["article"] is None
    assert row["name"] == "Гнутый фасад"
    assert row["amount"] == "6000.00"


def test_shipped_metric_ignores_orders_without_shipping_date(client, auth_headers):
    milling = _price_item(client, auth_headers, "ФР-01", "milling", "1000.00")
    order_id = _order_with_positions(
        client,
        auth_headers,
        [{"price_item_id": milling, "name": "Фасад", "width": "1000", "height": "1000"}],
    )

    empty = client.get(
        "/api/v1/reports/work-kinds?period=all&metric=shipped", headers=auth_headers
    ).json()["data"]
    assert empty["by_kind"] == []

    client.post(f"/api/v1/orders/{order_id}/shipped", json={"shipped": True}, headers=auth_headers)

    shipped = client.get(
        "/api/v1/reports/work-kinds?period=all&metric=shipped", headers=auth_headers
    ).json()["data"]
    assert shipped["metric_label"] == "Отгружено"
    assert shipped["by_kind"][0]["amount"] == "1000.00"


def test_order_without_estimate_is_not_counted(client, auth_headers):
    _order_with_positions(client, auth_headers, [])

    data = client.get("/api/v1/reports/work-kinds?period=all", headers=auth_headers).json()["data"]

    assert data["by_kind"] == []
    assert data["total"]["orders_count"] == 0


def test_report_requires_authorization(client):
    response = client.get("/api/v1/reports/work-kinds")

    assert response.status_code == 401
