"""Пересохранение сметы не должно терять то, что уже в ней записано.

Смета правится целиком: таблица шлёт PUT со всеми строками сразу. Значит любое
поле, которого нет в присланной строке, при каждом сохранении обнуляется — даже
если менеджер просто нажал «Сохранить», ничего не поменяв.

Так и было с артикулом и типом работ у нестандартных строк: артикул, привезённый
из заявки, стирался, а тип работ становился «прочим», и заказ задним числом
выпадал из отчёта по обработке.
"""

from __future__ import annotations


def _create_order(client, auth_headers) -> str:
    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "website_form",
            "text": "Name: Пересохранение Тест, phone +79990000123",
            "raw_payload": {"form_id": "resave-1"},
        },
    ).json()["data"]
    return client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]["id"]


def _positions(client, auth_headers, order_id: str) -> list[dict]:
    return client.get(f"/api/v1/orders/{order_id}", headers=auth_headers).json()["data"][
        "positions"
    ]


def _row(**overrides) -> dict:
    row = {
        "is_custom": True,
        "article": "128",
        "name": "Фасад плёнка touch",
        "kind": "film",
        "unit": "sqm",
        "quantity": "2",
        "width": "716",
        "height": "396",
        "unit_price": "1200.00",
    }
    row.update(overrides)
    return row


def _save(client, auth_headers, order_id: str, rows: list[dict]):
    return client.put(
        f"/api/v1/orders/{order_id}/positions",
        json={"positions": rows},
        headers=auth_headers,
    )


def test_article_survives_resave(client, auth_headers):
    """Сохранили дважды подряд — артикул на месте."""
    order_id = _create_order(client, auth_headers)
    first = _save(client, auth_headers, order_id, [_row()])
    assert first.status_code == 200, first.text
    saved = _positions(client, auth_headers, order_id)[0]
    assert saved["article"] == "128"

    # Менеджер вернулся в заказ и пересохранил смету как есть.
    again = _save(
        client,
        auth_headers,
        order_id,
        [_row(article=saved["article"], kind=saved["kind"])],
    )

    assert again.status_code == 200, again.text
    assert _positions(client, auth_headers, order_id)[0]["article"] == "128"


def test_work_kind_survives_resave(client, auth_headers):
    """Тип работ не съезжает в «прочее» — на нём стоит отчёт по обработке."""
    order_id = _create_order(client, auth_headers)
    _save(client, auth_headers, order_id, [_row()])
    saved = _positions(client, auth_headers, order_id)[0]

    _save(client, auth_headers, order_id, [_row(article=saved["article"], kind=saved["kind"])])

    assert _positions(client, auth_headers, order_id)[0]["kind"] == "film"


def test_resave_keeps_position_in_the_work_kind_report(client, auth_headers):
    """Главное последствие: заказ остаётся в отчёте по обработке.

    Отчёт считается по строкам сметы. Съехавший в «прочее» тип уводил уже
    посчитанные деньги из своей строки отчёта, и цифры менялись задним числом.
    """
    order_id = _create_order(client, auth_headers)
    _save(client, auth_headers, order_id, [_row()])
    saved = _positions(client, auth_headers, order_id)[0]
    _save(client, auth_headers, order_id, [_row(article=saved["article"], kind=saved["kind"])])

    report = client.get(
        "/api/v1/reports/work-kinds?period=all&metric=accepted", headers=auth_headers
    ).json()["data"]

    kinds = {row["kind"] for row in report["by_kind"]}
    assert "film" in kinds, f"плёнки нет в отчёте: {sorted(kinds)}"
    assert "other" not in kinds


def test_custom_row_without_article_is_allowed(client, auth_headers):
    """Артикул необязателен: доборы и гнутьё продаются без номера."""
    order_id = _create_order(client, auth_headers)

    response = _save(
        client,
        auth_headers,
        order_id,
        [_row(article=None, name="Доставка", kind="other", unit="pcs", width=None, height=None)],
    )

    assert response.status_code == 200, response.text
    assert _positions(client, auth_headers, order_id)[0]["article"] is None


def test_article_typed_by_hand_is_cleaned_on_save(client, auth_headers):
    """«арт. 128» в смете и «128» в справочнике — один артикул, не два."""
    order_id = _create_order(client, auth_headers)

    _save(client, auth_headers, order_id, [_row(article="арт. 128")])

    assert _positions(client, auth_headers, order_id)[0]["article"] == "128"
