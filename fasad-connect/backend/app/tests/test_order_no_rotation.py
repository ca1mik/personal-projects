"""Запрет поворота детали в заказе.

Заказчик: «сделай сразу в самом заказе „нельзя поворачивать"».

Признак «материал с текстурой» это делал побочно, но причина не всегда в
текстуре: бывает направление шлифовки, рисунок фрезы, требование клиента класть
все фасады в одну сторону. Отмечать такое текстурой значило бы врать в данных.
"""

from __future__ import annotations


def _create_order(client, auth_headers) -> dict:
    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "website_form",
            "text": "Name: Поворот Тест, phone +79990000777",
            "raw_payload": {"form_id": "rotation-1"},
        },
    ).json()["data"]
    return client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]


def test_new_order_allows_rotation(client, auth_headers):
    """По умолчанию поворот разрешён: так на лист влезает больше."""
    order = _create_order(client, auth_headers)

    assert order["no_rotation"] is False
    assert order["has_texture"] is False


def test_flag_is_saved_and_read_back(client, auth_headers):
    order = _create_order(client, auth_headers)

    response = client.patch(
        f"/api/v1/orders/{order['id']}", json={"no_rotation": True}, headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["no_rotation"] is True
    stored = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()["data"]
    assert stored["no_rotation"] is True


def test_flag_can_be_removed(client, auth_headers):
    """Поставили по ошибке — снимается."""
    order = _create_order(client, auth_headers)
    client.patch(f"/api/v1/orders/{order['id']}", json={"no_rotation": True}, headers=auth_headers)

    off = client.patch(
        f"/api/v1/orders/{order['id']}", json={"no_rotation": False}, headers=auth_headers
    )

    assert off.json()["data"]["no_rotation"] is False


def test_flag_is_independent_from_texture(client, auth_headers):
    """Два разных признака: запрет поворота не выставляет текстуру и наоборот."""
    order = _create_order(client, auth_headers)

    client.patch(f"/api/v1/orders/{order['id']}", json={"no_rotation": True}, headers=auth_headers)
    stored = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()["data"]
    assert stored["no_rotation"] is True
    assert stored["has_texture"] is False

    client.patch(f"/api/v1/orders/{order['id']}", json={"has_texture": True}, headers=auth_headers)
    both = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()["data"]
    assert both["no_rotation"] is True
    assert both["has_texture"] is True


def test_other_fields_survive_the_flag(client, auth_headers):
    """Частичная правка не сбрасывает соседние поля."""
    order = _create_order(client, auth_headers)
    client.patch(
        f"/api/v1/orders/{order['id']}",
        json={"comment": "везти в субботу"},
        headers=auth_headers,
    )

    client.patch(f"/api/v1/orders/{order['id']}", json={"no_rotation": True}, headers=auth_headers)

    stored = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()["data"]
    assert stored["comment"] == "везти в субботу"
    assert stored["no_rotation"] is True


def test_garbage_value_is_rejected(client, auth_headers):
    """«иногда» — не булево значение."""
    order = _create_order(client, auth_headers)

    response = client.patch(
        f"/api/v1/orders/{order['id']}", json={"no_rotation": "иногда"}, headers=auth_headers
    )

    assert response.status_code == 422, response.text
