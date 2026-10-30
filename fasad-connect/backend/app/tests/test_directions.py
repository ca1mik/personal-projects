"""Пункты 2 и 3 ТЗ заказчика.

п. 2 — заявки фиксируются как Эмаль (номер), ПВХ (номер и «П»), Шпон (номер и «Ш»).
п. 3 — карточка клиента: ФИО, организация, адрес, телефон, история заказов.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.directions.models import ProductionDirection
from app.modules.directions.service import DirectionService

DIRECTIONS = [
    ("enamel", "Эмаль", "", 10),
    ("pvc", "ПВХ", "П", 20),
    ("veneer", "Шпон", "Ш", 30),
]


@pytest.fixture
def directions(db_session):
    """Три направления из ТЗ. В проде их создаёт миграция 0007."""
    for code, name, suffix, sort_order in DIRECTIONS:
        db_session.add(
            ProductionDirection(
                code=code,
                name=name,
                number_suffix=suffix,
                sort_order=sort_order,
                is_active=True,
            )
        )
    db_session.commit()
    return DIRECTIONS


def create_client(client, auth_headers, **overrides):
    payload = {
        "full_name": "Иван Петров",
        "organization": "ООО «Мебельщик»",
        "phone": "+79991234567",
        "address": "г. Москва, ул. Производственная, 5",
    }
    payload.update(overrides)
    response = client.post("/api/v1/clients", headers=auth_headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def manager_id(client, auth_headers):
    users = client.get("/api/v1/admin/users?page=1&size=10", headers=auth_headers).json()["data"]
    return users[0]["id"]


# --- нумерация по направлениям (п. 2) --------------------------------------


def test_order_number_carries_direction_letter(client, auth_headers, directions):
    created = create_client(client, auth_headers)
    manager = manager_id(client, auth_headers)

    numbers = {}
    for code in ("enamel", "pvc", "veneer"):
        response = client.post(
            "/api/v1/orders",
            headers=auth_headers,
            json={
                "client_id": created["id"],
                "manager_id": manager,
                "direction_code": code,
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        numbers[code] = data["order_number"]
        assert data["direction"]["code"] == code

    assert numbers["enamel"].isdigit()
    assert numbers["pvc"].endswith("-П")
    assert numbers["veneer"].endswith("-Ш")


def test_order_keeps_manually_entered_digits_and_adds_direction_letter(
    client, auth_headers, directions
):
    created = create_client(client, auth_headers)
    manager = manager_id(client, auth_headers)
    response = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "client_id": created["id"],
            "manager_id": manager,
            "direction_code": "pvc",
            "order_number": "004666п",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["order_number"] == "004666-П"


@pytest.mark.parametrize(('manual','expected'),[('4666','4666-Ш'),('004666п','004666-Ш'),('АБ-007','АБ-007')])
def test_order_from_lead_uses_manual_lead_digits_and_direction(
    client, auth_headers, directions, manual, expected
):
    lead_response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "lead_number": manual,
            "direction_code": "veneer",
            "text": "Клиент: Студия, фасады",
            "sender": {"full_name": "Студия", "email": "manual-number@example.com"},
            "raw_payload": {},
        },
    )
    assert lead_response.status_code == 200, lead_response.text
    lead = lead_response.json()["data"]
    response = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["order_number"] == expected
    assert lead["lead_number"] == manual


@pytest.mark.parametrize(('direction','kind','expected'),[
    ('enamel','paint','004403'),('pvc','milling','004403-П'),
    ('veneer','soap','004403-Ш'),('enamel','milling','004403'),
    ('enamel','soap','004403'),('enamel','film','004403'),
])
def test_manual_digits_survive_conversion_with_work_letter(client,auth_headers,directions,direction,kind,expected):
    response=client.post('/api/v1/leads/intake',json={
        'source_channel':'manual_manager_input','lead_number':'004403','direction_code':direction,
        'text':'Фасады','sender':{'full_name':'Студия','email':'letters@example.com'},
        'raw_payload':{'parts':[{'length':'720','width':'400','quantity':'1','kind':kind}]},
    })
    assert response.status_code==200,response.text
    lead=response.json()['data']
    response=client.post(f"/api/v1/leads/{lead['id']}/create-order",json={},headers=auth_headers)
    assert response.status_code==200,response.text
    assert response.json()['data']['order_number']==expected


def test_order_numbers_are_unique_across_directions(client, auth_headers, directions):
    created = create_client(client, auth_headers)
    manager = manager_id(client, auth_headers)

    seen = set()
    for code in ("enamel", "pvc", "veneer", "enamel", "pvc"):
        response = client.post(
            "/api/v1/orders",
            headers=auth_headers,
            json={"client_id": created["id"], "manager_id": manager, "direction_code": code},
        )
        number = response.json()["data"]["order_number"]
        assert number not in seen, f"номер {number} выдан дважды"
        seen.add(number)


def test_order_without_direction_gets_plain_number(client, auth_headers, directions):
    created = create_client(client, auth_headers)
    manager = manager_id(client, auth_headers)

    response = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"client_id": created["id"], "manager_id": manager},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["order_number"].isdigit()
    assert data["direction"] is None


def test_unknown_direction_code_is_rejected(client, auth_headers, directions):
    created = create_client(client, auth_headers)
    manager = manager_id(client, auth_headers)

    response = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "client_id": created["id"],
            "manager_id": manager,
            "direction_code": "laminate",
        },
    )

    assert response.status_code == 404
    assert "laminate" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    ("suffix", "expected"),
    [("", "0007"), ("П", "0007-П"), ("Ш", "0007-Ш")],
)
def test_number_format(suffix, expected):
    direction = ProductionDirection(code="x", name="X", number_suffix=suffix)
    assert DirectionService.format_order_number(7, direction) == expected


# --- заявки (п. 2) ---------------------------------------------------------


def test_manual_intake_accepts_direction(client, auth_headers, directions):
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "external_message_id": "manual-dir-1",
            "text": "Фасады ПВХ 716x396, 12 шт",
            "direction_code": "pvc",
            "sender": {"full_name": "Пётр Сидоров", "phone": "+79995554433"},
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["direction"]["name"] == "ПВХ"


def test_manager_sets_direction_on_email_lead(client, auth_headers, directions):
    """Письмо приходит без направления — менеджер выставляет его после прочтения."""
    intake = client.post(
        "/api/v1/messaging/email/intake",
        json={
            "message_id": "dir-mail-1",
            "subject": "Фасады под эмаль",
            "from_name": "Анна",
            "from_email": "anna@example.com",
            "body_text": "Нужны фасады 700x400 под эмаль, 20 шт",
        },
    )
    lead_id = intake.json()["data"]["id"]
    assert intake.json()["data"]["direction"] is None

    updated = client.patch(
        f"/api/v1/leads/{lead_id}",
        headers=auth_headers,
        json={"direction_code": "enamel"},
    )

    assert updated.status_code == 200
    assert updated.json()["data"]["direction"]["code"] == "enamel"


def test_order_inherits_direction_from_lead(client, auth_headers, directions):
    intake = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "external_message_id": "manual-dir-2",
            "text": "Шпон дуб, 8 фасадов",
            "direction_code": "veneer",
            "sender": {"full_name": "Ольга", "phone": "+79997778899"},
        },
    )
    lead_id = intake.json()["data"]["id"]

    order = client.post(f"/api/v1/leads/{lead_id}/create-order", json={}, headers=auth_headers)

    assert order.status_code == 200
    data = order.json()["data"]
    assert data["direction"]["code"] == "veneer"
    assert data["order_number"].endswith("-Ш")


def test_leads_filter_by_direction(client, auth_headers, directions):
    for index, code in enumerate(("pvc", "enamel", "pvc")):
        client.post(
            "/api/v1/leads/intake",
            json={
                "source_channel": "manual_manager_input",
                "external_message_id": f"filter-{index}",
                "text": "Фасады",
                "direction_code": code,
                "sender": {"full_name": f"Клиент {index}", "phone": f"+7999000000{index}"},
            },
        )

    response = client.get("/api/v1/leads?page=1&size=20&direction_code=pvc", headers=auth_headers)

    assert response.status_code == 200
    leads = response.json()["data"]
    assert len(leads) == 2
    assert {lead["direction"]["code"] for lead in leads} == {"pvc"}


# --- карточка клиента (п. 3) ----------------------------------------------


def test_client_card_has_organization_and_order_history(client, auth_headers, directions):
    created = create_client(client, auth_headers)
    manager = manager_id(client, auth_headers)

    for code in ("enamel", "pvc"):
        order = client.post(
            "/api/v1/orders",
            headers=auth_headers,
            json={"client_id": created["id"], "manager_id": manager, "direction_code": code},
        ).json()["data"]
        client.post(
            f"/api/v1/orders/{order['id']}/items",
            headers=auth_headers,
            json={
                "item_type": "facade",
                "name": "Фасад",
                "width": "716",
                "height": "396",
                "depth": "16",
                "quantity": 4,
            },
        )

    response = client.get(f"/api/v1/clients/{created['id']}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["organization"] == "ООО «Мебельщик»"
    assert data["address"].startswith("г. Москва")
    assert data["totals"]["orders_count"] == 2
    assert data["totals"]["days_since_last_order"] == 0
    assert len(data["order_history"]) == 2

    entry = data["order_history"][0]
    assert entry["direction_name"] in {"Эмаль", "ПВХ"}
    assert entry["items_count"] == 1
    assert "716×396" in entry["items_summary"]
    assert entry["status_name"]


def test_client_without_orders_has_empty_totals(client, auth_headers):
    created = create_client(client, auth_headers, full_name="Новый Клиент")

    data = client.get(f"/api/v1/clients/{created['id']}", headers=auth_headers).json()["data"]

    assert data["order_history"] == []
    assert data["totals"]["orders_count"] == 0
    assert Decimal(data["totals"]["total_amount"]) == Decimal("0")
    assert data["totals"]["days_since_last_order"] is None


def test_client_search_covers_organization(client, auth_headers):
    create_client(client, auth_headers, full_name="Сергей Кузнецов", organization="ИП Кузнецов")
    create_client(client, auth_headers, full_name="Мария Орлова", organization="ООО «Фасады»")

    response = client.get("/api/v1/clients?page=1&size=20&search=кузнецов", headers=auth_headers)

    assert response.status_code == 200
    names = [item["full_name"] for item in response.json()["data"]]
    assert names == ["Сергей Кузнецов"]


def test_client_update_sets_organization(client, auth_headers):
    created = create_client(client, auth_headers, organization=None)

    response = client.patch(
        f"/api/v1/clients/{created['id']}",
        headers=auth_headers,
        json={"organization": "ООО «Новая мебель»"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["organization"] == "ООО «Новая мебель»"


# --- справочник направлений -----------------------------------------------


def test_directions_list_is_sorted_and_active_filtered(
    client, auth_headers, directions, db_session
):
    db_session.add(
        ProductionDirection(
            code="acrylic", name="Акрил", number_suffix="А", sort_order=40, is_active=False
        )
    )
    db_session.commit()

    everything = client.get("/api/v1/directions", headers=auth_headers).json()["data"]
    only_active = client.get("/api/v1/directions?only_active=true", headers=auth_headers).json()[
        "data"
    ]

    assert [item["name"] for item in everything] == ["Эмаль", "ПВХ", "Шпон", "Акрил"]
    assert [item["name"] for item in only_active] == ["Эмаль", "ПВХ", "Шпон"]


def test_duplicate_direction_letter_is_rejected(client, auth_headers, directions):
    response = client.post(
        "/api/v1/directions",
        headers=auth_headers,
        json={"code": "pvc_matte", "name": "ПВХ матовый", "number_suffix": "П"},
    )

    assert response.status_code == 409
    assert "ПВХ" in response.json()["error"]["message"]


def test_duplicate_direction_code_is_rejected(client, auth_headers, directions):
    response = client.post(
        "/api/v1/directions",
        headers=auth_headers,
        json={"code": "pvc", "name": "ПВХ дубль", "number_suffix": "Д"},
    )

    assert response.status_code == 409


# --- выбор направления в форме заявки (P0-4) --------------------------------
#
# Форма приёма берёт список из `/price-book/options` и шлёт выбранный код в
# `direction_code`. Раньше там были коды типов работ («paint», «film»), приём
# заявки их не знал, и направление не проставлялось вообще: все отборы и отчёты
# по направлениям выходили пустыми.


def production_options(client, auth_headers) -> list[dict]:
    response = client.get("/api/v1/price-book/options", headers=auth_headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]["production_kinds"]


def test_intake_accepts_every_production_option(client, auth_headers, directions):
    options = production_options(client, auth_headers)

    assert [item["code"] for item in options] == ["enamel", "pvc", "veneer"]
    for index, option in enumerate(options):
        response = client.post(
            "/api/v1/leads/intake",
            json={
                "source_channel": "manual_manager_input",
                "external_message_id": f"option-{index}",
                "text": "Фасады 716x396, 12 шт",
                "direction_code": option["code"],
                "sender": {"full_name": f"Клиент {index}", "phone": f"+7999111000{index}"},
            },
        )

        assert response.status_code == 200, response.text
        assert response.json()["data"]["direction"]["code"] == option["code"]


def test_production_option_kind_is_a_real_price_book_kind(client, auth_headers, directions):
    """Артикул из заявки заводится в прайсе под этим типом — он должен там быть."""
    data = client.get("/api/v1/price-book/options", headers=auth_headers).json()["data"]
    known = {item["code"] for item in data["kinds"]}

    for option in data["production_kinds"]:
        assert option["kind"] in known


def test_price_kind_code_is_not_accepted_as_direction(client, auth_headers, directions):
    """Старый код типа работ направлением не считается — иначе молчаливая потеря."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "external_message_id": "kind-as-direction",
            "text": "Фасады",
            "direction_code": "film",
            "sender": {"full_name": "Клиент", "phone": "+79991110009"},
        },
    )

    assert response.status_code == 404
    assert "film" in response.json()["error"]["message"]


def test_intake_without_direction_still_works(client, auth_headers, directions):
    """Направление необязательно: письмо приходит без него, меняют потом."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "external_message_id": "no-direction",
            "text": "Фасады",
            "direction_code": None,
            "sender": {"full_name": "Клиент", "phone": "+79991110008"},
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["direction"] is None
