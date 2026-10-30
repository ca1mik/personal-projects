"""Отбор направления в отчёте по объёмам.

Заказчик: «а где можно выбрать, по какому направлению я делаю этот отчёт?».
Разбивка по направлениям в отчёте была, а отбора не было: чтобы посмотреть один
шпон, приходилось читать строку в таблице и держать в уме, что все остальные
цифры — не про него.
"""

from __future__ import annotations

from decimal import Decimal


def _direction(db_session, code: str, name: str, suffix: str):
    from app.modules.directions.models import ProductionDirection

    direction = ProductionDirection(
        code=code,
        name=name,
        number_suffix=suffix,
        material_area_factor=Decimal("1.000"),
        sort_order=1,
        is_active=True,
    )
    db_session.add(direction)
    db_session.commit()
    return direction


def _order_with_direction(client, auth_headers, code: str, email: str, amount: str):
    """Заказ нужного направления с посчитанной сметой."""
    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "direction_code": code,
            "text": "Заказ для отчёта",
            "sender": {"full_name": "Отчёт Тест", "email": email},
            "raw_payload": {},
        },
    ).json()["data"]
    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    item = client.post(
        "/api/v1/price-book",
        json={
            "article": f"ОТЧ-{code}",
            "name": f"Работа {code}",
            "kind": "milling",
            "unit": "pcs",
            "price": amount,
        },
        headers=auth_headers,
    ).json()["data"]
    client.put(
        f"/api/v1/orders/{order['id']}/positions",
        json={
            "positions": [
                {"price_item_id": item["id"], "name": "Позиция", "quantity": "1", "unit": "pcs"}
            ]
        },
        headers=auth_headers,
    )
    return order


def test_report_can_be_filtered_by_direction(client, auth_headers, db_session):
    """С отбором в отчёте остаётся только выбранное направление."""
    _direction(db_session, "veneer", "Шпон", "Ш")
    _direction(db_session, "pvc", "ПВХ", "П")
    _order_with_direction(client, auth_headers, "veneer", "vn@example.com", "1000.00")
    _order_with_direction(client, auth_headers, "pvc", "pvc@example.com", "2000.00")

    report = client.get(
        "/api/v1/reports/volume?period=all&metric=accepted&direction_code=veneer",
        headers=auth_headers,
    ).json()["data"]

    keys = [row["key"] for row in report["by_direction"]]
    assert keys == ["veneer"]
    assert report["total"]["amount"] == "1000.00"


def test_report_without_filter_shows_everything(client, auth_headers, db_session):
    """Без отбора отчёт как был: все направления и общая сумма."""
    _direction(db_session, "veneer", "Шпон", "Ш")
    _direction(db_session, "pvc", "ПВХ", "П")
    _order_with_direction(client, auth_headers, "veneer", "vn2@example.com", "1000.00")
    _order_with_direction(client, auth_headers, "pvc", "pvc2@example.com", "2000.00")

    report = client.get(
        "/api/v1/reports/volume?period=all&metric=accepted", headers=auth_headers
    ).json()["data"]

    keys = sorted(row["key"] for row in report["by_direction"])
    assert keys == ["pvc", "veneer"]
    assert report["total"]["amount"] == "3000.00"


def test_unknown_direction_gives_empty_report(client, auth_headers, db_session):
    """Направления нет — отчёт пустой, а не «все заказы»."""
    _direction(db_session, "veneer", "Шпон", "Ш")
    _order_with_direction(client, auth_headers, "veneer", "vn3@example.com", "1000.00")

    report = client.get(
        "/api/v1/reports/volume?period=all&direction_code=такого-нет",
        headers=auth_headers,
    ).json()["data"]

    assert report["by_direction"] == []
    # сравниваем числом: у пустого отчёта сумма приходит как «0», а не «0.00»
    assert Decimal(report["total"]["amount"]) == Decimal("0")


def test_orders_without_direction_are_selectable(client, auth_headers):
    """Заказы без направления тоже можно отобрать отдельной группой."""
    _order_with_direction(client, auth_headers, "", "nodir@example.com", "500.00")

    report = client.get(
        "/api/v1/reports/volume?period=all&direction_code=none", headers=auth_headers
    ).json()["data"]

    assert [row["key"] for row in report["by_direction"]] == ["none"]
    assert report["total"]["amount"] == "500.00"
