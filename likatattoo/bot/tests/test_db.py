from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.db import Database


@pytest.mark.asyncio
async def test_apply_pack_payment_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()

    first = await db.apply_pack_payment(
        user_id=101,
        payload="pack:starter",
        amount=50,
        currency="XTR",
        credits_added=5,
        provider_charge_id=None,
        telegram_charge_id="tg-charge-1",
        raw={"id": 1},
    )
    second = await db.apply_pack_payment(
        user_id=101,
        payload="pack:starter",
        amount=50,
        currency="XTR",
        credits_added=5,
        provider_charge_id=None,
        telegram_charge_id="tg-charge-1",
        raw={"id": 1},
    )

    assert first.applied is True
    assert first.balance == 5
    assert second.applied is False
    assert second.balance == 5
    assert await db.get_balance(101) == 5

    with sqlite3.connect(tmp_path / "bot.db") as connection:
        payments_count = connection.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    assert payments_count == 1


@pytest.mark.asyncio
async def test_record_deposit_payment_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()

    first = await db.record_deposit_payment(
        user_id=202,
        payload="service:session",
        offer_code="session",
        offer_title="Предоплата за сеанс",
        amount=150000,
        currency="RUB",
        amount_rub=1500,
        status="paid",
        telegram_charge_id="tg-deposit-1",
        provider_charge_id="provider-1",
        raw={"kind": "deposit"},
    )
    second = await db.record_deposit_payment(
        user_id=202,
        payload="service:session",
        offer_code="session",
        offer_title="Предоплата за сеанс",
        amount=150000,
        currency="RUB",
        amount_rub=1500,
        status="paid",
        telegram_charge_id="tg-deposit-1",
        provider_charge_id="provider-1",
        raw={"kind": "deposit"},
    )

    assert first.applied is True
    assert second.applied is False

    with sqlite3.connect(tmp_path / "bot.db") as connection:
        deposits_count = connection.execute("SELECT COUNT(*) FROM deposits").fetchone()[0]
        payments_count = connection.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        offer = connection.execute("SELECT offer_code, offer_title FROM deposits").fetchone()
    assert deposits_count == 1
    assert payments_count == 1
    assert offer == ("session", "Предоплата за сеанс")


@pytest.mark.asyncio
async def test_consume_credit_does_not_go_negative(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()
    await db.add_credits(303, 1)

    first_balance = await db.consume_credit(303)
    second_balance = await db.consume_credit(303)

    assert first_balance == 0
    assert second_balance == 0
    assert await db.get_balance(303) == 0


@pytest.mark.asyncio
async def test_upsert_user_grants_free_generations_once(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()

    await db.upsert_user(404, "lika", "Lika", starter_credits=5)
    first_balance = await db.get_balance(404)
    await db.upsert_user(404, "lika", "Lika Tattoo", starter_credits=5)
    second_balance = await db.get_balance(404)

    assert first_balance == 5
    assert second_balance == 5


@pytest.mark.asyncio
async def test_upsert_user_grants_free_generations_to_existing_balance_once(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()
    await db.add_credits(505, 7)

    await db.upsert_user(505, None, None, starter_credits=5)
    first_balance = await db.get_balance(505)
    await db.upsert_user(505, None, None, starter_credits=5)
    second_balance = await db.get_balance(505)

    assert first_balance == 12
    assert second_balance == 12


@pytest.mark.asyncio
async def test_create_booking_request_persists_lead_data(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()

    result = await db.create_booking_request(
        user_id=606,
        username="lika_client",
        full_name="Lika Client",
        idea="black raven with moon",
        size="8-10 cm",
        placement="forearm",
        preferred_date="next week",
        contact="@lika_client",
    )

    assert result.request_id > 0

    with sqlite3.connect(tmp_path / "bot.db") as connection:
        row = connection.execute(
            """
            SELECT user_id, username, full_name, idea, size, placement, preferred_date, contact, status, source, details_json
            FROM booking_requests
            """
        ).fetchone()

    assert row == (
        606,
        "lika_client",
        "Lika Client",
        "black raven with moon",
        "8-10 cm",
        "forearm",
        "next week",
        "@lika_client",
        "new",
        "telegram-bot",
        "{}",
    )


@pytest.mark.asyncio
async def test_create_booking_request_stores_source_and_details(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()

    payload = {"contact_channel": "telegram", "price_range": "4 000-6 500"}
    result = await db.create_booking_request(
        user_id=707,
        username=None,
        full_name="Website Lead",
        idea="thin lettering",
        size="5-10 cm",
        placement="forearm",
        preferred_date="weekday evening",
        contact="@website_lead",
        source="website-form",
        details_json=json.dumps(payload, ensure_ascii=False),
    )

    requests = await db.list_booking_requests(limit=5)

    assert result.request_id > 0
    assert requests[0].request_id == result.request_id
    assert requests[0].source == "website-form"
    assert json.loads(requests[0].details_json) == payload


@pytest.mark.asyncio
async def test_list_booking_requests_returns_latest_first(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()

    await db.create_booking_request(
        user_id=1,
        username="first",
        full_name="First Client",
        idea="small flower",
        size="5 cm",
        placement="wrist",
        preferred_date="friday",
        contact="@first",
    )
    second = await db.create_booking_request(
        user_id=2,
        username="second",
        full_name="Second Client",
        idea="moon linework",
        size="8 cm",
        placement="forearm",
        preferred_date="next week",
        contact="@second",
    )

    requests = await db.list_booking_requests(limit=5)

    assert len(requests) == 2
    assert requests[0].request_id == second.request_id
    assert requests[0].idea == "moon linework"
    assert requests[1].username == "first"


@pytest.mark.asyncio
async def test_count_booking_requests_by_status_groups_rows(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()

    await db.create_booking_request(
        user_id=1,
        username="alpha",
        full_name="Alpha",
        idea="snake",
        size="small",
        placement="ankle",
        preferred_date="july",
        contact="@alpha",
    )
    await db.create_booking_request(
        user_id=2,
        username="beta",
        full_name="Beta",
        idea="lettering",
        size="medium",
        placement="collarbone",
        preferred_date="weekend",
        contact="@beta",
        status="contacted",
    )
    await db.create_booking_request(
        user_id=3,
        username="gamma",
        full_name="Gamma",
        idea="star",
        size="tiny",
        placement="finger",
        preferred_date="tomorrow",
        contact="@gamma",
    )

    counts = await db.count_booking_requests_by_status()

    assert counts == {"contacted": 1, "new": 2}


@pytest.mark.asyncio
async def test_update_booking_request_status_changes_existing_row(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()

    created = await db.create_booking_request(
        user_id=9,
        username="delta",
        full_name="Delta",
        idea="rose",
        size="6 cm",
        placement="shoulder",
        preferred_date="monday",
        contact="@delta",
    )

    updated = await db.update_booking_request_status(created.request_id, "contacted")
    counts = await db.count_booking_requests_by_status()

    assert updated is True
    assert counts == {"contacted": 1}


@pytest.mark.asyncio
async def test_apply_robokassa_result_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.init()

    invoice_id = await db.create_robokassa_invoice_draft(
        user_id=707,
        offer_code="session",
        offer_title="Предоплата за сеанс",
        description="Предоплата за сеанс татуировки",
        amount_rub=1500,
        amount_text="1500.00",
    )
    await db.finalize_robokassa_invoice(
        invoice_id=invoice_id,
        receipt_json='{"items":[]}',
        payment_url="https://auth.robokassa.ru/Merchant/Index.aspx?...",
        signature_value="abc",
        shp_json=json.dumps({"Shp_offer_code": "session", "Shp_user_id": "707"}, ensure_ascii=False),
    )

    first = await db.apply_robokassa_result(
        invoice_id=invoice_id,
        out_sum_minor=150000,
        currency="RUB",
        email="client@example.com",
        payment_method="BankCard",
        op_key="op-1",
        callback_payload={"InvId": str(invoice_id), "OutSum": "1500.00"},
    )
    second = await db.apply_robokassa_result(
        invoice_id=invoice_id,
        out_sum_minor=150000,
        currency="RUB",
        email="client@example.com",
        payment_method="BankCard",
        op_key="op-1",
        callback_payload={"InvId": str(invoice_id), "OutSum": "1500.00"},
    )

    assert first.applied is True
    assert second.applied is False

    with sqlite3.connect(tmp_path / "bot.db") as connection:
        deposits_count = connection.execute("SELECT COUNT(*) FROM deposits").fetchone()[0]
        payments_count = connection.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        invoice_status = connection.execute(
            "SELECT status, email, op_key FROM robokassa_invoices WHERE invoice_id = ?",
            (invoice_id,),
        ).fetchone()

    assert deposits_count == 1
    assert payments_count == 1
    assert invoice_status == ("paid", "client@example.com", "op-1")
