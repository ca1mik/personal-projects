"""Буква в номере заказа.

Заказчик: «в зависимости от фрезы, мыла, шпона и т.д. присваивалась к цифрам
буква». Букву даёт направление, а если у направления её нет — тип работ из
заявки.

Раньше условие смотрело только на то, задано ли направление вообще. Поэтому
заявка с направлением «Эмаль» (у которого буквы нет по замыслу) и строками
фрезеровки давала голое число: тип работ до номера не доходил.
"""

from __future__ import annotations

from decimal import Decimal


def _direction(db_session, code: str, name: str, suffix: str):
    from app.modules.directions.models import ProductionDirection

    direction = ProductionDirection(
        code=code,
        name=name,
        number_suffix=suffix,
        material_area_factor=Decimal("1.000"),
        sort_order=1,
        is_active=True,
    )
    db_session.add(direction)
    db_session.commit()
    return direction


def _lead_with_milling(client, auth_headers, email: str, direction_code: str = ""):
    """Заявка со строкой фрезеровки.

    Тип работ система берёт из `raw_payload.parts[].kind` — там же, откуда его
    читают печать и раскрой. Именно эту форму присылает таблица бланка.
    """
    payload = {
        "source_channel": "manual_manager_input",
        "text": "Фасады с фрезеровкой",
        "sender": {"full_name": "Буква Тест", "email": email},
        "raw_payload": {
            "parts": [
                {
                    "width": 716,
                    "height": 396,
                    "quantity": 2,
                    "article": "112",
                    "kind": "milling",
                    "price": "1000.00",
                }
            ]
        },
    }
    if direction_code:
        payload["direction_code"] = direction_code
    return client.post("/api/v1/leads/intake", json=payload).json()["data"]


def _order_number(client, auth_headers, lead_id: str) -> str:
    return client.post(
        f"/api/v1/leads/{lead_id}/create-order", json={}, headers=auth_headers
    ).json()["data"]["order_number"]


def test_direction_letter_wins(client, auth_headers, db_session):
    """У направления есть своя буква — она и стоит в номере."""
    _direction(db_session, "pvc", "ПВХ", "П")
    lead = _lead_with_milling(client, auth_headers, "pvc@example.com", "pvc")

    number = _order_number(client, auth_headers, lead["id"])

    assert number.endswith("-П"), number


def test_work_kind_letter_when_direction_has_none(client, auth_headers, db_session):
    """Направление без буквы — букву даёт тип работ, а не пустота.

    Это и есть починенный случай: «Эмаль» буквы не несёт, но фрезеровка несёт.
    """
    _direction(db_session, "enamel", "Эмаль", "")
    lead = _lead_with_milling(client, auth_headers, "enamel@example.com", "enamel")

    number = _order_number(client, auth_headers, lead["id"])

    assert number.endswith("-Ф"), f"буква типа работ потерялась: {number}"


def test_no_direction_and_no_kind_gives_plain_number(client, auth_headers):
    """Ни направления, ни типа работ — просто номер, без хвоста."""
    lead = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Заявка без расчёта",
            "sender": {"full_name": "Без Буквы", "email": "plain@example.com"},
            "raw_payload": {},
        },
    ).json()["data"]

    number = _order_number(client, auth_headers, lead["id"])

    assert "-" not in number, number


def _lead_with_rows(client, email: str, direction_code: str, rows: list[tuple[str, int]]):
    """Заявка с заданным набором строк: (тип работ, сколько строк)."""
    parts = []
    for kind, count in rows:
        for _ in range(count):
            parts.append(
                {"width": 716, "height": 396, "quantity": 1, "article": "112", "kind": kind}
            )
    return client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "manual_manager_input",
            "text": "Фасады",
            "sender": {"full_name": "Голосование", "email": email},
            "direction_code": direction_code,
            "raw_payload": {"parts": parts},
        },
    ).json()["data"]


def test_extra_hand_typed_rows_do_not_change_the_letter(client, auth_headers, db_session):
    """Дописал артикулы руками — номер заказа не должен смениться.

    Основную операцию выбирают голосованием по строкам. Строки, повторяющие
    само направление («Эмаль» → тип `paint`), ничего нового не сообщают, но
    пока они голосовали наравне, буква зависела от их количества: две строки
    фрезеровки против одной обычной давали «-Ф», а против трёх — голый номер.
    Менеджер дописывал артикул — и номер уезжал.
    """
    _direction(db_session, "enamel", "Эмаль", "")

    few = _lead_with_rows(client, "few@example.com", "enamel", [("milling", 2), ("paint", 1)])
    many = _lead_with_rows(client, "many@example.com", "enamel", [("milling", 2), ("paint", 5)])

    first = _order_number(client, auth_headers, few["id"])
    second = _order_number(client, auth_headers, many["id"])

    assert first.endswith("-Ф"), first
    assert second.endswith("-Ф"), f"буква пропала из-за лишних обычных строк: {second}"


def test_order_without_operations_keeps_the_direction_letter(client, auth_headers, db_session):
    """Только обычные фасады своего направления — буква направления, и всё.

    «Эмаль» буквы не несёт: «1024» и есть эмаль.
    """
    _direction(db_session, "enamel", "Эмаль", "")
    lead = _lead_with_rows(client, "plainrows@example.com", "enamel", [("paint", 3)])

    number = _order_number(client, auth_headers, lead["id"])

    assert "-" not in number, number


def test_manual_digits_keep_the_direction_letter(client, auth_headers, db_session):
    """Цифры студии остаются, буква приходит из выбранного направления."""
    _direction(db_session, "pvc", "ПВХ", "П")
    lead = _lead_with_milling(client, auth_headers, "manual@example.com", "pvc")

    order = client.post(
        f"/api/v1/leads/{lead['id']}/create-order",
        json={"order_number": "44 03 п"},
        headers=auth_headers,
    ).json()["data"]

    assert order["order_number"] == "44 03-П"
