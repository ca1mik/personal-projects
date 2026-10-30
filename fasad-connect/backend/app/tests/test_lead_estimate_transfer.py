"""Посчитанная заявка превращается в смету заказа.

Заказчик считает клиенту цену прямо в таблице приёма заявки. Эти строки обязаны
перейти в заказ — иначе менеджер вводит их второй раз, а цена, названная
клиенту, теряется.
"""

from __future__ import annotations


def _price_item(client, auth_headers, **overrides):
    payload = {
        "article": "ФР-10",
        "name": "Фрезеровка из заявки",
        "kind": "milling",
        "unit": "sqm",
        "price": "1000.00",
    }
    payload.update(overrides)
    return client.post("/api/v1/price-book", json=payload, headers=auth_headers).json()["data"]


def _lead_with_parts(client, parts, *, email="est@example.com", estimate=None):
    raw = {"quantity": sum(int(p.get("quantity", 1)) for p in parts), "parts": parts}
    if estimate:
        raw["estimate"] = estimate
    return client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Заявка с расчётом",
            "sender": {"full_name": "Смета Тест", "phone": "+79990001010", "email": email},
            "raw_payload": raw,
        },
    ).json()["data"]


def test_manual_lead_saves_new_article_and_price_before_order(client, auth_headers):
    part = {
        "width": 600,
        "height": 400,
        "quantity": 1,
        "article": "арт. 331",
        "kind": "milling",
        "unit": "sqm",
        "unit_price": "1800.00",
    }
    _lead_with_parts(client, [part])

    book = client.get("/api/v1/price-book?search=331", headers=auth_headers).json()["data"]
    assert len(book) == 1
    assert book[0]["article"] == "331"
    assert book[0]["price"] == "1800.00"

    _lead_with_parts(client, [{**part, "unit_price": "1500.00"}], email="repeat@example.com")
    book = client.get("/api/v1/price-book?search=331", headers=auth_headers).json()["data"]
    assert len(book) == 1
    assert book[0]["price"] == "1800.00"


def test_priced_lead_becomes_order_estimate(client, auth_headers):
    item = _price_item(client, auth_headers)
    lead = _lead_with_parts(
        client,
        [
            {
                "width": 1000,
                "height": 500,
                "quantity": 2,
                "material": "Эмаль RAL 9003",
                "thickness": "19",
                "milling": "фрез",
                "article": item["article"],
                "kind": "milling",
                "unit": "sqm",
                "unit_price": "1000.00",
                "amount": "1000.00",
                "area_sqm": "1.000000",
            }
        ],
        estimate={"final_amount": "1000.00", "currency": "RUB"},
    )

    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    assert len(order["positions"]) == 1
    position = order["positions"][0]
    assert position["article"] == item["article"]
    assert position["unit_price"] == "1000.00"
    assert position["amount"] == "1000.00"
    assert position["area_sqm"] == "1.000000"
    assert position["color"] == "Эмаль RAL 9003"
    assert position["thickness"] == "19.00"
    assert order["total_amount"] == "1000.00"


def test_price_named_to_client_survives_price_book_change(client, auth_headers):
    """Справочник подорожал после заявки — клиенту всё равно та цена, что назвали."""
    item = _price_item(client, auth_headers)
    lead = _lead_with_parts(
        client,
        [
            {
                "width": 1000,
                "height": 1000,
                "quantity": 1,
                "article": item["article"],
                "unit": "sqm",
                "unit_price": "1000.00",
                "amount": "1000.00",
            }
        ],
        email="frozen@example.com",
    )
    client.patch(
        f"/api/v1/price-book/{item['id']}", json={"price": "5000.00"}, headers=auth_headers
    )

    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    assert order["positions"][0]["unit_price"] == "1000.00"
    assert order["total_amount"] == "1000.00"


def test_lead_without_prices_makes_empty_estimate(client, auth_headers):
    """Заявка без расчёта — заказ без сметы, а не строки за 0 ₽."""
    lead = _lead_with_parts(
        client,
        [{"width": 716, "height": 396, "quantity": 4, "thickness": "19"}],
        email="noprice@example.com",
    )

    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    assert order["positions"] == []
    assert order["total_amount"] == "0.00"


def test_rows_without_price_are_skipped_but_priced_ones_transfer(client, auth_headers):
    item = _price_item(client, auth_headers)
    lead = _lead_with_parts(
        client,
        [
            {"width": 500, "height": 500, "quantity": 1, "thickness": "16"},
            {
                "width": 1000,
                "height": 1000,
                "quantity": 1,
                "article": item["article"],
                "unit": "sqm",
                "unit_price": "1000.00",
                "amount": "1000.00",
            },
        ],
        email="mixed@example.com",
    )

    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    assert len(order["positions"]) == 1
    assert order["positions"][0]["article"] == item["article"]
    assert order["total_amount"] == "1000.00"


def test_unknown_article_is_added_to_the_price_book(client, auth_headers):
    """Номера ещё нет в справочнике — он заводится при переносе в заказ.

    Заказчик: «пусть вводят номенклатуры сами... уже занося в заказ — она
    попадала бы в базу, именно той части, которую выбрали». Раньше такая строка
    уезжала нестандартом, и номер терялся: в следующий раз менеджер набирал его
    заново и цену вспоминал по памяти.
    """
    lead = _lead_with_parts(
        client,
        [
            {
                "width": 1000,
                "height": 1000,
                "quantity": 1,
                "article": "331",
                "kind": "paint",
                "unit": "sqm",
                "unit_price": "1500.00",
                "amount": "1500.00",
            }
        ],
        email="gone@example.com",
    )

    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    position = order["positions"][0]
    assert position["article"] == "331"
    assert position["unit_price"] == "1500.00"
    assert order["total_amount"] == "1500.00"
    # нестандартом больше не считается: у строки есть артикул из справочника
    assert position["is_custom"] is False

    book = client.get("/api/v1/price-book", params={"search": "331"}, headers=auth_headers).json()[
        "data"
    ]
    created = [item for item in book if item["article"] == "331"]
    assert created and created[0]["kind"] == "paint"
    assert created[0]["price"] == "1500.00"
    assert created[0]["name"] == "Эмаль, арт. 331"


def test_article_prefix_does_not_reach_the_order_line(client, auth_headers):
    """«арт. 112» в заявке — в заказе и в справочнике это один и тот же 112-й.

    Раньше в справочник уходил нормализованный номер, а в строку заказа — сырая
    строка с приставкой. Печатная смета и справочник расходились на ровном месте.
    """
    lead = _lead_with_parts(
        client,
        [
            {
                "width": 1000,
                "height": 1000,
                "quantity": 1,
                "article": "арт. 778",
                "kind": "paint",
                "unit": "sqm",
                "unit_price": "1000.00",
                "amount": "1000.00",
            }
        ],
        email="prefix@example.com",
    )

    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    assert order["positions"][0]["article"] == "778"


def test_amount_is_recomputed_when_missing(client, auth_headers):
    """Суммы в строке нет — считаем сами, а не переносим ноль."""
    lead = _lead_with_parts(
        client,
        [
            {
                "width": 1000,
                "height": 2000,
                "quantity": 1,
                "unit": "sqm",
                "unit_price": "1000.00",
            }
        ],
        email="calc@example.com",
    )

    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    # 1000 × 2000 = 2 м², по 1000 ₽ — 2000 ₽
    assert order["positions"][0]["amount"] == "2000.00"


def test_piece_priced_row_uses_quantity_not_area(client, auth_headers):
    item = _price_item(
        client,
        auth_headers,
        article="ПР-10",
        name="Присадка",
        kind="service",
        unit="pcs",
        price="60.00",
    )
    lead = _lead_with_parts(
        client,
        [
            {
                "width": 700,
                "height": 400,
                "quantity": 5,
                "article": item["article"],
                "unit": "pcs",
                "unit_price": "60.00",
            }
        ],
        email="pcs@example.com",
    )

    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    assert order["positions"][0]["amount"] == "300.00"


def test_second_create_order_does_not_double_the_estimate(client, auth_headers):
    """Повторный вызов возвращает тот же заказ и не удваивает строки."""
    item = _price_item(client, auth_headers)
    lead = _lead_with_parts(
        client,
        [
            {
                "width": 1000,
                "height": 1000,
                "quantity": 1,
                "article": item["article"],
                "unit": "sqm",
                "unit_price": "1000.00",
                "amount": "1000.00",
            }
        ],
        email="twice@example.com",
    )

    first = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]
    second = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    assert first["id"] == second["id"]
    assert len(second["positions"]) == 1
    assert second["total_amount"] == "1000.00"
