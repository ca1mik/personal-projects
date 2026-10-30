from __future__ import annotations

import uuid


def _create_order_from_lead(client, auth_headers):
    lead_response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "website_form",
            "text": "Name: Test Client, phone +79990000000, email order@example.com, wardrobe 1200x2400x600",
            "raw_payload": {"form_id": "wf-1"},
        },
    )
    lead_id = lead_response.json()["data"]["id"]
    order_response = client.post(
        f"/api/v1/leads/{lead_id}/create-order", json={}, headers=auth_headers
    )
    order_id = order_response.json()["data"]["id"]
    return order_id


def test_generate_parts(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)
    templates = client.get("/api/v1/templates?page=1&size=10", headers=auth_headers).json()["data"]
    template_id = templates[0]["id"]

    client.post(
        f"/api/v1/orders/{order_id}/items",
        json={
            "template_id": template_id,
            "item_type": "wardrobe_basic",
            "name": "Wardrobe test",
            "width": 1200,
            "height": 2400,
            "depth": 600,
            "quantity": 1,
        },
        headers=auth_headers,
    )

    response = client.post(f"/api/v1/orders/{order_id}/generate-parts", headers=auth_headers)

    assert response.status_code == 200
    parts = response.json()["data"]
    assert len(parts) >= 5


def test_calculate_order(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)
    template_id = client.get("/api/v1/templates?page=1&size=10", headers=auth_headers).json()[
        "data"
    ][0]["id"]
    client.post(
        f"/api/v1/orders/{order_id}/items",
        json={
            "template_id": template_id,
            "item_type": "wardrobe_basic",
            "name": "Wardrobe calc",
            "width": 1200,
            "height": 2400,
            "depth": 600,
            "quantity": 1,
        },
        headers=auth_headers,
    )
    client.post(f"/api/v1/orders/{order_id}/generate-parts", headers=auth_headers)

    response = client.post(f"/api/v1/orders/{order_id}/calculate", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert float(data["final_amount"]) > 0
    assert data["components"]


def test_export_cutting(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)
    template_id = client.get("/api/v1/templates?page=1&size=10", headers=auth_headers).json()[
        "data"
    ][0]["id"]
    client.post(
        f"/api/v1/orders/{order_id}/items",
        json={
            "template_id": template_id,
            "item_type": "wardrobe_basic",
            "name": "Wardrobe export",
            "width": 1200,
            "height": 2400,
            "depth": 600,
            "quantity": 1,
        },
        headers=auth_headers,
    )
    client.post(f"/api/v1/orders/{order_id}/generate-parts", headers=auth_headers)

    response = client.post(f"/api/v1/orders/{order_id}/export-cutting", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["format"] == "csv"
    assert data["file_name"].endswith(".csv")


def test_export_cutting_from_smeta_positions(client, auth_headers):
    """Реальный путь: заказ из заявки, без единой позиции каталога (OrderItem)
    — так живёт почти любой настоящий заказ. Раньше это гарантированно давало
    500 (`generate_parts` требовал кромочный материал ещё до того, как понять,
    что генерировать нечего, а `export_order` смотрел только на пустой
    `order.parts`). Раскрой должен строиться из сметы (`OrderPosition`)."""
    order_id = _create_order_from_lead(client, auth_headers)
    put_response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "name": "Фасад кухни",
                    "is_custom": True,
                    "unit_price": "1500",
                    "quantity": "2",
                    "width": "1000",
                    "height": "500",
                },
            ]
        },
        headers=auth_headers,
    )
    assert put_response.status_code == 200, put_response.text

    response = client.post(f"/api/v1/orders/{order_id}/export-cutting", headers=auth_headers)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["format"] == "csv"
    assert data["file_name"].endswith(".csv")


def test_export_cutting_without_any_dimensions_is_a_clean_error(client, auth_headers):
    """Ни позиций каталога, ни сметы с размерами — раньше 500 без единой
    подсказки, что случилось. Должна быть понятная ошибка, а не трейсбек."""
    order_id = _create_order_from_lead(client, auth_headers)

    response = client.post(f"/api/v1/orders/{order_id}/export-cutting", headers=auth_headers)

    assert response.status_code == 400, response.text
    assert response.json()["error"]["message"]


def test_save_cutting_layout(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)

    response = client.post(
        f"/api/v1/orders/{order_id}/save-cutting-layout",
        json={
            "sheet_settings": {
                "sheetWidth": 2750,
                "sheetHeight": 1250,
                "marginX": 15,
                "marginY": 15,
                "defaultGapX": 60,
                "defaultGapY": 60,
                "algorithm": "optimal",
            },
            "stats": {
                "sheetCount": 1,
                "requestedCount": 2,
                "placedCount": 2,
                "unplacedCount": 0,
                "detailArea": 1.234,
                "freeArea": 0.456,
                "gapArea": 0.111,
                "marginArea": 0.089,
                "fillPercent": 68.76,
            },
            "parts": [
                {
                    "name": "Фасад 1246x436",
                    "width": 1246,
                    "height": 436,
                    "quantity": 2,
                    "gapX": 60,
                    "gapY": 60,
                }
            ],
            "sheets": [{"globalIndex": 1, "placements": [
                {"unitId": "facade-1", "x": 15, "y": 15, "width": 1246, "height": 436},
                {"unitId": "facade-2", "x": 1321, "y": 15, "width": 1246, "height": 436},
            ]}],
            "active_sheet_index": 1,
            "pattern_filter": "white_gloss",
            "sheet_svg": '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["export_type"] == "cutting_layout"
    assert data["format"] == "json"
    assert data["file_name"].endswith(".json")


def test_list_and_download_cutting_csv_export(client, auth_headers):
    """Раньше карточка «Экспорты» печатала file_name/file_path текстом без
    единой ссылки — файл нельзя было реально скачать. Список и скачивание
    должны работать по-настоящему."""
    order_id = _create_order_from_lead(client, auth_headers)
    client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={
            "positions": [
                {
                    "name": "Фасад кухни",
                    "is_custom": True,
                    "unit_price": "1500",
                    "quantity": "2",
                    "width": "1000",
                    "height": "500",
                },
            ]
        },
        headers=auth_headers,
    )
    export = client.post(f"/api/v1/orders/{order_id}/export-cutting", headers=auth_headers).json()[
        "data"
    ]

    listing = client.get(f"/api/v1/orders/{order_id}/exports", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    items = listing.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == export["id"]
    assert items[0]["export_type"] == "cutting"

    download = client.get(
        f"/api/v1/orders/{order_id}/exports/{export['id']}/download", headers=auth_headers
    )
    assert download.status_code == 200, download.text
    assert download.headers["content-type"].startswith("text/csv")
    assert "Фасад кухни" in download.text
    assert "1000" in download.text


def test_download_cutting_layout_export_returns_the_svg_map(client, auth_headers):
    """Сохранённая раскладка хранится как JSON-снимок (для повторного
    редактирования на экране), но скачать «Экспорт» должен давать саму
    SVG-карту раскроя — то, что реально открывают и печатают, а не
    внутреннюю структуру данных."""
    order_id = _create_order_from_lead(client, auth_headers)
    svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    export = client.post(
        f"/api/v1/orders/{order_id}/save-cutting-layout",
        json={
            "sheet_settings": {
                "sheetWidth": 2750,
                "sheetHeight": 1250,
                "marginX": 15,
                "marginY": 15,
                "defaultGapX": 60,
                "defaultGapY": 60,
                "algorithm": "optimal",
            },
            "stats": {
                "sheetCount": 1,
                "requestedCount": 1,
                "placedCount": 1,
                "unplacedCount": 0,
                "detailArea": 1.0,
                "freeArea": 0.1,
                "gapArea": 0.1,
                "marginArea": 0.1,
                "fillPercent": 90.0,
            },
            "parts": [
                {
                    "name": "Фасад",
                    "width": 500,
                    "height": 500,
                    "quantity": 1,
                    "gapX": 60,
                    "gapY": 60,
                }
            ],
            "sheets": [{"globalIndex": 1, "placements": [
                {"unitId": "facade-1", "x": 15, "y": 15, "width": 500, "height": 500},
            ]}],
            "active_sheet_index": 1,
            "pattern_filter": None,
            "sheet_svg": svg_content,
        },
        headers=auth_headers,
    ).json()["data"]

    download = client.get(
        f"/api/v1/orders/{order_id}/exports/{export['id']}/download", headers=auth_headers
    )

    assert download.status_code == 200, download.text
    assert download.headers["content-type"].startswith("image/svg+xml")
    assert download.text == svg_content


def test_download_export_from_wrong_order_is_not_found(client, auth_headers):
    """Отпечаток заказа в URL защищает от подстановки чужого export_id."""
    order_a = _create_order_from_lead(client, auth_headers)
    order_b = _create_order_from_lead(client, auth_headers)
    client.put(
        f"/api/v1/orders/{order_a}/positions",
        json={
            "positions": [
                {
                    "name": "Фасад",
                    "is_custom": True,
                    "unit_price": "1000",
                    "quantity": "1",
                    "width": "500",
                    "height": "500",
                },
            ]
        },
        headers=auth_headers,
    )
    export = client.post(f"/api/v1/orders/{order_a}/export-cutting", headers=auth_headers).json()[
        "data"
    ]

    response = client.get(
        f"/api/v1/orders/{order_b}/exports/{export['id']}/download", headers=auth_headers
    )

    assert response.status_code == 404


def _add_shipped_status(db_session):
    """Отгрузки нет в общем наборе статусов — заводим её точечно для теста."""
    from app.modules.order_statuses.models import OrderStatus

    db_session.add(OrderStatus(code="shipped", name="Отгружен", sort_order=90, is_terminal=True))
    db_session.commit()


def test_change_status_success(client, auth_headers):
    """Кнопка статуса переводит заказ и оставляет след в истории."""
    order_id = _create_order_from_lead(client, auth_headers)

    response = client.post(
        f"/api/v1/orders/{order_id}/change-status",
        json={"status_code": "approved"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"]["code"] == "approved"
    assert data["approved_at"] is not None
    assert len(data["status_history"]) == 2


def test_orders_list_filters_by_status_and_excludes_it(client, auth_headers, db_session):
    """Три состояния фильтра статуса из одного параметра каждое:
    status_code=cancelled — только отменённые; exclude_status_code=cancelled
    — все, кроме отменённых («обычные»); ни того, ни другого — вообще все."""
    # "cancelled" нет в общем наборе статусов тестовой БД (см. _add_shipped_status
    # чуть ниже — та же история) — заводим точечно для этого теста.
    from app.modules.order_statuses.models import OrderStatus

    db_session.add(OrderStatus(code="cancelled", name="Отменён", sort_order=100, is_terminal=True))
    db_session.commit()

    active_order = _create_order_from_lead(client, auth_headers)
    cancelled_order = _create_order_from_lead(client, auth_headers)
    cancel_response = client.post(
        f"/api/v1/orders/{cancelled_order}/change-status",
        json={"status_code": "cancelled"},
        headers=auth_headers,
    )
    assert cancel_response.status_code == 200, cancel_response.text

    only_cancelled = client.get(
        "/api/v1/orders?status_code=cancelled", headers=auth_headers
    ).json()["data"]
    assert [row["id"] for row in only_cancelled] == [cancelled_order]

    only_normal = client.get(
        "/api/v1/orders?exclude_status_code=cancelled", headers=auth_headers
    ).json()["data"]
    normal_ids = [row["id"] for row in only_normal]
    assert active_order in normal_ids
    assert cancelled_order not in normal_ids

    everyone = client.get("/api/v1/orders", headers=auth_headers).json()["data"]
    all_ids = [row["id"] for row in everyone]
    assert active_order in all_ids
    assert cancelled_order in all_ids


def test_change_status_sets_shipped_at(client, auth_headers, db_session):
    """Дата отгрузки проставляется сама — менеджер её руками не вводит."""
    _add_shipped_status(db_session)
    order_id = _create_order_from_lead(client, auth_headers)
    assert (
        client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]["shipped_at"]
        is None
    )

    response = client.post(
        f"/api/v1/orders/{order_id}/change-status",
        json={"status_code": "shipped"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"]["code"] == "shipped"
    assert data["shipped_at"] is not None


def test_change_status_rejects_unknown_status(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)

    response = client.post(
        f"/api/v1/orders/{order_id}/change-status",
        json={"status_code": "teleported"},
        headers=auth_headers,
    )

    assert response.status_code == 404
    message = response.json()["error"]["message"]
    assert "teleported" in message
    # текст отказа видит менеджер — он должен быть по-русски
    assert "не найден" in message


def test_change_status_rejects_unknown_order(client, auth_headers):
    response = client.post(
        f"/api/v1/orders/{uuid.uuid4()}/change-status",
        json={"status_code": "approved"},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Заказ не найден"


def test_order_texture_flag_defaults_to_false(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)

    data = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]

    assert data["has_texture"] is False


def test_order_texture_flag_saved(client, auth_headers):
    """Галочка текстуры сохраняется и переживает перечитывание заказа."""
    order_id = _create_order_from_lead(client, auth_headers)

    response = client.patch(
        f"/api/v1/orders/{order_id}",
        json={"has_texture": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["has_texture"] is True
    stored = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"]
    assert stored["has_texture"] is True

    off = client.patch(
        f"/api/v1/orders/{order_id}",
        json={"has_texture": False},
        headers=auth_headers,
    )
    assert off.json()["data"]["has_texture"] is False


def test_order_texture_flag_not_reset_by_other_edits(client, auth_headers):
    """Правка комментария не должна ронять галочку в «нет текстуры»."""
    order_id = _create_order_from_lead(client, auth_headers)
    client.patch(
        f"/api/v1/orders/{order_id}",
        json={"has_texture": True},
        headers=auth_headers,
    )

    response = client.patch(
        f"/api/v1/orders/{order_id}",
        json={"comment": "Плёнка под дерево"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["has_texture"] is True
    assert data["comment"] == "Плёнка под дерево"


def test_update_order_rejects_unknown_order(client, auth_headers):
    response = client.patch(
        f"/api/v1/orders/{uuid.uuid4()}",
        json={"has_texture": True},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_update_order_rejects_non_boolean_texture(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)

    response = client.patch(
        f"/api/v1/orders/{order_id}",
        json={"has_texture": "местами"},
        headers=auth_headers,
    )

    assert response.status_code == 422
