"""Правка сохранённой заявки, её адрес, позиции и ссылка на заказ.

Заказчик: сохранённую заявку нельзя было тронуть вообще. Клиент отказался — а
заявка навсегда оставалась «новой» и висела в карточке клиента как расчёт,
который «ждёт ответа»; ошиблись в номере или в сроке — переписать нечем.

Здесь же закрыты три соседние жалобы:
* адрес, введённый в форме заявки, «принимался», но в карточке клиента не
  появлялся, и куда он делся — было не видно;
* заявка с почты не разбиралась в позиции: один сплошной текст, пустой раскрой;
* «Создать заказ» на заявке с уже созданным заказом молча отдавала старый заказ,
  а ссылки на него в карточке не было — только «заказов: 1».
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.directions.models import ProductionDirection


@pytest.fixture
def directions(db_session):
    """Направления из ТЗ. В проде их создаёт миграция 0007."""
    rows = [
        ("enamel", "Эмаль", "", 10),
        ("pvc", "ПВХ", "П", 20),
    ]
    for code, name, suffix, sort_order in rows:
        db_session.add(
            ProductionDirection(
                code=code,
                name=name,
                number_suffix=suffix,
                material_area_factor=Decimal("1.000"),
                sort_order=sort_order,
                is_active=True,
            )
        )
    db_session.commit()


def _intake(client, **overrides) -> dict:
    payload = {
        "source_channel": "manual_manager_input",
        "text": "Клиент: Ольга Ефимова, фасады",
        "sender": {"full_name": "Ольга Ефимова", "phone": "+79170000001"},
        "raw_payload": {},
    }
    payload.update(overrides)
    response = client.post("/api/v1/leads/intake", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _patch(client, auth_headers, lead_id: str, body: dict):
    return client.patch(f"/api/v1/leads/{lead_id}", json=body, headers=auth_headers)


# --- правка заявки --------------------------------------------------------


def test_manager_can_reject_a_lead(client, auth_headers):
    """Главный сценарий: клиент отказался, заявка закрывается отказом."""
    lead = _intake(client)
    assert lead["status"] == "new"

    response = _patch(client, auth_headers, lead["id"], {"status": "rejected"})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "rejected"
    # и это именно сохранилось, а не показалось в ответе
    again = client.get(f"/api/v1/leads/{lead['id']}", headers=auth_headers).json()["data"]
    assert again["status"] == "rejected"


def test_lead_number_due_date_and_direction_are_editable(client, auth_headers, directions):
    """Номер, срок и направление правятся после сохранения.

    Раньше номер писался ровно один раз при создании, и перенести в систему
    свою нумерацию задним числом было нечем.
    """
    lead = _intake(client)

    response = _patch(
        client,
        auth_headers,
        lead["id"],
        {"lead_number": "44-03", "due_date": "2026-09-03", "direction_code": "pvc"},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["lead_number"] == "44-03"
    assert data["due_date"] == "2026-09-03"
    assert data["direction"]["code"] == "pvc"


def test_editing_one_field_keeps_the_others(client, auth_headers):
    """Правят по одному полю: срок не должен обнулять номер и статус."""
    lead = _intake(client)
    _patch(client, auth_headers, lead["id"], {"status": "in_progress"})

    response = _patch(client, auth_headers, lead["id"], {"due_date": "2026-10-01"})

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "in_progress"
    assert data["lead_number"] == lead["lead_number"]


def test_unknown_status_is_refused(client, auth_headers):
    """«отклонена» русским словом или опечатка — не статус: экраны его не знают."""
    lead = _intake(client)

    response = _patch(client, auth_headers, lead["id"], {"status": "отклонена"})

    assert response.status_code == 422, response.text
    assert "отклонена" in response.text


def test_blank_lead_number_is_refused(client, auth_headers):
    """Номером заявку зовут по телефону: пустой номер — потерянная заявка."""
    lead = _intake(client)

    response = _patch(client, auth_headers, lead["id"], {"lead_number": "   "})

    assert response.status_code == 400, response.text
    assert "номер" in response.json()["error"]["message"].lower()


def test_taken_lead_number_is_refused(client, auth_headers):
    """Две заявки под одним номером — по звонку не понять, о какой речь."""
    first = _intake(client, text="Первая", sender={"full_name": "Первый"})
    second = _intake(client, text="Вторая", sender={"full_name": "Второй"})

    response = _patch(client, auth_headers, second["id"], {"lead_number": first["lead_number"]})

    assert response.status_code == 409, response.text
    assert first["lead_number"] in response.json()["error"]["message"]


def test_lead_keeps_its_own_number_on_repeat_save(client, auth_headers):
    """Сохранили форму, не меняя номер, — свой же номер не считается занятым."""
    lead = _intake(client)

    response = _patch(client, auth_headers, lead["id"], {"lead_number": lead["lead_number"]})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["lead_number"] == lead["lead_number"]


def test_direction_and_due_date_can_be_cleared(client, auth_headers, directions):
    """Направление и срок снимаются: «пока не решили» — рабочее состояние заявки.

    Пустое поле формы должно означать именно «убрать», иначе ошибочно
    выбранное направление осталось бы в заявке навсегда.
    """
    lead = _intake(client, direction_code="pvc")
    _patch(client, auth_headers, lead["id"], {"due_date": "2026-09-03"})

    response = _patch(client, auth_headers, lead["id"], {"direction_code": None, "due_date": None})

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["direction"] is None
    assert data["due_date"] is None


def test_unknown_direction_code_is_refused(client, auth_headers):
    """Направления «шпон» в справочнике нет — молча оставлять заявку без него нельзя."""
    lead = _intake(client)

    response = _patch(client, auth_headers, lead["id"], {"direction_code": "veneer"})

    assert response.status_code == 404, response.text


def test_editing_unknown_lead_returns_404(client, auth_headers):
    response = _patch(
        client,
        auth_headers,
        "00000000-0000-0000-0000-000000000000",
        {"status": "rejected"},
    )

    assert response.status_code == 404, response.text


def test_editing_requires_authorization(client):
    """Правка заявки — не публичное действие, в отличие от приёма с сайта."""
    lead = _intake(client)

    response = client.patch(f"/api/v1/leads/{lead['id']}", json={"status": "rejected"})

    assert response.status_code == 401


# --- адрес доставки -------------------------------------------------------
# Адрес живёт при заявке: доставка бывает разовой (на объект, на склад
# монтажников), и юридический адрес карточки заказчика от неё меняться не
# должен. Раньше введённый адрес просто нигде не показывался.


def test_delivery_address_is_saved_on_the_lead(client, auth_headers):
    lead = _intake(client)

    response = _patch(client, auth_headers, lead["id"], {"address": "Казань, Восстания 100, склад"})

    assert response.status_code == 200, response.text
    payload = response.json()["data"]["parsed_payload_json"]
    assert payload["address"] == "Казань, Восстания 100, склад"


def test_delivery_address_does_not_touch_the_client_card(client, auth_headers):
    """Адрес заявки не перетирает адрес карточки — и виден отдельно от него."""
    existing = client.post(
        "/api/v1/clients",
        json={"full_name": "Агат-Сервис", "phone": "+79991234567", "address": "Казань, Рахимова 8"},
        headers=auth_headers,
    ).json()["data"]
    lead = _intake(
        client,
        sender={
            "full_name": "Агат-Сервис",
            "client_id": existing["id"],
            "address": "Москва, склад на Ленина",
        },
    )

    # адрес из формы приёма остался при заявке, карточка не тронута
    assert lead["parsed_payload_json"]["address"] == "Москва, склад на Ленина"
    assert lead["client"]["address"] == "Казань, Рахимова 8"

    card = client.get(f"/api/v1/clients/{existing['id']}", headers=auth_headers).json()["data"]
    assert card["address"] == "Казань, Рахимова 8"


def test_edit_fills_an_empty_client_address(client, auth_headers):
    """Пустой адрес карточки правка заявки дописывает — как и приём.

    Интерфейс так и обещает: «в карточке клиента адреса не было — он записан
    туда же». Пока правило работало только на приёме, обещание было ложным:
    менеджер вписывал адрес в форме правки, а карточка оставалась пустой.
    """
    existing = client.post(
        "/api/v1/clients",
        json={"full_name": "Без Адреса", "phone": "+79991230000"},
        headers=auth_headers,
    ).json()["data"]
    assert not existing["address"]
    lead = _intake(
        client,
        sender={"full_name": "Без Адреса", "client_id": existing["id"]},
    )

    _patch(client, auth_headers, lead["id"], {"address": "Казань, Восстания 100"})

    card = client.get(f"/api/v1/clients/{existing['id']}", headers=auth_headers).json()["data"]
    assert card["address"] == "Казань, Восстания 100"


def test_edit_does_not_overwrite_a_filled_client_address(client, auth_headers):
    """Заполненный адрес карточки правка заявки не трогает.

    Адрес доставки бывает разовым — на объект, на склад монтажников. Менять из-за
    него юридический адрес клиента нельзя.
    """
    existing = client.post(
        "/api/v1/clients",
        json={"full_name": "С Адресом", "phone": "+79991230001", "address": "Казань, Рахимова 8"},
        headers=auth_headers,
    ).json()["data"]
    lead = _intake(client, sender={"full_name": "С Адресом", "client_id": existing["id"]})

    _patch(client, auth_headers, lead["id"], {"address": "Москва, склад на Ленина"})

    card = client.get(f"/api/v1/clients/{existing['id']}", headers=auth_headers).json()["data"]
    assert card["address"] == "Казань, Рахимова 8"
    stored = client.get(f"/api/v1/leads/{lead['id']}", headers=auth_headers).json()["data"]
    assert stored["parsed_payload_json"]["address"] == "Москва, склад на Ленина"


def test_blank_address_clears_the_lead_address(client, auth_headers):
    """Стёрли адрес в форме правки — значит адреса у заявки нет.

    Пустая строка в карточке хуже отсутствия: по ней менеджер решил бы, что
    адрес есть, просто не прочитался.
    """
    lead = _intake(
        client,
        sender={"full_name": "Ольга", "phone": "+79170000002", "address": "Казань, Рахимова 8"},
    )
    assert lead["parsed_payload_json"]["address"] == "Казань, Рахимова 8"

    response = _patch(client, auth_headers, lead["id"], {"address": "   "})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["parsed_payload_json"]["address"] is None


def test_address_is_untouched_when_it_was_not_sent(client, auth_headers):
    """Правка статуса не должна стирать адрес доставки."""
    lead = _intake(
        client,
        sender={"full_name": "Ольга", "phone": "+79170000003", "address": "Казань, Рахимова 8"},
    )

    response = _patch(client, auth_headers, lead["id"], {"status": "in_progress"})

    assert response.json()["data"]["parsed_payload_json"]["address"] == "Казань, Рахимова 8"


# --- позиции из канала ----------------------------------------------------
# Заявка с почты приходит сплошным текстом. Раньше в неё попадал только первый
# размер: карточка показывала один блок текста, площадь считалась по одной
# строке, а раскрой по такой заявке открывался пустым.


def test_sizes_from_a_letter_become_positions(client, auth_headers):
    lead = _intake(
        client,
        source_channel="email",
        subject="Расчёт фасадов",
        text="Здравствуйте! Посчитайте, пожалуйста:\n560х123 — 3 шт.\n610x120 — 5 шт.",
        sender={"full_name": "Иван", "email": "ivan@example.com"},
    )

    parts = lead["parsed_payload_json"]["raw_payload"]["parts"]
    assert parts == [
        {"width": 560, "height": 123, "quantity": 3},
        {"width": 610, "height": 120, "quantity": 5},
    ]
    # 560*123*3 + 610*120*5 = 572 640 мм² = 0.573 м²
    assert lead["summary"]["facade_area_sqm"] == "0.573"
    assert lead["summary"]["quantity"] == 8


def test_single_size_keeps_the_declared_quantity(client, auth_headers):
    """Один размер и количество отдельным полем — это одна позиция на N штук.

    Регрессия площади: разбор не должен превращать «1000x1000, 3 штуки» в одну
    деталь и занижать заявку втрое.
    """
    lead = _intake(
        client,
        text="Фасады 1000x1000",
        raw_payload={"quantity": 3, "dimensions": {"width": 1000, "height": 1000}},
    )

    parts = lead["parsed_payload_json"]["raw_payload"]["parts"]
    assert parts == [{"width": 1000, "height": 1000, "quantity": 3}]
    assert lead["summary"]["facade_area_sqm"] == "3.000"


def test_positions_from_the_form_are_not_overwritten(client, auth_headers):
    """Менеджер занёс строки руками — разбор текста в них не лезет."""
    lead = _intake(
        client,
        text="Размеры: 560x123 — 3 шт.",
        raw_payload={
            "parts": [
                {"width": 560, "height": 123, "quantity": 3, "material": "RAL 9003"},
            ]
        },
    )

    parts = lead["parsed_payload_json"]["raw_payload"]["parts"]
    assert parts == [{"width": 560, "height": 123, "quantity": 3, "material": "RAL 9003"}]


def test_letter_without_sizes_gets_no_positions(client, auth_headers):
    """«Сколько стоит покрасить фасады?» — позиций нет, выдумывать их нечем."""
    lead = _intake(
        client,
        source_channel="email",
        text="Добрый день! Сколько стоит покрасить фасады? Перезвоните на +7 917 000-00-11.",
        sender={"full_name": "Иван", "email": "ivan2@example.com"},
    )

    assert "parts" not in lead["parsed_payload_json"]["raw_payload"]
    assert lead["summary"]["quantity"] == 1


def test_phone_number_does_not_become_a_position(client, auth_headers):
    """В количество не должно уехать чужое число из строки."""
    lead = _intake(
        client,
        text="Телефон 8 917 000 00 11, нужен 1 фасад 600x400",
        sender={"full_name": "Пётр", "phone": "+79170000011"},
    )

    parts = lead["parsed_payload_json"]["raw_payload"]["parts"]
    assert parts == [{"width": 600, "height": 400, "quantity": 1}]


# --- ссылка на заказ ------------------------------------------------------


def test_lead_summary_carries_the_order_link(client, auth_headers):
    """На карточке заявки было только «заказов: 1» — перейти в заказ нечем."""
    lead = _intake(client)
    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    summary = client.get(f"/api/v1/leads/{lead['id']}", headers=auth_headers).json()["data"][
        "summary"
    ]

    assert summary["orders_count"] == 1
    assert [item["id"] for item in summary["orders"]] == [order["id"]]
    assert summary["orders"][0]["order_number"] == order["order_number"]


def test_first_create_order_reports_that_it_created(client, auth_headers):
    lead = _intake(client)

    response = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["meta"]["created"] is True


def test_repeated_create_order_says_the_order_already_existed(client, auth_headers):
    """Второй заказ по заявке не заводится — и об этом надо сказать вслух.

    Раньше повторное нажатие молча отдавало старый заказ, и менеджер считал,
    что создал новый.
    """
    lead = _intake(client)
    first = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()

    second = client.post(f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers)

    assert second.status_code == 200, second.text
    body = second.json()
    assert body["meta"]["created"] is False
    assert body["data"]["id"] == first["data"]["id"]


def test_lead_without_orders_has_an_empty_order_list(client, auth_headers):
    lead = _intake(client)

    summary = client.get(f"/api/v1/leads/{lead['id']}", headers=auth_headers).json()["data"][
        "summary"
    ]

    assert summary["orders"] == []
    assert summary["orders_count"] == 0
