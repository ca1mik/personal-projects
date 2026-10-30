"""Справочник артикулов: цена подтягивается, история пишется, дубли не проходят."""

from __future__ import annotations


def _create_item(client, auth_headers, **overrides):
    payload = {
        "article": "ФР-01",
        "name": "Фрезеровка «Классика»",
        "kind": "milling",
        "unit": "sqm",
        "price": "1200.00",
    }
    payload.update(overrides)
    return client.post("/api/v1/price-book", json=payload, headers=auth_headers)


def test_create_price_item_writes_first_price_into_history(client, auth_headers):
    response = _create_item(client, auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["article"] == "ФР-01"
    assert data["kind_label"] == "Фрезеровка"
    assert data["unit_label"] == "м²"
    # Заведение артикула — тоже событие цены: иначе в карточке пустая история.
    assert len(data["price_changes"]) == 1
    assert data["price_changes"][0]["new_price"] == "1200.00"


def test_article_is_normalized_and_duplicates_rejected(client, auth_headers):
    _create_item(client, auth_headers)

    # Тот же артикул в другом регистре и с пробелами — это он же.
    response = _create_item(client, auth_headers, article="  фр-01 ")

    assert response.status_code == 409
    assert "уже есть" in response.json()["error"]["message"]


def test_price_change_is_recorded_with_comment(client, auth_headers):
    item_id = _create_item(client, auth_headers).json()["data"]["id"]

    response = client.patch(
        f"/api/v1/price-book/{item_id}",
        json={"price": "1450.00", "price_comment": "Подорожал материал"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    changes = response.json()["data"]["price_changes"]
    assert len(changes) == 2
    latest = changes[0]
    assert latest["old_price"] == "1200.00"
    assert latest["new_price"] == "1450.00"
    assert latest["comment"] == "Подорожал материал"


def test_update_without_price_change_adds_no_history(client, auth_headers):
    item_id = _create_item(client, auth_headers).json()["data"]["id"]

    response = client.patch(
        f"/api/v1/price-book/{item_id}",
        json={"name": "Фрезеровка «Классика» 2"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert len(response.json()["data"]["price_changes"]) == 1


def test_manager_can_correct_article_and_name_in_catalog(client, auth_headers):
    item_id = _create_item(client, auth_headers).json()["data"]["id"]

    response = client.patch(
        f"/api/v1/price-book/{item_id}",
        json={"article": "арт. 112 пвх эмаль", "name": "Мыло R2", "kind": "film"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["article"] == "112"
    assert response.json()["data"]["name"] == "Мыло R2"
    assert response.json()["data"]["kind"] == "film"
    assert len(response.json()["data"]["price_changes"]) == 1


def test_correcting_article_cannot_duplicate_one_in_same_kind(client, auth_headers):
    first_id = _create_item(client, auth_headers).json()["data"]["id"]
    second_id = _create_item(client, auth_headers, article="ФР-02").json()["data"]["id"]

    conflict = client.patch(
        f"/api/v1/price-book/{second_id}",
        json={"article": " фр-01 "},
        headers=auth_headers,
    )

    assert conflict.status_code == 409
    assert client.get(f"/api/v1/price-book/{first_id}", headers=auth_headers).json()["data"]["article"] == "ФР-01"
    assert client.get(f"/api/v1/price-book/{second_id}", headers=auth_headers).json()["data"]["article"] == "ФР-02"


def test_changing_kind_cannot_create_duplicate_article(client, auth_headers):
    _create_item(client, auth_headers, article="R2", kind="milling")
    second_id = _create_item(client, auth_headers, article="R2", kind="film").json()["data"]["id"]

    conflict = client.patch(
        f"/api/v1/price-book/{second_id}",
        json={"kind": "milling"},
        headers=auth_headers,
    )

    assert conflict.status_code == 409
    assert client.get(f"/api/v1/price-book/{second_id}", headers=auth_headers).json()["data"]["kind"] == "film"


def test_search_and_kind_filter(client, auth_headers):
    _create_item(client, auth_headers)
    _create_item(
        client,
        auth_headers,
        article="ШП-01",
        name="Шпон дуб",
        kind="veneer",
        price="2500.00",
    )

    by_kind = client.get("/api/v1/price-book?kind=veneer", headers=auth_headers).json()["data"]
    assert [item["article"] for item in by_kind] == ["ШП-01"]

    by_search = client.get("/api/v1/price-book?search=дуб", headers=auth_headers).json()["data"]
    assert [item["article"] for item in by_search] == ["ШП-01"]


def test_list_accepts_the_page_size_frontend_asks_for(client, auth_headers):
    """Справочник целиком нужен выпадающему списку в смете.

    Общая пагинация обрывает страницу на 100 записях, и запрос фронта на 200
    отвечал 422 — список артикулов в заказе молча оказывался пустым.
    """
    _create_item(client, auth_headers)

    response = client.get("/api/v1/price-book?page=1&size=200", headers=auth_headers)

    assert response.status_code == 200
    assert [item["article"] for item in response.json()["data"]] == ["ФР-01"]


def test_list_rejects_absurd_page_size(client, auth_headers):
    response = client.get("/api/v1/price-book?page=1&size=5000", headers=auth_headers)

    assert response.status_code == 422


def test_price_item_requires_authorization(client):
    response = client.get("/api/v1/price-book")

    assert response.status_code == 401


def test_operator_cannot_create_price_item(client, operator_auth_headers):
    """Вошёл, но прав нет — 403, а не 401.

    401 фронт понимает как «сессия протухла» и уводит на страницу входа, где
    человек вводит верный пароль и снова видит форму.
    """
    response = _create_item(client, operator_auth_headers)

    assert response.status_code == 403


def test_options_list_kinds_and_units(client, auth_headers):
    response = client.get("/api/v1/price-book/options", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert {"code": "milling", "label": "Фрезеровка"} in data["kinds"]
    assert {"code": "sqm", "label": "м²"} in data["units"]


def test_article_prefix_is_stripped_only_before_a_number(client, auth_headers):
    r"""«Арт 109» и «артикул 109» — один и тот же артикул «109».

    Приставку снимали правилом `^арт[.\s]*`, и у слова «артикул» оно съедало
    первые три буквы: «артикул 113» превращалось в «ИКУЛ 113». Заказчик пишет
    фрезеровку в бланке именно словом «артикул», и такой номер уезжал в
    справочник искажённым.
    """
    with_prefix = _create_item(client, auth_headers, article="Арт 109")
    assert with_prefix.status_code == 200
    assert with_prefix.json()["data"]["article"] == "109"

    spelled_out = _create_item(client, auth_headers, article="артикул 113")
    assert spelled_out.status_code == 200
    assert spelled_out.json()["data"]["article"] == "113"

    # Тот же номер, записанный словом и цифрой, — дубль.
    assert _create_item(client, auth_headers, article="109").status_code == 409


def test_composite_article_survives_normalization(client, auth_headers):
    """«ФР 01» остаётся целым: это номер, а не приставка с номером."""
    response = _create_item(client, auth_headers, article="ФР 01")

    assert response.status_code == 200
    assert response.json()["data"]["article"] == "ФР 01"
