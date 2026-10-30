"""Отбор заказов по отметке «материал заказан».

Заказчик спрашивает это каждое утро перед звонком поставщику: «на что материал
ещё не заказан». Отметка в системе была, а отобрать по ней список было нечем —
менеджер открывал каждый заказ по очереди.

Отбор считает сервер, а не страница: фильтровать уже загруженную сотню
бесполезно, нужный заказ может быть и не в ней.
"""

from __future__ import annotations


def _order(client, auth_headers, email: str) -> dict:
    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Фасады",
            "sender": {"full_name": "Материал Тест", "email": email},
            "raw_payload": {},
        },
    ).json()["data"]
    return client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]


def _mark(client, auth_headers, order_id: str, ordered: bool):
    return client.post(
        f"/api/v1/orders/{order_id}/material-ordered",
        json={"material_ordered": ordered},
        headers=auth_headers,
    )


def _numbers(client, auth_headers, query: str) -> set[str]:
    data = client.get(f"/api/v1/orders?{query}", headers=auth_headers).json()["data"]
    return {item["order_number"] for item in data}


def test_filter_finds_orders_waiting_for_material(client, auth_headers):
    """Главный вопрос утра: на что материал ещё не заказан."""
    waiting = _order(client, auth_headers, "wait@example.com")
    done = _order(client, auth_headers, "done@example.com")
    _mark(client, auth_headers, done["id"], True)

    found = _numbers(client, auth_headers, "page=1&size=50&material_ordered=false")

    assert waiting["order_number"] in found
    assert done["order_number"] not in found


def test_filter_finds_orders_with_material_ordered(client, auth_headers):
    """Обратный отбор тоже нужен: по нему сверяют, что уже заказано."""
    waiting = _order(client, auth_headers, "wait2@example.com")
    done = _order(client, auth_headers, "done2@example.com")
    _mark(client, auth_headers, done["id"], True)

    found = _numbers(client, auth_headers, "page=1&size=50&material_ordered=true")

    assert found == {done["order_number"]}
    assert waiting["order_number"] not in found


def test_without_the_filter_all_orders_are_listed(client, auth_headers):
    """Без отбора список как был — фильтр не должен «прилипать»."""
    waiting = _order(client, auth_headers, "wait3@example.com")
    done = _order(client, auth_headers, "done3@example.com")
    _mark(client, auth_headers, done["id"], True)

    found = _numbers(client, auth_headers, "page=1&size=50")

    assert {waiting["order_number"], done["order_number"]} <= found


def test_unmarking_returns_the_order_to_the_waiting_list(client, auth_headers):
    """Отметили по ошибке и сняли — заказ снова ждёт материал."""
    order = _order(client, auth_headers, "back@example.com")
    _mark(client, auth_headers, order["id"], True)
    _mark(client, auth_headers, order["id"], False)

    found = _numbers(client, auth_headers, "page=1&size=50&material_ordered=false")

    assert order["order_number"] in found


def test_garbage_filter_value_is_rejected(client, auth_headers):
    """«иногда» — не булево значение, и молча игнорировать его нельзя.

    Молча проигнорированный отбор опаснее ошибки: менеджер решит, что материал
    заказан на всё, и не позвонит поставщику.
    """
    response = client.get(
        "/api/v1/orders?page=1&size=50&material_ordered=иногда", headers=auth_headers
    )

    assert response.status_code == 422
