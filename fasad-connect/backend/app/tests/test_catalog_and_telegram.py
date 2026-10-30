from __future__ import annotations


def test_catalog_estimate_returns_amount(client, auth_headers):
    response = client.post(
        "/api/v1/templates/catalog/estimate",
        headers=auth_headers,
        json={
            "product_code": "wardrobe_basic",
            "width": 1200,
            "height": 2400,
            "depth": 600,
            "quantity": 1,
            "material_code": "ldsp_white_18",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["product_code"] == "wardrobe_basic"
    assert float(data["final_amount"]) > 0
    assert float(data["area_sqm"]) > 0
    assert data["components"]


def test_telegram_bot_flow_creates_lead(client, auth_headers):
    start_response = client.post(
        "/api/v1/messaging/telegram/bot/webhook",
        json={
            "update_id": 1,
            "message": {
                "message_id": 1,
                "text": "/start",
                "chat": {"id": 501, "type": "private"},
                "from": {"id": 7001, "first_name": "Demo", "last_name": "User"},
            },
        },
    )
    assert start_response.status_code == 200
    assert start_response.json()["data"]["reply"]["session_state"] == "choose_product"

    product_response = client.post(
        "/api/v1/messaging/telegram/bot/webhook",
        json={
            "update_id": 2,
            "callback_query": {
                "id": "cb-2",
                "data": "product:wardrobe_basic",
                "from": {"id": 7001, "first_name": "Demo", "last_name": "User"},
                "message": {
                    "message_id": 2,
                    "chat": {"id": 501, "type": "private"},
                },
            },
        },
    )
    assert product_response.status_code == 200
    assert product_response.json()["data"]["reply"]["session_state"] == "await_width"

    for update_id, text, expected_state in (
        (3, "1200", "await_height"),
        (4, "2400", "await_depth"),
        (5, "600", "await_material"),
    ):
        response = client.post(
            "/api/v1/messaging/telegram/bot/webhook",
            json={
                "update_id": update_id,
                "message": {
                    "message_id": update_id,
                    "text": text,
                    "chat": {"id": 501, "type": "private"},
                    "from": {"id": 7001, "first_name": "Demo", "last_name": "User"},
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["data"]["reply"]["session_state"] == expected_state

    material_response = client.post(
        "/api/v1/messaging/telegram/bot/webhook",
        json={
            "update_id": 6,
            "callback_query": {
                "id": "cb-6",
                "data": "material:ldsp_white_18",
                "from": {"id": 7001, "first_name": "Demo", "last_name": "User"},
                "message": {
                    "message_id": 6,
                    "chat": {"id": 501, "type": "private"},
                },
            },
        },
    )
    assert material_response.status_code == 200
    assert material_response.json()["data"]["reply"]["estimated_total"] is not None
    assert material_response.json()["data"]["reply"]["session_state"] == "await_name"

    name_response = client.post(
        "/api/v1/messaging/telegram/bot/webhook",
        json={
            "update_id": 7,
            "message": {
                "message_id": 7,
                "text": "Иван Петров",
                "chat": {"id": 501, "type": "private"},
                "from": {"id": 7001, "first_name": "Demo", "last_name": "User"},
            },
        },
    )
    assert name_response.status_code == 200
    assert name_response.json()["data"]["reply"]["session_state"] == "await_phone"

    phone_response = client.post(
        "/api/v1/messaging/telegram/bot/webhook",
        json={
            "update_id": 8,
            "message": {
                "message_id": 8,
                "text": "+79990001122",
                "chat": {"id": 501, "type": "private"},
                "from": {"id": 7001, "first_name": "Demo", "last_name": "User"},
            },
        },
    )
    assert phone_response.status_code == 200
    reply = phone_response.json()["data"]["reply"]
    assert reply["lead_id"] is not None
    assert reply["session_state"] == "choose_product"

    leads_response = client.get("/api/v1/leads?page=1&size=20", headers=auth_headers)
    assert leads_response.status_code == 200
    leads = leads_response.json()["data"]
    assert any(lead["source_channel"] == "telegram_bot" for lead in leads)


def test_telegram_api_endpoint_returns_send_message_shape(client):
    response = client.post(
        "/api/v1/messaging/telegram/bot/telegram-api",
        json={
            "update_id": 99,
            "message": {
                "message_id": 99,
                "text": "/start",
                "chat": {"id": 9100, "type": "private"},
                "from": {"id": 8001, "first_name": "API", "last_name": "Demo"},
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "sendMessage"
    assert data["chat_id"] == 9100
    assert data["reply_markup"]["inline_keyboard"]
