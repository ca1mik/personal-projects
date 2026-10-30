"""Карточка заказа: допы списком, адрес клиента и отбор по материалу.

Три вещи, за которыми менеджер сейчас ходит мимо системы:

* доп. заказы — карточка знала только их количество, поэтому «2 доп. заказа»
  были текстом без ссылок, и найти сам доп можно было только поиском по номеру;
* адрес клиента — его спрашивают ради «куда везти», а виден он был ровно в
  одном месте, в карточке клиента;
* «на что материал ещё не заказан» — вопрос каждого утра перед звонком
  поставщику, а отобрать список по этой отметке было нечем.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.pagination import PageParams
from app.modules.orders.repository import OrderRepository


@pytest.fixture
def manager_id(client, auth_headers) -> str:
    return client.get("/api/v1/admin/users?page=1&size=5", headers=auth_headers).json()["data"][0][
        "id"
    ]


@pytest.fixture
def client_with_address(client, auth_headers) -> dict:
    response = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json={
            "full_name": "Адресный Клиент",
            "organization": "ООО «Развозка»",
            "address": "Казань, Рахимова, 8 корпус 1",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def make_order(client, auth_headers, client_id: str, manager_id: str) -> dict:
    response = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"client_id": client_id, "manager_id": manager_id},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


# --- доп. заказы списком ---------------------------------------------------


def test_parent_lists_its_additional_orders(client, auth_headers, client_with_address, manager_id):
    """У родителя виден сам доп, а не только его количество."""
    parent = make_order(client, auth_headers, client_with_address["id"], manager_id)
    extra = client.post(
        f"/api/v1/orders/{parent['id']}/additional",
        headers=auth_headers,
        json={},
    ).json()["data"]

    card = client.get(f"/api/v1/orders/{parent['id']}", headers=auth_headers).json()["data"]

    assert card["additional_orders_count"] == 1
    assert [item["id"] for item in card["additional_orders"]] == [extra["id"]]
    assert card["additional_orders"][0]["order_number"] == extra["order_number"]
    # Ради ссылки список и заводился: без id открыть доп из карточки нечем.
    assert card["additional_orders"][0]["status"]["code"] == "new"


def test_additional_order_can_be_created_with_its_own_positions(
    client, auth_headers, client_with_address, manager_id
):
    """Смету допа можно занести сразу при создании — одним действием.

    Заказчик: «при доп заявке оставить контур как в рабочем месте» — то есть
    занести детали сразу, а не заводить пустой доп и отдельно идти на его
    карточку заполнять смету.
    """
    parent = make_order(client, auth_headers, client_with_address["id"], manager_id)

    extra = client.post(
        f"/api/v1/orders/{parent['id']}/additional",
        headers=auth_headers,
        json={
            "positions": [
                {
                    "is_custom": True,
                    "name": "Довезённый фасад",
                    "quantity": "2",
                    "width": "500",
                    "height": "700",
                    "unit_price": "1000.00",
                }
            ]
        },
    ).json()["data"]

    assert len(extra["positions"]) == 1
    assert extra["positions"][0]["name"] == "Довезённый фасад"
    # 0.5 * 0.7 * 2 = 0.7 м² * 1000 ₽ = 700 ₽
    assert extra["final_amount"] == "700.00"

    card = client.get(f"/api/v1/orders/{parent['id']}", headers=auth_headers).json()["data"]
    assert card["additional_orders"][0]["final_amount"] == "700.00"


def test_additional_order_rejects_unpriced_custom_position(
    client, auth_headers, client_with_address, manager_id
):
    """Та же проверка цены, что и у PUT /positions — доп не создаётся молча за 0 ₽."""
    parent = make_order(client, auth_headers, client_with_address["id"], manager_id)

    response = client.post(
        f"/api/v1/orders/{parent['id']}/additional",
        headers=auth_headers,
        json={"positions": [{"is_custom": True, "name": "Гнутьё", "unit": "pcs"}]},
    )

    assert response.status_code == 422
    assert "своя цена" in response.json()["error"]["message"]
    # Заказ при отказе не должен был остаться висеть без сметы и без причины.
    card = client.get(f"/api/v1/orders/{parent['id']}", headers=auth_headers).json()["data"]
    assert card["additional_orders"] == []


def test_additional_order_without_positions_stays_empty(
    client, auth_headers, client_with_address, manager_id
):
    """Смету при создании допа по-прежнему можно не заносить — поле необязательное."""
    parent = make_order(client, auth_headers, client_with_address["id"], manager_id)

    extra = client.post(
        f"/api/v1/orders/{parent['id']}/additional", headers=auth_headers, json={}
    ).json()["data"]

    assert extra["positions"] == []
    assert extra["final_amount"] == "0.00"


def test_additional_orders_come_in_the_list_too(
    client, auth_headers, client_with_address, manager_id
):
    """Список заказов показывает допы под родителем — там же, где и карточка."""
    parent = make_order(client, auth_headers, client_with_address["id"], manager_id)
    client.post(f"/api/v1/orders/{parent['id']}/additional", headers=auth_headers, json={})
    client.post(f"/api/v1/orders/{parent['id']}/additional", headers=auth_headers, json={})

    rows = client.get("/api/v1/orders?page=1&size=50", headers=auth_headers).json()["data"]
    row = next(item for item in rows if item["id"] == parent["id"])

    assert row["additional_orders_count"] == 2
    assert len(row["additional_orders"]) == 2
    # Порядок — по дате создания: доп №1 идёт перед допом №2, как в номерах.
    assert [item["order_number"] for item in row["additional_orders"]] == sorted(
        item["order_number"] for item in row["additional_orders"]
    )


def test_order_without_additional_has_empty_list(
    client, auth_headers, client_with_address, manager_id
):
    """Обычный заказ отдаёт пустой список, а не отсутствующее поле."""
    order = make_order(client, auth_headers, client_with_address["id"], manager_id)

    card = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()["data"]

    assert card["additional_orders"] == []
    assert card["additional_orders_count"] == 0


def test_additional_order_points_back_and_lists_nothing(
    client, auth_headers, client_with_address, manager_id
):
    """У самого допа список пуст: доп к допу не заводится, дерева нет."""
    parent = make_order(client, auth_headers, client_with_address["id"], manager_id)
    extra = client.post(
        f"/api/v1/orders/{parent['id']}/additional",
        headers=auth_headers,
        json={},
    ).json()["data"]

    card = client.get(f"/api/v1/orders/{extra['id']}", headers=auth_headers).json()["data"]

    assert card["parent_order_id"] == parent["id"]
    assert card["parent_order_number"] == parent["order_number"]
    assert card["additional_orders"] == []


def test_additional_order_has_its_own_payment_status(
    client, auth_headers, client_with_address, manager_id
):
    """Статус оплаты у допа свой — не тот, что у родителя.

    Заказчик: «статус оплаты в самих заказах сделать». У допа могут быть свои
    деньги: довезли доплату по нему, а родитель при этом мог быть оплачен
    полностью или вообще без расчёта — по одному счётчику родителя это не видно.
    """
    parent = make_order(client, auth_headers, client_with_address["id"], manager_id)
    extra = client.post(
        f"/api/v1/orders/{parent['id']}/additional", headers=auth_headers, json={}
    ).json()["data"]

    card = client.get(f"/api/v1/orders/{parent['id']}", headers=auth_headers).json()["data"]
    assert card["additional_orders"][0]["payment_status"] == "Нет расчёта"

    client.post(
        f"/api/v1/orders/{extra['id']}/payments",
        json={"amount": "1500.00", "method": "cash"},
        headers=auth_headers,
    )

    card = client.get(f"/api/v1/orders/{parent['id']}", headers=auth_headers).json()["data"]
    assert card["additional_orders"][0]["payment_status"] == "Аванс"
    # Родителя эта оплата не касается — его собственный баланс не сдвинулся.
    assert card["balance"]["status"] == "Нет расчёта"


# --- адрес клиента в заказе ------------------------------------------------


def test_order_card_carries_client_address(client, auth_headers, client_with_address, manager_id):
    """Адрес приезжает вместе с заказом — карточке не надо ходить за клиентом."""
    order = make_order(client, auth_headers, client_with_address["id"], manager_id)

    card = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()["data"]

    assert card["client"]["address"] == "Казань, Рахимова, 8 корпус 1"


def test_order_list_carries_client_address(client, auth_headers, client_with_address, manager_id):
    make_order(client, auth_headers, client_with_address["id"], manager_id)

    rows = client.get("/api/v1/orders?page=1&size=50", headers=auth_headers).json()["data"]

    assert rows[0]["client"]["address"] == "Казань, Рахимова, 8 корпус 1"


def test_client_without_address_keeps_null(client, auth_headers, manager_id):
    """Адреса может не быть — поле остаётся пустым, а не пропадает из ответа."""
    bare = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json={"full_name": "Без Адреса"},
    ).json()["data"]
    order = make_order(client, auth_headers, bare["id"], manager_id)

    card = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()["data"]

    assert card["client"]["address"] is None


# --- поиск клиента по адресу -----------------------------------------------


def test_clients_search_finds_by_address(client, auth_headers, client_with_address):
    """«Кто у нас на Рахимова» — обычный вопрос, когда машина едет в ту сторону."""
    response = client.get("/api/v1/clients?page=1&size=50&search=рахимова", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["data"]] == [client_with_address["id"]]


def test_clients_search_by_other_street_finds_nobody(client, auth_headers, client_with_address):
    response = client.get("/api/v1/clients?page=1&size=50&search=ленина", headers=auth_headers)

    assert response.json()["data"] == []


def test_clients_search_by_address_needs_authorization(client, client_with_address):
    assert client.get("/api/v1/clients?page=1&size=50&search=рахимова").status_code == 401


# --- отбор «материал не заказан» -------------------------------------------


def test_repository_filters_orders_without_material(
    client, auth_headers, client_with_address, manager_id, db_session
):
    """Отбор «материал не заказан» — тот самый список для звонка поставщику."""
    waiting = make_order(client, auth_headers, client_with_address["id"], manager_id)
    ordered = make_order(client, auth_headers, client_with_address["id"], manager_id)
    client.post(
        f"/api/v1/orders/{ordered['id']}/material-ordered",
        headers=auth_headers,
        json={"material_ordered": True},
    )

    rows, meta = OrderRepository.list_orders(
        db_session, PageParams(page=1, size=50), material_ordered=False
    )

    assert [str(item.id) for item in rows] == [waiting["id"]]
    assert meta["total"] == 1


def test_repository_filters_orders_with_material(
    client, auth_headers, client_with_address, manager_id, db_session
):
    make_order(client, auth_headers, client_with_address["id"], manager_id)
    ordered = make_order(client, auth_headers, client_with_address["id"], manager_id)
    client.post(
        f"/api/v1/orders/{ordered['id']}/material-ordered",
        headers=auth_headers,
        json={"material_ordered": True},
    )

    rows, _ = OrderRepository.list_orders(
        db_session, PageParams(page=1, size=50), material_ordered=True
    )

    assert [str(item.id) for item in rows] == [ordered["id"]]


def test_repository_without_material_filter_returns_everything(
    client, auth_headers, client_with_address, manager_id, db_session
):
    """Фильтр не задан — список прежний. Старые вызовы поведение не меняют."""
    make_order(client, auth_headers, client_with_address["id"], manager_id)
    make_order(client, auth_headers, client_with_address["id"], manager_id)

    rows, meta = OrderRepository.list_orders(db_session, PageParams(page=1, size=50))

    assert meta["total"] == 2
    assert len(rows) == 2


def test_repository_material_filter_combines_with_client(
    client, auth_headers, client_with_address, manager_id, db_session
):
    """Отбор по материалу не отменяет остальные условия."""
    make_order(client, auth_headers, client_with_address["id"], manager_id)
    other = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json={"full_name": "Другой Клиент"},
    ).json()["data"]
    make_order(client, auth_headers, other["id"], manager_id)

    rows, _ = OrderRepository.list_orders(
        db_session,
        PageParams(page=1, size=50),
        material_ordered=False,
        client_id=uuid.UUID(other["id"]),
    )

    assert [str(item.client_id) for item in rows] == [other["id"]]
