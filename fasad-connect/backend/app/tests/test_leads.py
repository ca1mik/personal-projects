from __future__ import annotations


def test_lead_intake(client):
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "website_form",
            "text": "Name: Ivan Petrov, phone +79991234567, email ivan@example.com, wardrobe 1200x2400x600",
            "raw_payload": {"form_id": "site-1"},
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "new"
    assert data["client"]["email"] == "ivan@example.com"
    assert data["parsed_payload_json"]["dimensions"]["width"] == 1200


def test_create_order_from_lead(client, auth_headers):
    lead_response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Client: Maria Ivanova, email maria@example.com, kitchen 800x720x560",
            "raw_payload": {"manager": "crm"},
        },
    )
    lead_id = lead_response.json()["data"]["id"]

    response = client.post(f"/api/v1/leads/{lead_id}/create-order", json={}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["source_lead_id"] == lead_id
    # Формат номера задан ТЗ заказчика: эмаль — «0001», ПВХ — «0001-П», шпон — «0001-Ш».
    # Заявка без направления даёт номер без буквы.
    assert data["order_number"].isdigit()
    assert data["direction"] is None
    # Комментарий заявки должен перейти в заказ как есть — раньше здесь
    # писалась техническая строка "Заказ из заявки {uuid}", и реальный текст
    # клиента/менеджера при конвертации терялся безвозвратно.
    assert data["comment"] == "Client: Maria Ivanova, email maria@example.com, kitchen 800x720x560"


# --- номер заявки ---------------------------------------------------------
# Менеджер называет номер клиенту по телефону, поэтому он нужен человеческий,
# а не UUID. Нумерация своя, не общая с заказами.


def test_lead_gets_human_number(client):
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Пётр, фасады 560x123",
            "raw_payload": {},
        },
    )

    assert response.status_code == 200
    number = response.json()["data"]["lead_number"]
    assert number is not None
    assert number.startswith("З-")
    assert len(number) == 6  # «З-» плюс четыре цифры


def test_lead_takes_the_number_manager_typed(client):
    """Заказчик ведёт свои номера заявок, подменять их системными нельзя."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "lead_number": "44-03",
            "text": "Клиент: Пётр",
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["lead_number"] == "44-03"


def test_blank_lead_number_is_generated(client):
    """Поле не заполнили — нумерация работает как раньше."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "lead_number": "   ",
            "text": "Клиент: Пётр",
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["lead_number"].startswith("З-")


def test_duplicate_lead_number_is_refused(client):
    """Две заявки с одним номером — по звонку клиента не понять, о какой речь."""
    first = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "lead_number": "77-01",
            "text": "Первая",
            "raw_payload": {},
        },
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "lead_number": "77-01",
            "text": "Вторая",
            "raw_payload": {},
        },
    )

    assert second.status_code == 409, second.text
    assert "77-01" in second.json()["error"]["message"]


def test_lead_numbers_do_not_repeat(client):
    numbers = []
    for index in range(3):
        response = client.post(
            "/api/v1/leads/intake",
            json={
                "source_channel": "website_form",
                "external_message_id": f"form-number-{index}",
                "text": f"Заявка номер {index}",
                "raw_payload": {},
            },
        )
        assert response.status_code == 200
        numbers.append(response.json()["data"]["lead_number"])

    assert len(set(numbers)) == 3


def test_next_number_preview_matches_what_intake_actually_assigns(client, auth_headers):
    """Подсказка номера — то самое число, что реально встанет при сохранении.

    Заказчик: «чтобы дважды не заносили предыдущие номера» — менеджер
    подглядывал последний номер в списке руками. Подсказка должна совпасть с
    результатом, а не просто быть похожей на него.
    """
    preview = client.get("/api/v1/leads/next-number", headers=auth_headers)
    assert preview.status_code == 200, preview.text
    predicted = preview.json()["data"]["next_number"]

    created = client.post(
        "/api/v1/leads/intake",
        json={"source_channel": "manual_manager_input", "text": "Пустой номер", "raw_payload": {}},
    ).json()["data"]

    assert created["lead_number"] == predicted


def test_next_number_preview_advances_after_a_lead_is_created(client, auth_headers):
    """После создания заявки подсказка уходит вперёд, а не остаётся прежней."""
    first = client.get("/api/v1/leads/next-number", headers=auth_headers).json()["data"][
        "next_number"
    ]
    client.post(
        "/api/v1/leads/intake",
        json={"source_channel": "manual_manager_input", "text": "Ещё одна", "raw_payload": {}},
    )
    second = client.get("/api/v1/leads/next-number", headers=auth_headers).json()["data"][
        "next_number"
    ]

    assert first != second


def test_next_number_preview_requires_auth(client):
    response = client.get("/api/v1/leads/next-number")
    assert response.status_code == 401


def test_client_placeholder_name_is_russian(client):
    """Без имени клиента в базу шло «Client from manual_manager_input»."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Нужны фасады, размеры уточню позже",
            "raw_payload": {},
        },
    )

    assert response.status_code == 200
    full_name = response.json()["data"]["client"]["full_name"]
    assert full_name == "Клиент без имени"
    assert "Client" not in full_name


# --- сводка заявки -------------------------------------------------------


def test_lead_summary_counts_area_from_parts(client, auth_headers):
    """Площадь считается по разобранным размерам: 560x123 в трёх штуках."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Пётр\nРазмеры:\n560x123 — 3 шт.",
            "raw_payload": {
                "quantity": 3,
                "dimensions": {"width": 560, "height": 123},
                "parts": [{"width": 560, "height": 123, "quantity": 3}],
            },
        },
    )
    lead_id = response.json()["data"]["id"]

    detail = client.get(f"/api/v1/leads/{lead_id}", headers=auth_headers)

    assert detail.status_code == 200
    summary = detail.json()["data"]["summary"]
    assert summary["quantity"] == 3
    # 560 * 123 * 3 / 1 000 000 = 0.20664 -> 0.207
    assert summary["facade_area_sqm"] == "0.207"
    assert summary["estimated_amount"] is None
    assert summary["orders_count"] == 0


def test_lead_summary_doubles_material_area_for_pvc(client, auth_headers, db_session):
    """У ПВХ плёнка клеится с двух сторон: материала вдвое больше фасадов."""
    from decimal import Decimal

    from app.modules.directions.models import ProductionDirection

    # в проде направления создаёт миграция 0007, в тестах создаём сами
    db_session.add(
        ProductionDirection(
            code="pvc",
            name="ПВХ",
            number_suffix="П",
            material_area_factor=Decimal("2.000"),
            sort_order=2,
            is_active=True,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "direction_code": "pvc",
            "text": "ПВХ фасады 1000x1000",
            "raw_payload": {"quantity": 1, "dimensions": {"width": 1000, "height": 1000}},
        },
    )
    assert response.status_code == 200, response.text
    lead_id = response.json()["data"]["id"]

    summary = client.get(f"/api/v1/leads/{lead_id}", headers=auth_headers).json()["data"]["summary"]

    assert summary["facade_area_sqm"] == "1.000"
    assert summary["material_area_sqm"] == "2.000"


def test_lead_summary_prefers_existing_estimate(client, auth_headers):
    """Если расчёт уже был, берём его цифры, а не пересчитываем сами."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "catalog_demo",
            "text": "Расчёт по справочнику",
            "raw_payload": {
                "quantity": 1,
                "dimensions": {"width": 600, "height": 1800},
                "estimate": {
                    "area_sqm": "1.080",
                    "material_area_sqm": "2.187",
                    "final_amount": "16541.98",
                    "currency": "RUB",
                },
            },
        },
    )
    lead_id = response.json()["data"]["id"]

    summary = client.get(f"/api/v1/leads/{lead_id}", headers=auth_headers).json()["data"]["summary"]

    assert summary["facade_area_sqm"] == "1.080"
    assert summary["material_area_sqm"] == "2.187"
    assert summary["estimated_amount"] == "16541.98"


def test_lead_summary_survives_broken_payload(client, auth_headers):
    """Мусор в размерах не должен ломать карточку заявки."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "webhook",
            "text": "Заявка без размеров",
            "raw_payload": {"quantity": "много", "dimensions": {"width": "нет", "height": None}},
        },
    )
    lead_id = response.json()["data"]["id"]

    detail = client.get(f"/api/v1/leads/{lead_id}", headers=auth_headers)

    assert detail.status_code == 200
    summary = detail.json()["data"]["summary"]
    assert summary["quantity"] == 1
    assert summary["facade_area_sqm"] == "0.000"


def test_lead_summary_shows_money_after_order_is_created(client, auth_headers):
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Ольга, фасады 800x600",
            "raw_payload": {"quantity": 1, "dimensions": {"width": 800, "height": 600}},
        },
    )
    lead_id = response.json()["data"]["id"]

    order = client.post(
        f"/api/v1/leads/{lead_id}/create-order",
        headers=auth_headers,
        json={},
    )
    assert order.status_code == 200

    summary = client.get(f"/api/v1/leads/{lead_id}", headers=auth_headers).json()["data"]["summary"]

    assert summary["orders_count"] == 1


def test_lead_summary_sums_area_over_all_positions(client, auth_headers):
    """Разные размеры в одной заявке складываются, а не берутся по первому.

    Регрессия: площадь считалась как «первый размер × общее количество», и для
    двух позиций 560x123x3 и 610x120x5 выходило 0.551 м² вместо 0.573 м².
    """
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Размеры: 560x123 — 3 шт., 610x120 — 5 шт.",
            "raw_payload": {
                "quantity": 8,
                "dimensions": {"width": 560, "height": 123},
                "parts": [
                    {"width": 560, "height": 123, "quantity": 3},
                    {"width": 610, "height": 120, "quantity": 5},
                ],
            },
        },
    )
    lead_id = response.json()["data"]["id"]

    summary = client.get(f"/api/v1/leads/{lead_id}", headers=auth_headers).json()["data"]["summary"]

    # 560*123*3 + 610*120*5 = 206 640 + 366 000 = 572 640 мм² = 0.573 м²
    assert summary["facade_area_sqm"] == "0.573"
    assert summary["quantity"] == 8


# --- подсказка клиента в форме заявки -------------------------------------
# Менеджер набирал имя заново на каждой заявке, и один заказчик расползался
# по базе как «Агат-Сервис», «агат сервис» и «ООО Агат». Подсказка тянет
# совпадения из базы тем же поиском, что и список клиентов.


def _add_client(client, auth_headers, **fields) -> dict:
    response = client.post("/api/v1/clients", json=fields, headers=auth_headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _suggest(client, auth_headers, term: str):
    response = client.get(
        "/api/v1/clients", params={"search": term, "size": 8}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_client_suggestions_find_by_name_and_organization(client, auth_headers):
    _add_client(
        client,
        auth_headers,
        full_name="Агат-Сервис",
        organization="ООО Агат",
        phone="+7 999 123-45-67",
    )
    _add_client(client, auth_headers, full_name="Берёзка", organization="ИП Смирнов")

    by_name = _suggest(client, auth_headers, "ага")
    by_organization = _suggest(client, auth_headers, "ооо аг")

    assert [item["full_name"] for item in by_name] == ["Агат-Сервис"]
    assert [item["full_name"] for item in by_organization] == ["Агат-Сервис"]
    # В подсказку подставляются телефон и организация, поэтому они должны прийти
    assert by_name[0]["phone"] == "+7 999 123-45-67"
    assert by_name[0]["organization"] == "ООО Агат"


def test_client_suggestions_find_phone_written_in_another_format(client, auth_headers):
    """«8999…» должно находить клиента, записанного как «+7 999 123-45-67»."""
    _add_client(client, auth_headers, full_name="Агат-Сервис", phone="+7 999 123-45-67")

    found = _suggest(client, auth_headers, "89991234567")

    assert [item["full_name"] for item in found] == ["Агат-Сервис"]


def test_client_suggestions_require_authorization(client):
    response = client.get("/api/v1/clients", params={"search": "ага"})

    assert response.status_code == 401


def test_client_suggestions_empty_for_unknown_term(client, auth_headers):
    _add_client(client, auth_headers, full_name="Агат-Сервис", phone="+79991234567")

    found = _suggest(client, auth_headers, "щщщ")

    assert found == []


def test_client_suggestions_do_not_match_foreign_phone(client, auth_headers):
    """Похожий, но чужой номер не должен подставляться менеджеру как «тот самый»."""
    _add_client(client, auth_headers, full_name="Агат-Сервис", phone="+79991234567")

    found = _suggest(client, auth_headers, "89997654321")

    assert found == []


def test_lead_binds_to_client_picked_from_base(client, auth_headers):
    """Выбрал клиента в подсказке — заявка легла на него, дубля не завелось."""
    existing = _add_client(
        client,
        auth_headers,
        full_name="Агат-Сервис",
        organization="ООО Агат",
        phone="+7 999 123-45-67",
    )

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат-Сервис\nТелефон: +7 999 123-45-67",
            "sender": {
                "full_name": "Агат-Сервис",
                "phone": "+7 999 123-45-67",
                "client_id": existing["id"],
            },
            "raw_payload": {"client_id": existing["id"]},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["id"] == existing["id"]
    assert len(_suggest(client, auth_headers, "агат")) == 1


def test_lead_binds_to_picked_client_without_contacts(client, auth_headers):
    """Клиента выбрали из базы, а телефона и почты в карточке нет.

    Регрессия: форма присылала id, но сервер его не читал и узнавал клиента
    только по контактам — на «Агат-Сервис» без телефона заводился дубль.
    """
    existing = _add_client(client, auth_headers, full_name="Агат-Сервис")

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат-Сервис",
            "sender": {"full_name": "Агат-Сервис", "client_id": existing["id"]},
            "raw_payload": {"client_id": existing["id"]},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["id"] == existing["id"]
    assert len(_suggest(client, auth_headers, "агат")) == 1


def test_lead_picked_client_wins_over_contacts_of_another(client, auth_headers):
    """Выбор менеджера важнее совпадения по телефону: заявка на выбранного."""
    picked = _add_client(client, auth_headers, full_name="Агат-Сервис")
    other = _add_client(client, auth_headers, full_name="Берёзка", phone="+79991234567")

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат-Сервис",
            "sender": {
                "full_name": "Агат-Сервис",
                "phone": "+7 999 123-45-67",
                "client_id": picked["id"],
            },
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    got = response.json()["data"]["client"]["id"]
    assert got == picked["id"]
    assert got != other["id"]


def test_lead_survives_client_id_of_deleted_card(client, auth_headers):
    """Карточку удалили, пока менеджер набирал заявку — заявка не должна падать."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат-Сервис",
            "sender": {
                "full_name": "Агат-Сервис",
                "phone": "+79990000001",
                "client_id": "00000000-0000-0000-0000-000000000000",
            },
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["full_name"] == "Агат-Сервис"


def test_lead_rejects_broken_client_id(client, auth_headers):
    """Не-UUID в client_id — понятная ошибка валидации, а не 500."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат-Сервис",
            "sender": {"full_name": "Агат-Сервис", "client_id": "не-uuid"},
            "raw_payload": {},
        },
    )

    assert response.status_code == 422


def test_lead_binds_to_client_when_phone_format_differs(client, auth_headers):
    """Номер того же клиента в другой записи не должен плодить второго."""
    existing = _add_client(client, auth_headers, full_name="Агат-Сервис", phone="+7 999 123-45-67")

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: агат сервис",
            "sender": {"full_name": "агат сервис", "phone": "8 (999) 123-45-67"},
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["id"] == existing["id"]


def test_lead_binds_to_client_by_email_in_other_case(client, auth_headers):
    existing = _add_client(
        client, auth_headers, full_name="Агат-Сервис", email="zakaz@agat.example"
    )

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат",
            "sender": {"full_name": "Агат", "email": "Zakaz@Agat.example"},
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["id"] == existing["id"]


def test_lead_creates_new_client_when_nothing_was_picked(client, auth_headers):
    """Менеджер набрал своё, не глядя на подсказку — заводится новый клиент."""
    existing = _add_client(client, auth_headers, full_name="Агат-Сервис", phone="+79991234567")

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Новый заказчик",
            "sender": {"full_name": "Новый заказчик", "phone": "+79990000000"},
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    created = response.json()["data"]["client"]
    assert created["id"] != existing["id"]
    assert created["full_name"] == "Новый заказчик"


# --- адрес клиента --------------------------------------------------------
# Заказчик: «адрес клиента не вижу куда вбивать». Поле в карточке было, а
# занести его при приёме заявки было негде — менеджер писал адрес в примечание,
# и в карточке он не оказывался.


def test_lead_saves_client_address(client):
    """Адрес из формы заявки попадает в карточку нового клиента."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Ольга Ефимова",
            "sender": {
                "full_name": "Ольга Ефимова",
                "phone": "+79170000001",
                "address": "Казань, Рахимова 8, корп. 1",
            },
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["address"] == "Казань, Рахимова 8, корп. 1"


def test_lead_fills_address_when_card_had_none(client, auth_headers):
    """У клиента без адреса он дописывается из заявки."""
    existing = _add_client(client, auth_headers, full_name="Агат-Сервис", phone="+79991234567")
    assert existing["address"] is None

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат-Сервис",
            "sender": {
                "full_name": "Агат-Сервис",
                "client_id": existing["id"],
                "address": "Казань, Восстания 100",
            },
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["address"] == "Казань, Восстания 100"


def test_lead_does_not_overwrite_filled_address(client, auth_headers):
    """Заполненный адрес карточки заявка не перетирает.

    Иначе разовая доставка на другой объект молча заменила бы юридический
    адрес заказчика, и никто бы не заметил.
    """
    existing = _add_client(
        client,
        auth_headers,
        full_name="Агат-Сервис",
        phone="+79991234567",
        address="Казань, Рахимова 8",
    )

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат-Сервис",
            "sender": {
                "full_name": "Агат-Сервис",
                "client_id": existing["id"],
                "address": "Москва, склад на Ленина",
            },
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["address"] == "Казань, Рахимова 8"


def test_blank_address_does_not_touch_card(client, auth_headers):
    """Пробелы вместо адреса не должны заменять адрес на пустую строку."""
    existing = _add_client(
        client,
        auth_headers,
        full_name="Агат-Сервис",
        phone="+79991234567",
        address="Казань, Рахимова 8",
    )

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат-Сервис",
            "sender": {
                "full_name": "Агат-Сервис",
                "client_id": existing["id"],
                "address": "   ",
            },
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["address"] == "Казань, Рахимова 8"


def test_lead_saves_client_organization(client):
    """Организация из формы «Рабочее место» попадает в карточку нового клиента.

    Раньше поле уходило только текстом внутрь заявки (в примечание), а
    структурированно в карточку клиента не долетало вовсе.
    """
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Ольга Ефимова",
            "sender": {
                "full_name": "Ольга Ефимова",
                "phone": "+79170000002",
                "organization": "ООО Ромашка",
            },
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["organization"] == "ООО Ромашка"


def test_lead_fills_organization_when_card_had_none(client, auth_headers):
    """У клиента без организации она дописывается из заявки — как с адресом."""
    existing = _add_client(client, auth_headers, full_name="Агат-Сервис", phone="+79991234568")
    assert existing["organization"] is None

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат-Сервис",
            "sender": {
                "full_name": "Агат-Сервис",
                "client_id": existing["id"],
                "organization": "ИП Агатова",
            },
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["organization"] == "ИП Агатова"


def test_lead_does_not_overwrite_filled_organization(client, auth_headers):
    """Заполненную организацию карточки заявка не перетирает."""
    existing = _add_client(
        client,
        auth_headers,
        full_name="Агат-Сервис",
        phone="+79991234569",
        organization="ООО Агат",
    )

    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Агат-Сервис",
            "sender": {
                "full_name": "Агат-Сервис",
                "client_id": existing["id"],
                "organization": "Случайно другое юрлицо",
            },
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["organization"] == "ООО Агат"


def test_lead_without_organization_keeps_card_empty(client):
    """Организацию не назвали — карточка остаётся пустой, без выдумки."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "email",
            "text": "Здравствуйте, посчитайте фасады 560x123",
            "sender": {"full_name": "Иван", "email": "ivan2@example.com"},
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["organization"] is None


def test_lead_without_address_keeps_card_empty(client):
    """Из письма адрес не приходит — карточка остаётся без адреса, без пустых строк."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "email",
            "text": "Здравствуйте, посчитайте фасады 560x123",
            "sender": {"full_name": "Иван", "email": "ivan@example.com"},
            "raw_payload": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["client"]["address"] is None


# --- свой номер заказа ----------------------------------------------------
# Заказчик вводит цифры вручную; букву заказа определяет направление/тип работ.
# Пусто и отсутствие ручного номера у заявки оставляют автоматический счётчик.


def _lead_for_order(client, email: str) -> str:
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Клиент: Студия",
            "sender": {"full_name": "Студия фасадов", "email": email},
            "raw_payload": {},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_order_takes_manual_number(client, auth_headers):
    """Названный менеджером номер попадает в заказ как есть."""
    lead_id = _lead_for_order(client, "num1@example.com")

    response = client.post(
        f"/api/v1/leads/{lead_id}/create-order",
        json={"order_number": "44 03 п"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["order_number"] == "44 03 п"


def test_empty_number_still_generated_automatically(client, auth_headers):
    """Поле не заполнили — нумерация работает как раньше."""
    lead_id = _lead_for_order(client, "num2@example.com")

    response = client.post(f"/api/v1/leads/{lead_id}/create-order", json={}, headers=auth_headers)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["order_number"].isdigit()


def test_blank_number_does_not_create_nameless_order(client, auth_headers):
    """Пробелы вместо номера — не номер: заказ без номера в цеху не найти."""
    lead_id = _lead_for_order(client, "num3@example.com")

    response = client.post(
        f"/api/v1/leads/{lead_id}/create-order",
        json={"order_number": "   "},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["order_number"].strip()


def _lead_with_kind(client, kind: str, email: str) -> str:
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Заявка с типом работ",
            "sender": {"full_name": "Тип работ", "email": email},
            "raw_payload": {
                "quantity": 1,
                "parts": [
                    {
                        "width": 1000,
                        "height": 1000,
                        "quantity": 1,
                        "kind": kind,
                        "unit": "sqm",
                        "unit_price": "1000.00",
                        "amount": "1000.00",
                    }
                ],
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_number_letter_follows_the_work_kind(client, auth_headers):
    """Заказчик: буква в номере зависит «от фрезы, мыла, шпона и т.д.».

    Направление у ручной заявки не выбирают, и раньше номер оставался голым
    числом — в цеху по нему нельзя было понять, что за пачка.
    """
    cases = {"milling": "-Ф", "soap": "-М", "veneer": "-Ш", "film": "-П"}
    for index, (kind, suffix) in enumerate(cases.items()):
        lead_id = _lead_with_kind(client, kind, f"kind{index}@example.com")

        response = client.post(
            f"/api/v1/leads/{lead_id}/create-order", json={}, headers=auth_headers
        )

        assert response.status_code == 200, response.text
        number = response.json()["data"]["order_number"]
        assert number.endswith(suffix), f"{kind}: получили «{number}»"


def test_enamel_keeps_the_number_without_a_letter(client, auth_headers):
    """Эмаль у студии без буквы: «1024» и есть эмаль."""
    lead_id = _lead_with_kind(client, "paint", "paint-number@example.com")

    response = client.post(f"/api/v1/leads/{lead_id}/create-order", json={}, headers=auth_headers)

    assert response.json()["data"]["order_number"].isdigit()


def test_manual_digits_keep_their_value_but_letter_follows_work_kind(client, auth_headers):
    """Цифры менеджера не меняем; прежнюю букву заменяет актуальный тип работ."""
    lead_id = _lead_with_kind(client, "milling", "manual-over@example.com")

    response = client.post(
        f"/api/v1/leads/{lead_id}/create-order",
        json={"order_number": "44 03 п"},
        headers=auth_headers,
    )

    assert response.json()["data"]["order_number"] == "44 03-Ф"


def test_duplicate_number_is_refused(client, auth_headers):
    """Два заказа с одним номером — в цеху непонятно, какой из них резать."""
    first = client.post(
        f"/api/v1/leads/{_lead_for_order(client, 'num4@example.com')}/create-order",
        json={"order_number": "44-03-П"},
        headers=auth_headers,
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/v1/leads/{_lead_for_order(client, 'num5@example.com')}/create-order",
        json={"order_number": "44-03-П"},
        headers=auth_headers,
    )

    assert second.status_code == 409, second.text
    assert "44-03-П" in second.json()["error"]["message"]
