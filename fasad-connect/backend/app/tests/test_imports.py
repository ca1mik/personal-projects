"""Загрузка списка деталей из выгрузки заказчика."""

from __future__ import annotations

import io


def blank_csv() -> bytes:
    return "Длина;Ширина;Кол-во\r\n716;396;4\r\n596;396;2\r\n".encode("cp1251")


def blank_csv_with_color() -> bytes:
    """Бланк студии: колонка «Мм» пустая, толщина написана внутри цвета."""
    return (
        "Длина;Ширина;Кол-во;Мм;Фрезеровка;Цвет\r\n"
        "716;396;4;;Фрез  рамка;Эмаль RAL 9003 плита 19мм\r\n"
        "596;396;2;;;Тадж Прага P833UP\r\n"
    ).encode("cp1251")


def upload(client, auth_headers, name: str, content: bytes):
    return client.post(
        "/api/v1/imports/parts",
        headers=auth_headers,
        files={"file": (name, io.BytesIO(content), "application/octet-stream")},
    )


def test_import_returns_parts_and_size_lines(client, auth_headers):
    response = upload(client, auth_headers, "список.csv", blank_csv())

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_quantity"] == 6
    part = data["parts"][0]
    assert (part["width"], part["height"], part["quantity"]) == (716, 396, 4)
    assert (part["thickness"], part["milling"], part["color"]) == (None, None, None)
    # строки в том же формате, что менеджер набирает руками
    assert data["size_lines"] == "716 396 4\n596 396 2"


def test_import_cleans_color_thickness_and_milling(client, auth_headers):
    """Так выглядит бланк студии: цвет чистится, толщина берётся из него же."""
    response = upload(client, auth_headers, "бланк.csv", blank_csv_with_color())

    parts = response.json()["data"]["parts"]
    assert parts[0]["color"] == "RAL 9003"
    assert parts[0]["thickness"] == "19"
    assert parts[0]["milling"] == "фрез рамка"
    # без RAL название декора остаётся целиком, толщины в нём нет
    assert parts[1]["color"] == "Тадж Прага P833UP"
    assert parts[1]["thickness"] == "19"


def test_import_keeps_original_color_and_milling_fields(client, auth_headers):
    """Исходные записи из бланка нужны менеджеру для сверки с бумагой."""
    response = upload(client, auth_headers, "бланк.csv", blank_csv_with_color())

    parts = response.json()["data"]["parts"]
    # проверяем значение, а не наличие ключа: с ключом и null тест был бы зелёным
    assert parts[0]["color_source"] == "Эмаль RAL 9003 плита 19мм"
    assert parts[0]["milling_source"] == "Фрез  рамка"
    # пустая фрезеровка продолжает значение предыдущей строки
    assert parts[1]["color_source"] == "Тадж Прага P833UP"
    assert parts[1]["milling_source"] == "Фрез  рамка"


def test_import_area_matches_the_blank_formula(client, auth_headers):
    response = upload(client, auth_headers, "список.csv", blank_csv())

    # 716*396*4 + 596*396*2 = 1.134144 + 0.472032 = 1.606176 м²
    assert response.json()["data"]["total_area_sqm"] == "1.606176"


def test_import_combines_distant_matching_sizes_and_sums_their_quantities(client, auth_headers):
    content = (
        "Длина;Ширина;Кол-во;Мм;Фрезеровка;Цвет\r\n"
        "2245;440;2;16;Арт.110;Белый софт мс\r\n"
        "805;417;1;19;Арт.128;Эвкалипт гринвуд\r\n"
        "2245;440;3;16;арт 110;Белый софт мс\r\n"
        "2245;440;1;19;Арт.110;Белый софт мс\r\n"
    ).encode("cp1251")

    response = upload(client, auth_headers, "бланк.csv", content)

    assert response.status_code == 200
    data = response.json()["data"]
    assert [(part["width"], part["height"], part["quantity"], part["thickness"],
             part["milling"], part["color"]) for part in data["parts"]] == [
        (2245, 440, 5, "16", "арт.110", "Белый софт мс"),
        (805, 417, 1, "19", "арт.128", "Эвкалипт гринвуд"),
        (2245, 440, 1, "19", "арт.110", "Белый софт мс"),
    ]
    assert data["total_quantity"] == 7
    assert data["size_lines"] == "2245 440 5\n805 417 1\n2245 440 1"


def test_import_requires_authentication(client):
    response = client.post(
        "/api/v1/imports/parts",
        files={"file": ("список.csv", io.BytesIO(blank_csv()), "text/csv")},
    )

    assert response.status_code in (401, 403)


def test_import_rejects_unknown_format(client, auth_headers):
    response = upload(client, auth_headers, "договор.pdf", b"%PDF-1.4")

    assert response.status_code == 422
    assert "pdf" in response.json()["error"]["message"].lower()


def test_import_rejects_file_without_sizes(client, auth_headers):
    content = "Клиент;Телефон\r\nИванов;+79990001122\r\n".encode("cp1251")

    response = upload(client, auth_headers, "клиенты.csv", content)

    assert response.status_code == 422
    assert "Длина" in response.json()["error"]["message"]


def test_import_rejects_empty_file(client, auth_headers):
    response = upload(client, auth_headers, "пусто.xlsx", b"")

    assert response.status_code == 422


def test_import_does_not_create_anything(client, auth_headers):
    """Разбор только показывает: заявку менеджер создаёт сам, отдельно."""
    before = len(client.get("/api/v1/leads", headers=auth_headers).json()["data"])

    upload(client, auth_headers, "список.csv", blank_csv())

    after = len(client.get("/api/v1/leads", headers=auth_headers).json()["data"])
    assert after == before


def create_lead_with_parts(client) -> str:
    """Заявка с размерами — как её кладёт форма менеджера."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "external_message_id": "blank-export-1",
            "text": "Фасады 716x396 — 4 шт.",
            "sender": {"full_name": "Агат-Сервис"},
            "raw_payload": {
                "parts": [
                    {
                        "width": 716,
                        "height": 396,
                        "quantity": 4,
                        "material": "Эмаль RAL 9003",
                        "thickness": "19",
                        "milling": "Арт 109",
                    }
                ]
            },
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_blank_xlsx_downloads_as_a_file(client, auth_headers):
    lead_id = create_lead_with_parts(client)

    response = client.get(f"/api/v1/leads/{lead_id}/blank.xlsx", headers=auth_headers)

    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    # реальный xlsx — это zip-контейнер
    assert response.content[:2] == b"PK"


def test_blank_xlsx_requires_authentication(client):
    leads_response = client.get("/api/v1/leads")
    assert leads_response.status_code in (401, 403)

    response = client.get("/api/v1/leads/00000000-0000-0000-0000-000000000001/blank.xlsx")

    assert response.status_code in (401, 403)


def test_blank_xlsx_for_unknown_lead_is_404(client, auth_headers):
    response = client.get(
        "/api/v1/leads/00000000-0000-0000-0000-0000000000ff/blank.xlsx",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_blank_file_name_survives_cyrillic(client, auth_headers):
    """Номер заявки кириллицей: имя файла едет в filename* по RFC 5987."""
    lead_id = create_lead_with_parts(client)

    response = client.get(f"/api/v1/leads/{lead_id}/blank.xlsx", headers=auth_headers)
    disposition = response.headers["content-disposition"]

    assert "filename*=UTF-8''" in disposition
    assert "%D0%97" in disposition  # «З» из номера заявки
    # запасное ASCII-имя тоже на месте — старые клиенты берут его
    assert 'filename="' in disposition
