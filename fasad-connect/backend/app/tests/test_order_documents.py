"""Выгрузки по заказу: коммерческое предложение и спецификация.

Заказчик открыл список файлов заказа и спросил «это что и нахуя?»: там лежали
две выгрузки по «0 КБ» с англоязычным текстом и пустой спецификацией. Тесты
фиксируют три решения — размер и тип пишутся, текст русский, спецификация
читает смету, а у заказа, в котором описывать нечего, выгрузок не появляется.
"""

from __future__ import annotations


def _create_order(client, auth_headers) -> str:
    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "website_form",
            "text": "Name: Выгрузки Тест, phone +79990000001, email docs@example.com",
            "raw_payload": {"form_id": "docs-1"},
        },
    ).json()["data"]
    return client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]["id"]


def _put_position(client, auth_headers, order_id, **overrides):
    position = {
        "is_custom": True,
        "article": "113",
        "name": "Фасад кухни",
        "kind": "milling",
        "unit": "sqm",
        "quantity": "5",
        "width": "746",
        "height": "396",
        "unit_price": "1200.00",
        "thickness": "16",
        "color": "RAL 1016",
        "milling": "артикул 113",
    }
    position.update(overrides)
    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={"positions": [position]},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response


def _calculate(client, auth_headers, order_id):
    response = client.post(f"/api/v1/orders/{order_id}/calculate", headers=auth_headers)
    assert response.status_code == 200, response.text
    return response


def _files(client, auth_headers, order_id):
    return client.get(f"/api/v1/orders/{order_id}/files", headers=auth_headers).json()["data"]


def _download(client, auth_headers, document_id):
    response = client.get(f"/api/v1/documents/{document_id}/download", headers=auth_headers)
    assert response.status_code == 200, response.text
    return response


def test_exports_carry_size_and_type(client, auth_headers):
    """Размер и тип содержимого пишутся: раньше оба поля оставались пустыми."""
    order_id = _create_order(client, auth_headers)
    _put_position(client, auth_headers, order_id)

    _calculate(client, auth_headers, order_id)

    files = _files(client, auth_headers, order_id)
    assert sorted(item["doc_type"] for item in files) == ["quote", "specification"]
    for item in files:
        assert item["content_type"] == "text/markdown; charset=utf-8"
        # Размер не просто «не ноль», а совпадает с тем, что реально отдаётся.
        content = _download(client, auth_headers, item["id"]).content
        assert item["size_bytes"] == len(content)


def test_quote_and_specification_are_russian_and_read_the_estimate(client, auth_headers):
    """Текст по-русски, а спецификация — из строк сметы, а не из старых позиций."""
    order_id = _create_order(client, auth_headers)
    _put_position(client, auth_headers, order_id)

    _calculate(client, auth_headers, order_id)

    files = {item["doc_type"]: item for item in _files(client, auth_headers, order_id)}
    quote = _download(client, auth_headers, files["quote"]["id"]).content.decode("utf-8")
    assert "Коммерческое предложение по заказу" in quote
    assert "К оплате:" in quote
    assert "Commercial quote" not in quote

    spec = _download(client, auth_headers, files["specification"]["id"]).content.decode("utf-8")
    assert "Спецификация по заказу" in spec
    assert "арт. 113" in spec
    assert "746×396 мм" in spec
    assert "цвет: RAL 1016" in spec
    assert "фрезеровка: артикул 113" in spec
    # Толщина без хвоста нулей: в базе Numeric, на бумаге «16 мм».
    assert "16 мм" in spec


def test_order_without_anything_to_describe_gets_no_exports(client, auth_headers):
    """Пустой заказ: выгрузок нет вовсе, а не два файла из одного заголовка."""
    order_id = _create_order(client, auth_headers)

    _calculate(client, auth_headers, order_id)

    assert _files(client, auth_headers, order_id) == []


def test_recalculation_does_not_pile_up_copies(client, auth_headers):
    """Пересчёт перезаписывает выгрузки, а не добавляет ещё пару к списку."""
    order_id = _create_order(client, auth_headers)
    _put_position(client, auth_headers, order_id)

    _calculate(client, auth_headers, order_id)
    _calculate(client, auth_headers, order_id)
    _calculate(client, auth_headers, order_id)

    files = _files(client, auth_headers, order_id)
    assert len(files) == 2


def test_position_without_sizes_says_so(client, auth_headers):
    """Услуга без размеров: в спецификации честная пометка, а не «0×0 мм»."""
    order_id = _create_order(client, auth_headers)
    _put_position(
        client,
        auth_headers,
        order_id,
        name="Доставка",
        kind="service",
        unit="pcs",
        quantity="1",
        width=None,
        height=None,
        thickness=None,
        color=None,
        milling=None,
        article=None,
    )

    _calculate(client, auth_headers, order_id)

    files = {item["doc_type"]: item for item in _files(client, auth_headers, order_id)}
    spec = _download(client, auth_headers, files["specification"]["id"]).content.decode("utf-8")
    assert "размер не указан" in spec
    assert "Доставка" in spec


def test_emptied_estimate_clears_stale_exports(client, auth_headers):
    """Убрали все строки и пересчитали — прошлые выгрузки не остаются висеть."""
    order_id = _create_order(client, auth_headers)
    _put_position(client, auth_headers, order_id)
    _calculate(client, auth_headers, order_id)
    assert len(_files(client, auth_headers, order_id)) == 2

    response = client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={"positions": []},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    _calculate(client, auth_headers, order_id)

    assert _files(client, auth_headers, order_id) == []
