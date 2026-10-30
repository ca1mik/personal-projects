"""Сроки заказа.

Заказчик: «надо ещё сделать сроки заказа, типа например мыло типовое 14 дней,
так же с возможностью редактирования при создании заявки, и дальше уже по
цепочке эта дата пойдет со всей инфой этой заявки».

Правило: названная дата главнее типовой. Типовой срок — подстановка, обещание
клиенту даёт менеджер.
"""

from __future__ import annotations

from datetime import date, timedelta


def _intake(client, **fields):
    payload = {
        "source_channel": "manual_manager_input",
        "text": "Заявка со сроком",
        "sender": {"full_name": "Срок Тест", "phone": "+79990003030"},
        "raw_payload": {},
    }
    payload.update(fields)
    response = client.post("/api/v1/leads/intake", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_typical_term_for_soap_is_two_weeks(client):
    """Мыло — 14 дней от приёма, как назвал заказчик."""
    lead = _intake(client, work_kind="soap")

    assert lead["due_date"] == (date.today() + timedelta(days=14)).isoformat()


def test_manager_date_wins_over_typical_term(client):
    """Названную дату не перебиваем типовым сроком: обещание даёт менеджер."""
    promised = (date.today() + timedelta(days=3)).isoformat()

    lead = _intake(client, work_kind="soap", due_date=promised)

    assert lead["due_date"] == promised


def test_lead_without_work_kind_has_no_term(client):
    """Из письма тип работ не приходит — срок не выдумываем.

    Поставить дату «через две недели» от имени студии нельзя: по ней потом
    отвечать перед клиентом.
    """
    lead = _intake(client, source_channel="email", sender={"email": "mail@example.com"})

    assert lead["due_date"] is None


def test_term_travels_from_lead_to_order(client, auth_headers):
    """Срок едет в заказ сам: его уже назвали клиенту при расчёте."""
    promised = (date.today() + timedelta(days=10)).isoformat()
    lead = _intake(client, work_kind="milling", due_date=promised)

    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]

    assert order["due_date"] == promised


def test_term_can_be_moved_on_the_order(client, auth_headers):
    """Заказ живёт дольше заявки — срок переносят по заказу."""
    lead = _intake(client, work_kind="soap")
    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order", json={}, headers=auth_headers
    ).json()["data"]
    moved = (date.today() + timedelta(days=21)).isoformat()

    response = client.patch(
        f"/api/v1/orders/{order['id']}", json={"due_date": moved}, headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["due_date"] == moved
    # заявку перенос заказа не трогает: там осталось то, что обещали изначально
    lead_after = client.get(f"/api/v1/leads/{lead['id']}", headers=auth_headers).json()["data"]
    assert lead_after["due_date"] != moved


def test_term_is_editable_on_the_lead_too(client, auth_headers):
    """Клиент попросил раньше — срок правится и в заявке."""
    lead = _intake(client, work_kind="soap")
    earlier = (date.today() + timedelta(days=5)).isoformat()

    response = client.patch(
        f"/api/v1/leads/{lead['id']}", json={"due_date": earlier}, headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["due_date"] == earlier


def test_past_date_is_accepted_as_is(client):
    """Просроченную дату не запрещаем: заявку заносят и задним числом.

    Запрет здесь мешал бы работе — заказ из прошлой недели надо занести с его
    настоящим сроком, а не с сегодняшним.
    """
    past = (date.today() - timedelta(days=2)).isoformat()

    lead = _intake(client, work_kind="soap", due_date=past)

    assert lead["due_date"] == past


def test_broken_date_is_refused(client):
    """Мусор вместо даты не должен молча стать пустым сроком."""
    response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Заявка",
            "sender": {"full_name": "Срок Тест"},
            "raw_payload": {},
            "due_date": "когда-нибудь",
        },
    )

    assert response.status_code == 422
