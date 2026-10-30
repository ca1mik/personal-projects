"""Отметка «материал заказан».

Заказчик: «когда мы материал заказали на этот конкретный заказ, например плёнку,
мы цветом выделяем — все понимают, что на этот заказ плёнка заказана, больше не
трогаем. Вот тут можно сделать: заказан материал или не заказан, чтобы мы могли
отмечать».

Раньше это была заливка ячейки в экселе: её нельзя отфильтровать и нельзя
спросить «что ещё не заказано» — а спрашивают это каждый день.
"""

from __future__ import annotations


def _order(client, auth_headers, email: str) -> dict:
    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Заказ для проверки материала",
            "sender": {"full_name": "Материал Тест", "email": email},
            "raw_payload": {},
        },
    ).json()["data"]
    response = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_new_order_has_no_material_mark(client, auth_headers):
    """Пока не отметили — материал считается не заказанным."""
    order = _order(client, auth_headers, "mat1@example.com")

    assert order["material_ordered"] is False
    assert order["material_ordered_at"] is None


def test_mark_sets_the_date_itself(client, auth_headers):
    """Дату ставит система: по ней видно, сколько заказ ждёт материал."""
    order = _order(client, auth_headers, "mat2@example.com")

    response = client.post(
        f"/api/v1/orders/{order['id']}/material-ordered",
        json={"material_ordered": True},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["material_ordered"] is True
    assert data["material_ordered_at"] is not None


def test_unmark_clears_the_date(client, auth_headers):
    """Снятая галочка стирает дату — это отмена ошибочной отметки."""
    order = _order(client, auth_headers, "mat3@example.com")
    client.post(
        f"/api/v1/orders/{order['id']}/material-ordered",
        json={"material_ordered": True},
        headers=auth_headers,
    )

    response = client.post(
        f"/api/v1/orders/{order['id']}/material-ordered",
        json={"material_ordered": False},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["material_ordered"] is False
    assert data["material_ordered_at"] is None


def test_mark_survives_reload(client, auth_headers):
    """Отметка живёт в базе, а не только в ответе на нажатие."""
    order = _order(client, auth_headers, "mat4@example.com")
    client.post(
        f"/api/v1/orders/{order['id']}/material-ordered",
        json={"material_ordered": True},
        headers=auth_headers,
    )

    again = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()["data"]

    assert again["material_ordered"] is True


def test_mark_needs_an_existing_order(client, auth_headers):
    missing = "11111111-1111-1111-1111-111111111111"

    response = client.post(
        f"/api/v1/orders/{missing}/material-ordered",
        json={"material_ordered": True},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_mark_requires_authorization(client, auth_headers):
    order = _order(client, auth_headers, "mat5@example.com")

    response = client.post(
        f"/api/v1/orders/{order['id']}/material-ordered", json={"material_ordered": True}
    )

    assert response.status_code == 401
