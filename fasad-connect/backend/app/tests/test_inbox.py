from __future__ import annotations


def test_email_intake_creates_conversation_and_message(client, auth_headers):
    intake_response = client.post(
        "/api/v1/messaging/email/intake",
        json={
            "message_id": "email-001",
            "subject": "Wardrobe request",
            "from_name": "Ivan Petrov",
            "from_email": "ivan@example.com",
            "body_text": "Need wardrobe 1200x2400x600 in white board",
            "raw_payload": {"provider": "demo"},
        },
    )

    assert intake_response.status_code == 200

    conversations_response = client.get(
        "/api/v1/messaging/conversations?page=1&size=20",
        headers=auth_headers,
    )

    assert conversations_response.status_code == 200
    conversations = conversations_response.json()["data"]
    assert len(conversations) == 1
    assert conversations[0]["channel_account"]["channel_type"] == "email"
    assert conversations[0]["unread_count"] == 1
    assert conversations[0]["source_lead"]["source_channel"] == "email"


def test_duplicate_external_message_does_not_create_duplicate_message(client, auth_headers):
    payload = {
        "message_id": "telegram-100",
        "message": {
            "message_id": 100,
            "text": "Wardrobe 1200x2400x600",
            "chat": {"id": 777, "type": "private"},
            "from": {"id": 9001, "first_name": "Demo", "last_name": "Sender"},
        },
    }

    first_response = client.post("/api/v1/messaging/telegram/webhook", json=payload)
    second_response = client.post("/api/v1/messaging/telegram/webhook", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    conversations_response = client.get(
        "/api/v1/messaging/conversations?page=1&size=20",
        headers=auth_headers,
    )
    conversation_id = conversations_response.json()["data"][0]["id"]

    detail_response = client.get(
        f"/api/v1/messaging/conversations/{conversation_id}",
        headers=auth_headers,
    )

    assert detail_response.status_code == 200
    messages = detail_response.json()["data"]["messages"]
    assert len(messages) == 1
    assert messages[0]["external_message_id"] == "100"


def test_manager_can_reply_to_conversation_from_crm(client, auth_headers):
    intake_response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "external_message_id": "manual-001",
            "subject": "Manual intake",
            "text": "Client: Anna Ivanova, phone +79991234567, kitchen 2000x900x600",
            "sender": {
                "full_name": "Anna Ivanova",
                "phone": "+79991234567",
            },
            "raw_payload": {"source": "crm-demo"},
        },
    )

    assert intake_response.status_code == 200

    conversations_response = client.get(
        "/api/v1/messaging/conversations?page=1&size=20",
        headers=auth_headers,
    )
    conversation_id = conversations_response.json()["data"][0]["id"]

    reply_response = client.post(
        f"/api/v1/messaging/conversations/{conversation_id}/messages",
        headers=auth_headers,
        json={"body_text": "Здравствуйте. Подготовили предварительный расчет."},
    )

    assert reply_response.status_code == 200
    data = reply_response.json()["data"]
    assert data["status"] == "waiting_client"
    assert data["unread_count"] == 0
    assert len(data["messages"]) == 2
    assert data["messages"][-1]["direction"] == "outbound"
    assert data["messages"][-1]["status"] == "mock_sent"


def test_auto_provisioned_channel_names_are_russian():
    """Названия каналов уходят прямо в интерфейс — они должны быть русскими.

    Эту функцию вызывает приём заявки, когда канала ещё нет в базе. Английское
    имя здесь означает английский текст на карточке диалога и в списке каналов.
    """
    from app.modules.messaging.inbox_service import InboxService

    known = {
        "website_form": "Форма на сайте",
        "manual_manager_input": "Заявка от менеджера",
        "telegram_bot": "Telegram-бот приёма заявок",
        "email": "Почта",
    }
    for source_channel, expected in known.items():
        assert InboxService._channel_name(source_channel) == expected

    # неизвестный тип тоже не должен давать английское название
    assert InboxService._channel_name("some_new_source") == "Канал «some_new_source»"
