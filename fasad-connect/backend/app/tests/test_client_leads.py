"""Расчёты клиента в его карточке.

Заказчик: «зашла в карточку этого клиента... заказов 0, сумма 0. Вот как бы тот
случай, когда клиент просчитывается, и у него должны эти заказы, просчитанные,
сохраняться, как с пометкой на подтверждение. Потому что сейчас я сдала клиента,
2 заказа посчитала, но их здесь нет».

Правило: посчитанное и не купленное — это заявка. В выручку она не идёт, но из
карточки клиента исчезать не должна.
"""

from __future__ import annotations


def _lead_for(client, name: str, phone: str, amount: str | None = None):
    raw = {
        "quantity": 2,
        "parts": [{"width": 1000, "height": 500, "quantity": 2, "material": "RAL 9003"}],
    }
    if amount:
        raw["estimate"] = {"final_amount": amount, "currency": "RUB"}
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": f"Расчёт для {name}",
            "sender": {"full_name": name, "phone": phone},
            "raw_payload": raw,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_calculated_lead_shows_up_in_the_client_card(client, auth_headers):
    """Посчитали клиенту — расчёт виден в его карточке, а не только в заявках."""
    lead = _lead_for(client, "Ольга Расчёт", "+79990005050", amount="40000.00")

    card = client.get(f"/api/v1/clients/{lead['client']['id']}", headers=auth_headers).json()[
        "data"
    ]

    numbers = [item["lead_number"] for item in card["calculations"]]
    assert lead["lead_number"] in numbers
    row = next(item for item in card["calculations"] if item["lead_number"] == lead["lead_number"])
    assert row["estimated_amount"] == "40000.00"
    assert row["quantity"] == 2
    assert row["order_id"] is None


def test_pending_calculations_are_counted(client, auth_headers):
    """Видно, сколько расчётов ждут ответа и на какую сумму."""
    first = _lead_for(client, "Пётр Ждёт", "+79990005151", amount="10000.00")
    _lead_for(client, "Пётр Ждёт", "+79990005151", amount="25000.00")

    card = client.get(f"/api/v1/clients/{first['client']['id']}", headers=auth_headers).json()[
        "data"
    ]

    assert card["pending_calculations_count"] == 2
    assert card["pending_calculations_amount"] == "35000.00"


def test_rejected_calculation_stops_waiting(client, auth_headers):
    """Клиент отказался — расчёт больше не «ждёт ответа».

    Счётчик считался по «нет заказа», а не по статусу. Заказа по отказу не
    будет никогда, поэтому такой расчёт висел в ожидающих вечно, и закрыть его
    было нечем: менеджер видел растущую цифру, за которой ничего не стоит.
    """
    first = _lead_for(client, "Анна Отказ", "+79990005252", amount="10000.00")
    second = _lead_for(client, "Анна Отказ", "+79990005252", amount="25000.00")
    client_id = first["client"]["id"]

    before = client.get(f"/api/v1/clients/{client_id}", headers=auth_headers).json()["data"]
    assert before["pending_calculations_count"] == 2

    rejected = client.patch(
        f"/api/v1/leads/{second['id']}", json={"status": "rejected"}, headers=auth_headers
    )
    assert rejected.status_code == 200, rejected.text

    after = client.get(f"/api/v1/clients/{client_id}", headers=auth_headers).json()["data"]
    assert after["pending_calculations_count"] == 1
    assert after["pending_calculations_amount"] == "10000.00"
    # Сам расчёт из карточки не пропадает — менеджер должен помнить, что считал.
    assert len(after["calculations"]) == 2


def test_lead_status_is_written_in_russian(client, auth_headers):
    """«new» менеджеру ничего не говорит — в карточке «Ждёт ответа»."""
    lead = _lead_for(client, "Статус Тест", "+79990005252")

    card = client.get(f"/api/v1/clients/{lead['client']['id']}", headers=auth_headers).json()[
        "data"
    ]

    assert card["calculations"][0]["status_label"] == "Ждёт ответа"


def test_converted_lead_points_at_its_order(client, auth_headers):
    """Расчёт закончился делом — рядом виден номер заказа."""
    lead = _lead_for(client, "Стал Заказом", "+79990005353", amount="15000.00")
    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    card = client.get(f"/api/v1/clients/{lead['client']['id']}", headers=auth_headers).json()[
        "data"
    ]

    row = next(item for item in card["calculations"] if item["lead_number"] == lead["lead_number"])
    assert row["order_number"] == order["order_number"]
    assert row["status_label"] == "Стала заказом"
    # в «ждут ответа» такой расчёт уже не считается
    assert card["pending_calculations_count"] == 0


def test_client_without_calculations_has_empty_list(client, auth_headers):
    """У нового клиента список пуст, а не сломан."""
    created = client.post(
        "/api/v1/clients",
        json={"full_name": "Совсем Новый"},
        headers=auth_headers,
    ).json()["data"]

    card = client.get(f"/api/v1/clients/{created['id']}", headers=auth_headers).json()["data"]

    assert card["calculations"] == []
    assert card["pending_calculations_count"] == 0
    assert card["pending_calculations_amount"] == "0"
