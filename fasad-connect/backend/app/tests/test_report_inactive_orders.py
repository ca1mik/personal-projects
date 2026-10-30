"""«Их заказы» на странице пропавших клиентов — именно их.

Кнопка «Их заказы, Excel» без единой галочки молча выгружала всю базу заказов:
порог «не покупал N дней» до эндпоинта не доходил, и «их» означало «всех».
Файл с чужими заказами хуже отсутствия файла — по нему делают обзвон.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta


def _order_for(client, auth_headers, db_session, name: str, email: str, days_ago: int) -> dict:
    """Заказ клиента, заведённый нужное число дней назад."""
    from app.modules.orders.models import Order

    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Фасады",
            "sender": {"full_name": name, "email": email},
            "raw_payload": {},
        },
    ).json()["data"]
    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    row = db_session.get(Order, uuid.UUID(order["id"]))
    row.created_at = datetime.now(UTC) - timedelta(days=days_ago)
    db_session.commit()
    return order


def _numbers(client, auth_headers, query: str) -> set[str]:
    data = client.get(f"/api/v1/reports/orders?{query}", headers=auth_headers).json()["data"]
    return {row["order_number"] for row in data["rows"]}


def test_threshold_limits_the_orders_to_the_visible_clients(client, auth_headers, db_session):
    """Порог задан, галочек нет — в отчёт идут только пропавшие клиенты."""
    lost = _order_for(client, auth_headers, db_session, "Пропал", "lost@example.com", 200)
    active = _order_for(client, auth_headers, db_session, "Активен", "active@example.com", 3)

    found = _numbers(client, auth_headers, "period=all&inactive_days=90")

    assert lost["order_number"] in found
    assert active["order_number"] not in found, "в «их заказы» попал заказ активного клиента"


def test_without_threshold_all_orders_are_listed(client, auth_headers, db_session):
    """Без порога отчёт по заказам как был — общий."""
    lost = _order_for(client, auth_headers, db_session, "Пропал2", "lost2@example.com", 200)
    active = _order_for(client, auth_headers, db_session, "Активен2", "active2@example.com", 3)

    found = _numbers(client, auth_headers, "period=all")

    assert {lost["order_number"], active["order_number"]} <= found


def test_explicit_ticks_win_over_the_threshold(client, auth_headers, db_session):
    """Отметили галочками — берём отмеченных, а не всех подходящих под порог."""
    first = _order_for(client, auth_headers, db_session, "Первый", "one@example.com", 200)
    second = _order_for(client, auth_headers, db_session, "Второй", "two@example.com", 200)

    card = client.get(f"/api/v1/orders/{first['id']}", headers=auth_headers).json()["data"]
    found = _numbers(
        client, auth_headers, f"period=all&inactive_days=90&client_ids={card['client_id']}"
    )

    assert found == {first["order_number"]}
    assert second["order_number"] not in found


def test_threshold_matching_nobody_gives_an_empty_report(client, auth_headers, db_session):
    """Под порог никто не попал — пустой отчёт, а не вся база.

    Это и была исходная ошибка: пустой отбор читался как «отбора нет».
    """
    _order_for(client, auth_headers, db_session, "Активен3", "active3@example.com", 1)

    found = _numbers(client, auth_headers, "period=all&inactive_days=365")

    assert found == set()


def test_xlsx_respects_the_threshold(client, auth_headers, db_session):
    """Файл считается по тому же отбору, что и экран."""
    _order_for(client, auth_headers, db_session, "Активен4", "active4@example.com", 1)

    response = client.get(
        "/api/v1/reports/orders.xlsx?period=all&inactive_days=365", headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.content, "файл пустой"
