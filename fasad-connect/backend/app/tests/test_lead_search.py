"""Поиск заявки в списке.

Заказчик: «я сейчас всё закрыла, тот же заказ я уже создала, зашла в другую
вкладку — как мне его найти? Если я захожу в заявки, в заказы — его нет, под
этим номером ничего нет».

Искали только по тексту заявки, поэтому ни номер, ни имя клиента её не
находили — а именно номер менеджер и помнит.
"""

from __future__ import annotations


def _intake(client, **sender):
    payload = {
        "source_channel": "manual_manager_input",
        "text": "Фасады на кухню, размеры уточним",
        "sender": {"full_name": "Иванова Ольга", **sender},
        "raw_payload": {},
    }
    return client.post("/api/v1/leads/intake", json=payload).json()["data"]


def _search(client, auth_headers, query: str) -> list[dict]:
    return client.get(
        "/api/v1/leads", params={"search": query, "size": 50}, headers=auth_headers
    ).json()["data"]


def test_lead_is_found_by_its_number(client, auth_headers):
    """Номер заявки — то, что менеджер помнит и вбивает первым."""
    lead = _intake(client, phone="+79990000001", email="num@example.com")
    number = lead["lead_number"]
    assert number, "заявке не присвоился номер"

    found = _search(client, auth_headers, number)

    assert [item["id"] for item in found] == [lead["id"]]


def test_lead_is_found_by_part_of_the_number(client, auth_headers):
    """Хвост номера тоже находит: «0004» вместо «З-0004»."""
    lead = _intake(client, phone="+79990000002", email="part@example.com")
    tail = lead["lead_number"].split("-")[-1]

    found = _search(client, auth_headers, tail)

    assert lead["id"] in [item["id"] for item in found]


def test_lead_is_found_by_client_name(client, auth_headers):
    """По фамилии клиента — второе, чем ищут."""
    lead = _intake(client, phone="+79990000003", email="name@example.com")

    found = _search(client, auth_headers, "иванова")

    assert lead["id"] in [item["id"] for item in found]


def test_lead_is_found_by_client_phone(client, auth_headers):
    """Клиент перезвонил — ищут по номеру телефона."""
    lead = _intake(client, phone="+79995550011", email="phone@example.com")

    found = _search(client, auth_headers, "5550011")

    assert lead["id"] in [item["id"] for item in found]


def test_search_does_not_return_everything(client, auth_headers):
    """Отбор именно отбирает: чужие заявки в выдачу не попадают."""
    mine = _intake(client, phone="+79990000004", email="mine@example.com")
    client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Совсем другая заявка",
            "sender": {"full_name": "Петров Пётр", "phone": "+79991110022"},
            "raw_payload": {},
        },
    )

    found = _search(client, auth_headers, mine["lead_number"])

    assert [item["id"] for item in found] == [mine["id"]]


def test_search_for_nothing_returns_empty(client, auth_headers):
    """Ничего не нашлось — пустой список, а не весь справочник."""
    _intake(client, phone="+79990000005", email="empty@example.com")

    assert _search(client, auth_headers, "такого-номера-нет-12345") == []
