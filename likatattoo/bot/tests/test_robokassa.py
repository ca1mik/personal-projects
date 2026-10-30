from __future__ import annotations

import hashlib
from urllib.parse import parse_qs, urlparse

import pytest

from app.config import RobokassaConfig
from app.robokassa import (
    ReceiptItem,
    amount_to_minor_units,
    build_payment_link,
    build_receipt,
    build_result_signature,
    build_success_signature,
    format_amount,
    verify_result_signature,
    verify_success_signature,
)


def make_cfg() -> RobokassaConfig:
    return RobokassaConfig(
        merchant_login="lika-demo",
        password1="password-one",
        password2="password-two",
        hash_algorithm="MD5",
        is_test=True,
        result_url="https://example.com/robokassa/result",
        success_url="https://example.com/robokassa/success",
        success_url_method="GET",
        fail_url="https://example.com/robokassa/fail",
        fail_url_method="POST",
        bind_host="127.0.0.1",
        bind_port=8080,
    )


def test_format_amount_accepts_positive_numbers() -> None:
    assert format_amount(1500) == "1500"
    assert format_amount("1500.50") == "1500.50"


def test_format_amount_rejects_zero_and_bad_format() -> None:
    with pytest.raises(ValueError):
        format_amount("0")
    with pytest.raises(ValueError):
        format_amount("15,00")


def test_build_payment_link_uses_official_signature_order() -> None:
    cfg = make_cfg()
    link = build_payment_link(
        cfg,
        out_sum="1500",
        invoice_id=42,
        description="Deposit",
        shp={"b": "2", "a": "1"},
    )

    expected_payload = (
        "lika-demo:1500:42:"
        "https://example.com/robokassa/result:"
        "https://example.com/robokassa/success:GET:"
        "https://example.com/robokassa/fail:POST:"
        "password-one:Shp_a=1:Shp_b=2"
    )
    expected_signature = hashlib.md5(expected_payload.encode("utf-8")).hexdigest()

    parsed = urlparse(link.url)
    query = parse_qs(parsed.query)

    assert link.signature == expected_signature
    assert parsed.scheme == "https"
    assert parsed.netloc == "auth.robokassa.ru"
    assert query["MerchantLogin"] == ["lika-demo"]
    assert query["SignatureValue"] == [expected_signature]
    assert query["IsTest"] == ["1"]
    assert query["Shp_a"] == ["1"]
    assert query["Shp_b"] == ["2"]


def test_result_and_success_signatures_use_different_passwords() -> None:
    cfg = make_cfg()
    result_signature = build_result_signature(cfg, out_sum="1500", invoice_id=42, shp={"plan": "session"})
    success_signature = build_success_signature(
        cfg,
        out_sum="1500",
        invoice_id=42,
        shp={"plan": "session"},
    )

    assert result_signature != success_signature
    assert verify_result_signature(
        cfg,
        signature=result_signature.upper(),
        out_sum="1500",
        invoice_id=42,
        shp={"plan": "session"},
    )
    assert verify_success_signature(
        cfg,
        signature=success_signature.upper(),
        out_sum="1500",
        invoice_id=42,
        shp={"plan": "session"},
    )


def test_build_receipt_contains_service_item() -> None:
    receipt = build_receipt(
        items=[
            ReceiptItem(
                name="Предоплата за сеанс татуировки",
                quantity=1,
                sum_rub="1500.00",
                payment_method="prepayment",
                payment_object="service",
            )
        ]
    )

    assert '"name":"Предоплата за сеанс татуировки"' in receipt
    assert '"payment_method":"prepayment"' in receipt
    assert '"payment_object":"service"' in receipt


def test_amount_to_minor_units_converts_rubles_to_kopecks() -> None:
    assert amount_to_minor_units("1500.00") == 150000
