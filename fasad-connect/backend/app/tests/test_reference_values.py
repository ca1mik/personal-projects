"""Подсказки для полей «Цвет» и «Фрезеровка».

Настоящие значения студии в справочниках не заведены — они копятся в заявках и
заказах. Поиск должен искать именно по ним.
"""

from __future__ import annotations


def _lead_with(client, parts, email):
    return client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Заявка для подсказок",
            "sender": {"full_name": "Подсказки", "phone": "+79990002020", "email": email},
            "raw_payload": {"quantity": len(parts), "parts": parts},
        },
    ).json()["data"]


def test_colors_and_millings_come_from_previous_leads(client, auth_headers):
    _lead_with(
        client,
        [
            {
                "width": 700,
                "height": 400,
                "quantity": 2,
                "material": "Эмаль RAL 9003 плита 19мм",
                "milling": "фрез",
            },
            {
                "width": 500,
                "height": 400,
                "quantity": 1,
                "material": "Эмаль RAL 9003 плита 19мм",
                "milling": "мыло",
            },
        ],
        "hints1@example.com",
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]

    colors = {item["value"]: item["used"] for item in data["colors"]}
    millings = {item["value"]: item["used"] for item in data["millings"]}
    # В подсказке остаётся цвет, а не вся запись из бланка: иначе менеджер
    # выбирает из списка «Эмаль RAL 9003 плита 19мм» и снова заносит в цвет
    # толщину с видом работ.
    assert "Эмаль RAL 9003 плита 19мм" not in colors
    assert colors["RAL 9003"] == 2
    assert millings["фрез"] == 1
    assert millings["мыло"] == 1


def test_different_spellings_of_one_colour_merge(client, auth_headers):
    """Одна эмаль, записанная по-разному, — одна строка подсказки."""
    _lead_with(
        client,
        [
            {"width": 700, "height": 400, "quantity": 1, "material": "Эмаль RAL 9003 плита 19мм"},
            {"width": 700, "height": 400, "quantity": 1, "material": "эмаль рал-9003"},
            {"width": 700, "height": 400, "quantity": 1, "material": "RAL9003"},
        ],
        "hints5@example.com",
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]
    colors = [item["value"] for item in data["colors"]]

    assert colors.count("RAL 9003") == 1


def test_most_used_value_goes_first(client, auth_headers):
    _lead_with(
        client,
        [{"width": 700, "height": 400, "quantity": 1, "material": "Частый цвет"} for _ in range(3)]
        + [{"width": 700, "height": 400, "quantity": 1, "material": "Редкий цвет"}],
        "hints2@example.com",
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]
    values = [item["value"] for item in data["colors"]]

    assert values.index("Частый цвет") < values.index("Редкий цвет")


def test_hints_are_empty_until_studio_writes_something(client, auth_headers):
    """На пустой базе подсказка пустая — и это то, что просил заказчик.

    Раньше сюда подмешивался зашитый в код справочник плёнок, и менеджер видел
    «Кашемир матовый» с «Чёрным soft-touch», которых у студии в работе не было:
    «все эти цвета, какие-то непонятные, откуда-то там взявшиеся». Справочник
    плёнок остался справочником материалов для раскроя, но подсказку набирает
    работа, а не код.
    """
    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]

    assert data["colors"] == []
    assert data["millings"] == []


def test_seeded_film_colour_does_not_come_back_through_a_saved_layout(client, auth_headers):
    """Круг, которым зашитые цвета возвращались в подсказки.

    Раскрой подставляет новой детали первый материал справочника плёнок —
    «Белый глянец». При сохранении раскроя заявкой это имя уезжает в
    `raw_payload.parts[].material`, откуда подсказки его и читают. Через одну
    сохранённую заявку список снова наполнялся тем, на что жаловался заказчик.

    Одной очистки подсказок мало — нужен запрет на входе.
    """
    _lead_with(
        client,
        [{"width": 700, "height": 400, "quantity": 2, "material": "Белый глянец"}],
        "seeded@example.com",
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]

    assert [item["value"] for item in data["colors"]] == []


def test_studio_colour_still_gets_remembered(client, auth_headers):
    """Запрет касается только зашитых имён: своё студия по-прежнему копит."""
    _lead_with(
        client,
        [
            {"width": 700, "height": 400, "quantity": 1, "material": "Белый глянец"},
            {"width": 700, "height": 400, "quantity": 1, "material": "Капучино софт"},
        ],
        "mixed@example.com",
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]

    assert [item["value"] for item in data["colors"]] == ["Капучино софт"]


def test_article_names_do_not_leak_into_milling_hints(client, auth_headers):
    """Название артикула — не значение фрезеровки.

    Артикулы типа «Фрезеровка» подставлялись в подсказку целиком, и рядом с
    живым «фрез» вставало «Фрезерованный фасад, арт. 116, эмаль» — выбрав такое,
    менеджер занёс бы в графу фрезеровки название изделия.
    """
    created = client.post(
        "/api/v1/price-book",
        json={
            "article": "ФР-99",
            "name": "Фрезерованный фасад, арт. 116, эмаль",
            "kind": "milling",
            "unit": "sqm",
            "price": "1800",
        },
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]

    assert "Фрезерованный фасад, арт. 116, эмаль" not in [
        item["value"] for item in data["millings"]
    ]


def test_order_positions_also_feed_the_hints(client, auth_headers):
    lead = _lead_with(
        client,
        [{"width": 700, "height": 400, "quantity": 1}],
        "hints3@example.com",
    )
    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]
    client.put(
        f"/api/v1/orders/{order['id']}/positions",
        json={
            "positions": [
                {
                    "is_custom": True,
                    "name": "Позиция",
                    "unit": "pcs",
                    "quantity": "1",
                    "unit_price": "100.00",
                    "color": "Цвет из заказа",
                    "milling": "Фрезеровка из заказа",
                }
            ]
        },
        headers=auth_headers,
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]

    assert "Цвет из заказа" in [item["value"] for item in data["colors"]]
    assert "Фрезеровка из заказа" in [item["value"] for item in data["millings"]]


def test_blank_values_are_not_offered(client, auth_headers):
    _lead_with(
        client,
        [{"width": 700, "height": 400, "quantity": 1, "material": "   ", "milling": ""}],
        "hints4@example.com",
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]

    assert all(item["value"].strip() for item in data["colors"])
    assert all(item["value"].strip() for item in data["millings"])


def test_hints_require_authorization(client):
    assert client.get("/api/v1/reference-values").status_code == 401


# --- номера артикулов ------------------------------------------------------
# Заказчик: «я первый раз заполняю заявку и вручную прописываю артикул, например
# 128 — и этот артикул программа должна сохранить, а потом уже можно будет из
# списка его выбирать».


def test_article_typed_in_a_lead_is_remembered(client, auth_headers):
    """Набрала номер руками в заявке — в следующий раз он в подсказке."""
    _lead_with(
        client,
        [{"width": 700, "height": 400, "quantity": 1, "article": "128"}],
        "article1@example.com",
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]

    assert "128" in [item["value"] for item in data["articles"]]


def test_articles_are_sorted_by_how_often_they_are_used(client, auth_headers):
    """Чаще писали — выше в списке: студия набирает ходовые номера постоянно."""
    _lead_with(
        client,
        [{"width": 700, "height": 400, "quantity": 1, "article": "128"} for _ in range(3)]
        + [{"width": 700, "height": 400, "quantity": 1, "article": "301"}],
        "article2@example.com",
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]
    values = [item["value"] for item in data["articles"]]

    assert values.index("128") < values.index("301")


def test_article_from_order_line_is_remembered_too(client, auth_headers):
    """Номер, попавший в смету заказа, тоже остаётся в памяти."""
    lead = _lead_with(
        client,
        [{"width": 700, "height": 400, "quantity": 1}],
        "article3@example.com",
    )
    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]
    client.put(
        f"/api/v1/orders/{order['id']}/positions",
        json={
            "positions": [
                {
                    "article": "512",
                    "kind": "paint",
                    "name": "Фасад",
                    "unit": "sqm",
                    "quantity": "1",
                    "width": "1000",
                    "height": "1000",
                    "unit_price": "1000.00",
                }
            ]
        },
        headers=auth_headers,
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]

    assert "512" in [item["value"] for item in data["articles"]]


def test_blank_article_is_not_offered(client, auth_headers):
    """Пробелы вместо номера в подсказку не попадают."""
    _lead_with(
        client,
        [{"width": 700, "height": 400, "quantity": 1, "article": "   "}],
        "article4@example.com",
    )

    data = client.get("/api/v1/reference-values", headers=auth_headers).json()["data"]

    assert all(item["value"].strip() for item in data["articles"])
