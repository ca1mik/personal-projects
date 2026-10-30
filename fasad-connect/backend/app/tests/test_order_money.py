"""Смета заказа, оплата и баланс.

Главное правило, которое здесь проверяется: цена в заказе — копия справочника на
момент продажи. Справочник дорожает, старые заказы не двигаются.
"""

from __future__ import annotations


def _create_order(client, auth_headers) -> str:
    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "website_form",
            "text": "Name: Смета Тест, phone +79990000000, email money@example.com",
            "raw_payload": {"form_id": "money-1"},
        },
    ).json()["data"]
    response = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    )
    return response.json()["data"]["id"]


def _create_price_item(client, auth_headers, **overrides) -> dict:
    payload = {
        "article": "ФР-01",
        "name": "Фрезеровка «Классика»",
        "kind": "milling",
        "unit": "sqm",
        "price": "1000.00",
    }
    payload.update(overrides)
    return client.post("/api/v1/price-book", json=payload, headers=auth_headers).json()["data"]


def test_position_takes_price_from_book_and_counts_area(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers)

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "price_item_id": item["id"],
                    "name": "Фасад кухни",
                    "quantity": "2",
                    "width": "1000",
                    "height": "500",
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    position = response.json()["data"][0]
    # 1000 × 500 × 2 = 1 м²; по 1000 ₽ за м² — 1000 ₽.
    assert position["area_sqm"] == "1.000000"
    assert position["unit_price"] == "1000.00"
    assert position["amount"] == "1000.00"
    assert position["article"] == "ФР-01"
    assert position["is_custom"] is False

    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert order["total_amount"] == "1000.00"
    assert order["final_amount"] == "1000.00"


def test_old_order_keeps_its_price_after_book_goes_up(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers)
    client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "price_item_id": item["id"],
                    "name": "Фасад кухни",
                    "quantity": "1",
                    "width": "1000",
                    "height": "1000",
                }
            ]
        },
        headers=auth_headers,
    )

    client.patch(
        f"/api/v1/price-book/{item['id']}",
        json={"price": "5000.00"},
        headers=auth_headers,
    )

    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert order["positions"][0]["unit_price"] == "1000.00"
    assert order["total_amount"] == "1000.00"


def test_custom_position_uses_its_own_price(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "is_custom": True,
                    "name": "Нестандартная гнутая деталь",
                    "unit": "pcs",
                    "quantity": "3",
                    "unit_price": "1500.00",
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    position = response.json()["data"][0]
    assert position["is_custom"] is True
    assert position["price_item_id"] is None
    assert position["amount"] == "4500.00"


def test_piece_article_counts_by_quantity_even_if_request_says_sqm(client, auth_headers):
    """Единица берётся из справочника, а не из запроса.

    У артикула «за штуку» цена не должна умножаться на площадь: интерфейс
    присылает правильную единицу, но API обязан считать по своей.
    """
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(
        client, auth_headers, article="ГН-01", name="Гнутьё", unit="pcs", price="1500.00"
    )

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "price_item_id": item["id"],
                    "name": "Гнутая деталь",
                    "unit": "sqm",
                    "quantity": "3",
                    "width": "1000",
                    "height": "500",
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    position = response.json()["data"][0]
    # 3 шт × 1500 ₽, а не 1,5 м² × 1500 ₽.
    assert position["unit"] == "pcs"
    assert position["amount"] == "4500.00"


def test_priced_position_without_dimensions_is_rejected(client, auth_headers):
    """Цена есть, площади нет — строка ушла бы в заказ нулём."""
    order_id = _create_order(client, auth_headers)

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "is_custom": True,
                    "name": "Гнутьё нестандарт",
                    "unit": "sqm",
                    "quantity": "2",
                    "unit_price": "3500.00",
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert "не заданы размеры" in response.json()["error"]["message"]


def test_priced_position_with_zero_quantity_is_rejected(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "is_custom": True,
                    "name": "Доставка",
                    "unit": "pcs",
                    "quantity": "0",
                    "unit_price": "2000.00",
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert "не задано количество" in response.json()["error"]["message"]


def test_position_without_article_and_without_custom_flag_is_rejected(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={"positions": [{"name": "Непонятно что", "unit_price": "999.00"}]},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert "нестандарт" in response.json()["error"]["message"]


def test_custom_position_without_price_is_rejected(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={"positions": [{"is_custom": True, "name": "Гнутьё", "unit": "pcs"}]},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert "своя цена" in response.json()["error"]["message"]


def test_custom_position_with_explicit_zero_price_is_allowed(client, auth_headers):
    """Ноль руками — законная цена: бонусная позиция, доделка по гарантии.

    Отклоняется именно отсутствие цены, а не ноль. Интерфейс поэтому и просит
    написать 0, если позиция бесплатная.
    """
    order_id = _create_order(client, auth_headers)

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "is_custom": True,
                    "name": "Замена по гарантии",
                    "unit": "pcs",
                    "quantity": "1",
                    "unit_price": "0",
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["amount"] == "0.00"


def test_position_with_unknown_article_is_rejected(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "price_item_id": "00000000-0000-0000-0000-000000000001",
                    "name": "Фасад",
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_disabled_article_cannot_be_sold(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers)
    client.patch(
        f"/api/v1/price-book/{item['id']}", json={"is_active": False}, headers=auth_headers
    )

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={"positions": [{"price_item_id": item["id"], "name": "Фасад"}]},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert "отключён" in response.json()["error"]["message"]


def test_replacing_positions_drops_old_rows(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers)
    body = {
        "positions": [
            {"price_item_id": item["id"], "name": "Строка 1", "width": "1000", "height": "1000"},
            {"price_item_id": item["id"], "name": "Строка 2", "width": "1000", "height": "1000"},
        ]
    }
    client.put(f"/api/v1/orders/{order_id}/positions", json=body, headers=auth_headers)

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={"positions": [body["positions"][0]]},
        headers=auth_headers,
    )

    assert len(response.json()["data"]) == 1
    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert len(order["positions"]) == 1
    assert order["total_amount"] == "1000.00"


def test_balance_shows_advance_then_debt_then_paid(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers)

    # Аванс пришёл до сметы — это ещё не переплата.
    client.post(
        f"/api/v1/orders/{order_id}/payments",
        json={"amount": "3000.00", "method": "cash"},
        headers=auth_headers,
    )
    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert order["balance"]["status"] == "Аванс"
    assert order["balance"]["balance"] == "3000.00"

    client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "price_item_id": item["id"],
                    "name": "Фасады",
                    "quantity": "5",
                    "width": "1000",
                    "height": "1000",
                }
            ]
        },
        headers=auth_headers,
    )
    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert order["balance"]["status"] == "Долг"
    assert order["balance"]["balance"] == "-2000.00"

    client.post(
        f"/api/v1/orders/{order_id}/payments",
        json={"amount": "2000.00", "method": "transfer"},
        headers=auth_headers,
    )
    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert order["balance"]["status"] == "Оплачен полностью"
    assert order["balance"]["balance"] == "0.00"
    assert order["balance"]["by_method"] == [
        {"method": "cash", "label": "Наличные", "amount": "3000.00"},
        {"method": "transfer", "label": "Перевод на карту", "amount": "2000.00"},
    ]


def test_payment_with_unknown_method_is_rejected(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = client.post(
        f"/api/v1/orders/{order_id}/payments",
        json={"amount": "100.00", "method": "bitcoin"},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert "Неизвестный способ оплаты" in response.json()["error"]["message"]


def test_payment_must_be_positive(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = client.post(
        f"/api/v1/orders/{order_id}/payments",
        json={"amount": "0", "method": "cash"},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_payment_can_be_deleted(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    payment = client.post(
        f"/api/v1/orders/{order_id}/payments",
        json={"amount": "500.00", "method": "card"},
        headers=auth_headers,
    ).json()["data"]

    response = client.delete(
        f"/api/v1/orders/{order_id}/payments/{payment['id']}", headers=auth_headers
    )

    assert response.status_code == 200
    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert order["payments"] == []
    assert order["balance"]["paid_amount"] == "0.00"


def test_payment_of_another_order_cannot_be_deleted(client, auth_headers):
    first = _create_order(client, auth_headers)
    second = _create_order(client, auth_headers)
    payment = client.post(
        f"/api/v1/orders/{first}/payments",
        json={"amount": "500.00", "method": "card"},
        headers=auth_headers,
    ).json()["data"]

    response = client.delete(
        f"/api/v1/orders/{second}/payments/{payment['id']}", headers=auth_headers
    )

    assert response.status_code == 404


def test_shipped_flag_sets_and_clears_date(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    shipped = client.post(
        f"/api/v1/orders/{order_id}/shipped", json={"shipped": True}, headers=auth_headers
    ).json()["data"]
    assert shipped["shipped_at"] is not None

    returned = client.post(
        f"/api/v1/orders/{order_id}/shipped", json={"shipped": False}, headers=auth_headers
    ).json()["data"]
    assert returned["shipped_at"] is None


def test_payment_methods_are_listed(client, auth_headers):
    response = client.get("/api/v1/orders/payment-methods", headers=auth_headers)

    assert response.status_code == 200
    assert {"code": "cash", "label": "Наличные"} in response.json()["data"]


def test_positions_require_authorization(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = client.put(f"/api/v1/orders/{order_id}/positions", json={"positions": []})

    assert response.status_code == 401


# --- индивидуальная цена под заказ ----------------------------------------
# Заказчик: «пусть с базы подтягиваются, но при этом менеджер может сама
# корректировать их, не меняя в самой базе, просто по типу индивидуальных цен
# под заказ».


def _put_position(client, auth_headers, order_id: str, **fields):
    payload = {
        "name": "Фасад кухни",
        "quantity": "2",
        "width": "1000",
        "height": "500",
    }
    payload.update(fields)
    return client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={"positions": [payload]},
        headers=auth_headers,
    )


def test_manager_can_sell_article_below_price_list(client, auth_headers):
    """Своя цена в строке перебивает прайс и помечается как правка."""
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers, price="2100.00")

    response = _put_position(
        client, auth_headers, order_id, price_item_id=item["id"], unit_price="1900.00"
    )

    assert response.status_code == 200, response.text
    position = response.json()["data"][0]
    assert position["unit_price"] == "1900.00"
    assert position["base_price"] == "2100.00"
    assert position["price_overridden"] is True
    # 1 м² по 1900 ₽
    assert position["amount"] == "1900.00"


def test_price_list_is_not_touched_by_the_correction(client, auth_headers):
    """Правка живёт в заказе: справочник для остальных заказов не меняется."""
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers, price="2100.00")

    _put_position(client, auth_headers, order_id, price_item_id=item["id"], unit_price="1900.00")

    in_book = client.get(f"/api/v1/price-book/{item['id']}", headers=auth_headers).json()["data"]
    assert in_book["price"] == "2100.00"


def test_untouched_price_is_not_marked_as_corrected(client, auth_headers):
    """Цена совпала с прайсом — это не индивидуальная цена, а обычная продажа."""
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers, price="2100.00")

    response = _put_position(
        client, auth_headers, order_id, price_item_id=item["id"], unit_price="2100.00"
    )

    assert response.status_code == 200, response.text
    position = response.json()["data"][0]
    assert position["price_overridden"] is False
    assert position["unit_price"] == "2100.00"


def test_price_still_pulled_from_book_when_field_left_empty(client, auth_headers):
    """Поле цены не тронули — работает как раньше, цена из справочника."""
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers, price="2100.00")

    response = _put_position(client, auth_headers, order_id, price_item_id=item["id"])

    assert response.status_code == 200, response.text
    position = response.json()["data"][0]
    assert position["unit_price"] == "2100.00"
    assert position["price_overridden"] is False


def test_zero_correction_is_refused(client, auth_headers):
    """Ноль руками — это незаполненное поле, а не скидка 100 %."""
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers, price="2100.00")

    response = _put_position(
        client, auth_headers, order_id, price_item_id=item["id"], unit_price="0"
    )

    assert response.status_code == 422, response.text
    assert "нулевой" in response.json()["error"]["message"]


def test_corrected_price_survives_price_list_change(client, auth_headers):
    """Прайс подняли — в заказе осталась договорная цена, а не новая прайсовая."""
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers, price="2100.00")
    _put_position(client, auth_headers, order_id, price_item_id=item["id"], unit_price="1900.00")

    client.patch(
        f"/api/v1/price-book/{item['id']}",
        json={"price": "2500.00", "price_comment": "подорожание"},
        headers=auth_headers,
    )

    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert order["positions"][0]["unit_price"] == "1900.00"
    assert order["final_amount"] == "1900.00"


# --- номенклатура заводится из сметы --------------------------------------
# Заказчик: «пусть вводят номенклатуры сами... уже занося в заказ — она попадала
# бы в базу, именно той части, которую выбрали».


def _find_article(client, auth_headers, article: str, kind: str | None = None):
    items = client.get(
        "/api/v1/price-book", params={"search": article, "size": 50}, headers=auth_headers
    ).json()["data"]
    for item in items:
        if item["article"] == article and (kind is None or item["kind"] == kind):
            return item
    return None


def test_new_article_from_estimate_lands_in_the_price_book(client, auth_headers):
    """Написали номер и цену в смете — номер появился в справочнике."""
    order_id = _create_order(client, auth_headers)

    response = _put_position(
        client, auth_headers, order_id, article="112", kind="paint", unit_price="2100.00"
    )

    assert response.status_code == 200, response.text
    position = response.json()["data"][0]
    assert position["article"] == "112"
    assert position["is_custom"] is False

    created = _find_article(client, auth_headers, "112", "paint")
    assert created is not None
    assert created["price"] == "2100.00"
    assert created["kind_label"] == "Эмаль"
    # Название по типу, а не «арт. 112 пвх эмаль».
    assert created["name"] == "Эмаль, арт. 112"


def test_same_number_lives_in_two_types_independently(client, auth_headers):
    """112 в эмали и 112 в плёнке — разные позиции со своей ценой."""
    order_id = _create_order(client, auth_headers)

    _put_position(client, auth_headers, order_id, article="112", kind="paint", unit_price="2100.00")
    _put_position(client, auth_headers, order_id, article="112", kind="film", unit_price="900.00")

    paint = _find_article(client, auth_headers, "112", "paint")
    film = _find_article(client, auth_headers, "112", "film")
    assert paint and film and paint["id"] != film["id"]
    assert paint["price"] == "2100.00"
    assert film["price"] == "900.00"


def test_known_number_keeps_its_price_in_the_book(client, auth_headers):
    """Разовая скидка не переписывает прайс: она остаётся ценой строки."""
    order_id = _create_order(client, auth_headers)
    _put_position(client, auth_headers, order_id, article="221", kind="paint", unit_price="2000.00")

    response = _put_position(
        client, auth_headers, order_id, article="221", kind="paint", unit_price="1500.00"
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"][0]["unit_price"] == "1500.00"
    in_book = _find_article(client, auth_headers, "221", "paint")
    assert in_book["price"] == "2000.00"


def test_number_is_found_by_a_part_of_it(client, auth_headers):
    """Заказчик: занесли «331» — по поиску «3» оно должно находиться."""
    order_id = _create_order(client, auth_headers)
    _put_position(client, auth_headers, order_id, article="331", kind="paint", unit_price="1000.00")

    found = client.get(
        "/api/v1/price-book", params={"search": "3", "size": 50}, headers=auth_headers
    ).json()["data"]

    assert "331" in [item["article"] for item in found]


def test_article_prefix_is_cut_from_the_number(client, auth_headers):
    """«арт. 112» — это номер 112, а не отдельная позиция."""
    order_id = _create_order(client, auth_headers)

    _put_position(
        client, auth_headers, order_id, article="арт. 445", kind="paint", unit_price="1000.00"
    )

    assert _find_article(client, auth_headers, "445", "paint") is not None


def test_row_without_price_does_not_create_nomenclature(client, auth_headers):
    """Номер без цены в справочник не попадает: продавать было бы нечем."""
    order_id = _create_order(client, auth_headers)

    response = _put_position(client, auth_headers, order_id, article="556", kind="paint")

    assert response.status_code == 422, response.text
    assert _find_article(client, auth_headers, "556", "paint") is None


def test_description_after_the_number_is_dropped(client, auth_headers):
    """Дословный пример заказчика: «арт. 112 пвх эмаль» — это номер 112.

    Покрытие хранится типом позиции, в номере ему делать нечего: иначе один и
    тот же артикул расходится на несколько записей справочника.
    """
    order_id = _create_order(client, auth_headers)

    _put_position(
        client,
        auth_headers,
        order_id,
        article="арт. 112 пвх эмаль попаписякака",
        kind="paint",
        unit_price="2100.00",
    )

    assert _find_article(client, auth_headers, "112", "paint") is not None


def test_composite_number_with_space_survives(client, auth_headers):
    """«ФР 01» — составной номер целиком, а не «ФР».

    Отбрасываем только словесный хвост. Если в остатке есть цифры, это часть
    самого номера, и обрезать её значило бы слить разные позиции в одну.
    """
    order_id = _create_order(client, auth_headers)

    _put_position(
        client, auth_headers, order_id, article="ФР 01", kind="paint", unit_price="1500.00"
    )

    assert _find_article(client, auth_headers, "ФР 01", "paint") is not None


# --- доп. заказы ----------------------------------------------------------
# Заказчик: «доп заказы к этому же нужно создать... и в ветке было бы "заказ **
# (2 доп заказа)"». Клиент довёз замер или добавил фасады взамен испорченных:
# деньги и отгрузка у допа свои, но висит он под основным заказом.


def _add_extra(client, auth_headers, order_id: str, **body):
    return client.post(f"/api/v1/orders/{order_id}/additional", json=body, headers=auth_headers)


def test_additional_order_is_numbered_after_the_main_one(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    main = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]

    first = _add_extra(client, auth_headers, order_id)
    second = _add_extra(client, auth_headers, order_id)

    assert first.status_code == 200, first.text
    assert first.json()["data"]["order_number"] == f"{main['order_number']}/1"
    assert second.json()["data"]["order_number"] == f"{main['order_number']}/2"


def test_main_order_counts_its_additional_orders(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    _add_extra(client, auth_headers, order_id)
    _add_extra(client, auth_headers, order_id)

    main = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]

    assert main["additional_orders_count"] == 2
    assert main["parent_order_id"] is None


def test_additional_order_points_at_the_main_one(client, auth_headers):
    order_id = _create_order(client, auth_headers)
    main = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]

    extra = _add_extra(client, auth_headers, order_id).json()["data"]

    assert extra["parent_order_id"] == order_id
    assert extra["parent_order_number"] == main["order_number"]
    assert extra["client_id"] == main["client_id"]


def test_additional_of_additional_hangs_on_the_main_order(client, auth_headers):
    """Доп к допу — это дерево, в котором в цеху не разобраться."""
    order_id = _create_order(client, auth_headers)
    extra = _add_extra(client, auth_headers, order_id).json()["data"]

    deeper = _add_extra(client, auth_headers, extra["id"]).json()["data"]

    assert deeper["parent_order_id"] == order_id
    main = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert main["additional_orders_count"] == 2


def test_additional_order_starts_with_empty_estimate(client, auth_headers):
    """Доп — это то, что добавили сверх, а не копия основного заказа."""
    order_id = _create_order(client, auth_headers)
    item = _create_price_item(client, auth_headers, price="1000.00")
    _put_position(client, auth_headers, order_id, price_item_id=item["id"])

    extra = _add_extra(client, auth_headers, order_id).json()["data"]

    assert extra["positions"] == []
    assert extra["final_amount"] == "0.00"


def test_additional_order_accepts_its_own_number(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    extra = _add_extra(client, auth_headers, order_id, order_number="44 03 п доп").json()["data"]

    assert extra["order_number"] == "44 03 п доп"


def test_additional_order_needs_an_existing_main_one(client, auth_headers):
    missing = "11111111-1111-1111-1111-111111111111"

    response = _add_extra(client, auth_headers, missing)

    assert response.status_code == 404, response.text


def test_additional_order_requires_authorization(client, auth_headers):
    order_id = _create_order(client, auth_headers)

    response = client.post(f"/api/v1/orders/{order_id}/additional", json={})

    assert response.status_code == 401
