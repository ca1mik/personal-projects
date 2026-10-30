"""Отчёт «пропавшие клиенты»: галочки, произвольный порог и честный итог.

Заказчик: «я всех клиентов галочкой выбираю и вижу, когда последняя покупка
была». Галочек не было, порог задавался пятью зашитыми кнопками, а итог в шапке
считался ДО отбора — в одном файле шапка была по всей базе, а таблица под ней по
отфильтрованным.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.orders.models import Order

FACADE = {"item_type": "facade", "name": "Фасад", "width": "1000", "height": "500", "depth": "16"}


@pytest.fixture
def manager(client, auth_headers) -> str:
    return client.get("/api/v1/admin/users?page=1&size=5", headers=auth_headers).json()["data"][0][
        "id"
    ]


def _client(client, auth_headers, name: str, phone: str) -> str:
    return client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json={"full_name": name, "phone": phone},
    ).json()["data"]["id"]


def _order(client, auth_headers, db_session, client_id: str, manager: str, amount: str, days: int):
    """Заказ на одну позицию 1000×500 (0,5 м²), сдвинутый в прошлое на ``days``."""
    order = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"client_id": client_id, "manager_id": manager},
    ).json()["data"]
    client.post(
        f"/api/v1/orders/{order['id']}/items",
        headers=auth_headers,
        json={**FACADE, "quantity": 2},
    )
    stored = db_session.get(Order, uuid.UUID(order["id"]))
    stored.final_amount = Decimal(amount)
    stored.created_at = datetime.now(UTC) - timedelta(days=days)
    db_session.commit()
    return order


# --- итог считается после отбора -------------------------------------------


def test_total_matches_the_rows_after_inactive_filter(client, auth_headers, db_session, manager):
    """Шапка и таблица в одном файле должны сходиться.

    Регрессия: ``total`` копился по всем клиентам, а строки отдавались только
    отфильтрованные. В XLSX это выглядело как «сумма 30 000», под ней одна
    строка на 10 000 — заказчик считала это ошибкой в цифрах, и была права.
    """
    stale = _client(client, auth_headers, "Молчун", "+79990000001")
    fresh = _client(client, auth_headers, "Активный", "+79990000002")
    _order(client, auth_headers, db_session, stale, manager, "10000.00", days=200)
    _order(client, auth_headers, db_session, fresh, manager, "20000.00", days=1)

    report = client.get(
        "/api/v1/reports/clients?period=all&inactive_days=120", headers=auth_headers
    ).json()["data"]

    assert [row["full_name"] for row in report["rows"]] == ["Молчун"]
    assert Decimal(report["total"]["amount"]) == Decimal("10000.00")
    assert report["total"]["orders_count"] == 1
    # 2 фасада по 0,5 м² — площадь тоже только по отобранным
    assert Decimal(report["total"]["facade_area_sqm"]) == Decimal("1.000")


def test_total_without_filter_covers_everyone(client, auth_headers, db_session, manager):
    """Без порога отчёт как был: итог по всем клиентам."""
    first = _client(client, auth_headers, "Первый", "+79990000003")
    second = _client(client, auth_headers, "Второй", "+79990000004")
    _order(client, auth_headers, db_session, first, manager, "10000.00", days=200)
    _order(client, auth_headers, db_session, second, manager, "20000.00", days=1)

    report = client.get("/api/v1/reports/clients?period=all", headers=auth_headers).json()["data"]

    assert Decimal(report["total"]["amount"]) == Decimal("30000.00")
    assert report["inactive_days"] is None
    assert report["selected_clients"] is None


# --- произвольный порог ------------------------------------------------------


def test_arbitrary_threshold_is_accepted(client, auth_headers, db_session, manager):
    """Порог — любое число дней, а не пять зашитых кнопок.

    Заказчик спрашивала «а за 45 дней?» — в интерфейсе были только
    30/60/90/180/365, и такой список приходилось выбирать глазами.
    """
    quiet = _client(client, auth_headers, "Сорок Дней", "+79990000005")
    _order(client, auth_headers, db_session, quiet, manager, "5000.00", days=50)

    included = client.get(
        "/api/v1/reports/clients?period=all&inactive_days=45", headers=auth_headers
    ).json()["data"]
    excluded = client.get(
        "/api/v1/reports/clients?period=all&inactive_days=55", headers=auth_headers
    ).json()["data"]

    assert [row["full_name"] for row in included["rows"]] == ["Сорок Дней"]
    assert included["inactive_days"] == 45
    assert excluded["rows"] == []
    assert Decimal(excluded["total"]["amount"]) == Decimal("0")


def test_zero_threshold_is_rejected(client, auth_headers):
    """Ноль дней — не порог: отсекаем на входе, а не выдаём всю базу."""
    response = client.get(
        "/api/v1/reports/clients?period=all&inactive_days=0", headers=auth_headers
    )

    assert response.status_code == 422


def test_non_numeric_threshold_is_rejected(client, auth_headers):
    """Из адресной строки может прийти что угодно — это не должно ронять отчёт."""
    response = client.get(
        "/api/v1/reports/clients?period=all&inactive_days=навсегда", headers=auth_headers
    )

    assert response.status_code == 422


# --- галочки -----------------------------------------------------------------


def test_selected_clients_are_the_only_rows(client, auth_headers, db_session, manager):
    """Отмеченные галочками клиенты — и в таблице, и в итоге."""
    first = _client(client, auth_headers, "Отмеченный", "+79990000006")
    second = _client(client, auth_headers, "Неотмеченный", "+79990000007")
    _order(client, auth_headers, db_session, first, manager, "7000.00", days=10)
    _order(client, auth_headers, db_session, second, manager, "9000.00", days=10)

    report = client.get(
        f"/api/v1/reports/clients?period=all&client_ids={first}", headers=auth_headers
    ).json()["data"]

    assert [row["full_name"] for row in report["rows"]] == ["Отмеченный"]
    assert Decimal(report["total"]["amount"]) == Decimal("7000.00")
    assert report["selected_clients"] == 1


def test_several_selected_clients(client, auth_headers, db_session, manager):
    """Две галочки — две строки и сумма по ним."""
    first = _client(client, auth_headers, "Первый Выбор", "+79990000008")
    second = _client(client, auth_headers, "Второй Выбор", "+79990000009")
    _client(client, auth_headers, "Лишний", "+79990000010")
    _order(client, auth_headers, db_session, first, manager, "1000.00", days=10)
    _order(client, auth_headers, db_session, second, manager, "2000.00", days=10)

    report = client.get(
        f"/api/v1/reports/clients?period=all&client_ids={first}&client_ids={second}",
        headers=auth_headers,
    ).json()["data"]

    assert sorted(row["full_name"] for row in report["rows"]) == ["Второй Выбор", "Первый Выбор"]
    assert Decimal(report["total"]["amount"]) == Decimal("3000.00")


def test_unknown_client_id_gives_empty_report(client, auth_headers, db_session, manager):
    """Чужой id в адресе — пустой отчёт, а не вся база."""
    existing = _client(client, auth_headers, "Существует", "+79990000011")
    _order(client, auth_headers, db_session, existing, manager, "1000.00", days=10)

    report = client.get(
        f"/api/v1/reports/clients?period=all&client_ids={uuid.uuid4()}", headers=auth_headers
    ).json()["data"]

    assert report["rows"] == []
    assert Decimal(report["total"]["amount"]) == Decimal("0")


def test_broken_client_id_is_rejected(client, auth_headers):
    """Не-UUID в галочках — 422, а не пятисотка."""
    response = client.get(
        "/api/v1/reports/clients?period=all&client_ids=не-uuid", headers=auth_headers
    )

    assert response.status_code == 422


# --- материал последнего заказа -----------------------------------------


def test_last_order_material_status(client, auth_headers, db_session, manager):
    """Статус материала по ПОСЛЕДНЕМУ заказу клиента — тот же смысл, что и
    бейдж в списке заказов: «отгружен» важнее «заказан», а у клиента без
    заказов статуса нет вообще (не «не заказан» — заказывать ещё нечего)."""
    no_orders = _client(client, auth_headers, "Без Заказов", "+79990000020")
    not_ordered = _client(client, auth_headers, "Материал Не Заказан", "+79990000021")
    ordered = _client(client, auth_headers, "Материал Заказан", "+79990000022")
    shipped = _client(client, auth_headers, "Материал Отгружен", "+79990000023")

    _order(client, auth_headers, db_session, not_ordered, manager, "1000.00", days=1)

    order_ordered = _order(client, auth_headers, db_session, ordered, manager, "1000.00", days=1)
    stored = db_session.get(Order, uuid.UUID(order_ordered["id"]))
    stored.material_ordered = True
    db_session.commit()

    order_shipped = _order(client, auth_headers, db_session, shipped, manager, "1000.00", days=1)
    stored = db_session.get(Order, uuid.UUID(order_shipped["id"]))
    stored.material_ordered = True
    stored.shipped_at = datetime.now(UTC)
    db_session.commit()

    report = client.get(
        f"/api/v1/reports/clients?period=all&client_ids={no_orders}&client_ids={not_ordered}"
        f"&client_ids={ordered}&client_ids={shipped}",
        headers=auth_headers,
    ).json()["data"]
    by_name = {row["full_name"]: row for row in report["rows"]}

    assert by_name["Без Заказов"]["last_order_material_status"] is None
    assert by_name["Без Заказов"]["last_order_material_status_label"] is None
    assert by_name["Материал Не Заказан"]["last_order_material_status"] == "not_ordered"
    assert by_name["Материал Заказан"]["last_order_material_status"] == "ordered"
    assert by_name["Материал Отгружен"]["last_order_material_status"] == "shipped"


def test_threshold_and_selection_work_together(client, auth_headers, db_session, manager):
    """Галочки сужают уже отобранных по сроку, а не заменяют порог."""
    quiet_one = _client(client, auth_headers, "Тихий Первый", "+79990000012")
    quiet_two = _client(client, auth_headers, "Тихий Второй", "+79990000013")
    _order(client, auth_headers, db_session, quiet_one, manager, "4000.00", days=200)
    _order(client, auth_headers, db_session, quiet_two, manager, "6000.00", days=200)

    report = client.get(
        f"/api/v1/reports/clients?period=all&inactive_days=100&client_ids={quiet_two}",
        headers=auth_headers,
    ).json()["data"]

    assert [row["full_name"] for row in report["rows"]] == ["Тихий Второй"]
    assert Decimal(report["total"]["amount"]) == Decimal("6000.00")
    assert report["inactive_days"] == 100
    assert report["selected_clients"] == 1
