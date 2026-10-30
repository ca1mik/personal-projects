from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from app.config import RobokassaConfig

PAYMENT_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"
_AMOUNT_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")
_HASH_ALGORITHM_ALIASES = {
    "MD5": "md5",
    "RIPEMD160": "ripemd160",
    "SHA1": "sha1",
    "HS1": "sha1",
    "SHA256": "sha256",
    "HS256": "sha256",
    "SHA384": "sha384",
    "HS384": "sha384",
    "SHA512": "sha512",
    "HS512": "sha512",
}


class RobokassaError(ValueError):
    pass


@dataclass(frozen=True)
class PaymentLink:
    url: str
    signature: str
    params: dict[str, str]


@dataclass(frozen=True)
class ReceiptItem:
    name: str
    quantity: int | float | Decimal
    sum_rub: int | float | Decimal | str
    payment_method: str
    payment_object: str
    tax: str = "none"


def format_amount(value: int | float | Decimal | str) -> str:
    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, int):
        text = str(value)
    elif isinstance(value, Decimal):
        text = format(value, "f")
    else:
        text = format(Decimal(str(value)), "f")

    if not _AMOUNT_PATTERN.fullmatch(text):
        raise RobokassaError(f"Invalid OutSum format: {text!r}")

    try:
        decimal_value = Decimal(text)
    except InvalidOperation as error:
        raise RobokassaError(f"Invalid OutSum value: {text!r}") from error

    if decimal_value <= 0:
        raise RobokassaError("OutSum must be greater than zero.")
    return text


def amount_to_minor_units(value: int | float | Decimal | str) -> int:
    amount_text = format_amount(value)
    try:
        decimal_value = Decimal(amount_text)
    except InvalidOperation as error:
        raise RobokassaError(f"Invalid OutSum value: {amount_text!r}") from error
    return int((decimal_value * Decimal("100")).quantize(Decimal("1")))


def normalize_shp(shp: Mapping[str, str] | None) -> dict[str, str]:
    return {key: value for key, value in _normalize_shp(shp)}


def build_receipt(*, items: list[ReceiptItem], sno: str | None = None) -> str:
    if not items:
        raise RobokassaError("Receipt must contain at least one item.")

    payload_items: list[dict[str, object]] = []
    for item in items:
        payload_items.append(
            {
                "name": item.name,
                "quantity": float(Decimal(str(item.quantity))),
                "sum": float(Decimal(format_amount(item.sum_rub))),
                "payment_method": item.payment_method,
                "payment_object": item.payment_object,
                "tax": item.tax,
            }
        )

    receipt: dict[str, object] = {"items": payload_items}
    if sno:
        receipt["sno"] = sno
    return json.dumps(receipt, ensure_ascii=False, separators=(",", ":"))


def _hash_hexdigest(algorithm: str, payload: str) -> str:
    digest_name = _HASH_ALGORITHM_ALIASES.get(algorithm.upper())
    if digest_name is None:
        raise RobokassaError(f"Unsupported hash algorithm: {algorithm!r}")
    return hashlib.new(digest_name, payload.encode("utf-8")).hexdigest()


def _normalize_invoice_id(invoice_id: int | str | None) -> str:
    if invoice_id is None:
        return ""
    return str(invoice_id)


def _normalize_url_method(method: str | None) -> str | None:
    if method is None:
        return None
    normalized = method.upper()
    if normalized not in {"GET", "POST"}:
        raise RobokassaError(f"Unsupported HTTP method: {method!r}")
    return normalized


def _normalize_step_by_step(step_by_step: bool | str | None) -> str | None:
    if step_by_step is None:
        return None
    if isinstance(step_by_step, bool):
        return "1" if step_by_step else "0"
    normalized = str(step_by_step).strip()
    if normalized not in {"0", "1"}:
        raise RobokassaError("StepByStep must be bool, '0' or '1'.")
    return normalized


def _normalize_shp(shp: Mapping[str, str] | None) -> list[tuple[str, str]]:
    if not shp:
        return []

    normalized: list[tuple[str, str]] = []
    for key, value in shp.items():
        key_text = str(key).strip()
        if not key_text:
            raise RobokassaError("Shp parameter key must not be empty.")
        if not key_text.startswith("Shp_"):
            key_text = f"Shp_{key_text}"
        normalized.append((key_text, str(value)))
    return sorted(normalized, key=lambda item: item[0])


def _signature_parts(
    *,
    out_sum: str,
    invoice_id: int | str | None,
    password: str,
    receipt: str | None = None,
    step_by_step: bool | str | None = None,
    result_url: str | None = None,
    success_url: str | None = None,
    success_url_method: str | None = None,
    fail_url: str | None = None,
    fail_url_method: str | None = None,
    token: str | None = None,
    shp: Mapping[str, str] | None = None,
    merchant_login: str | None = None,
) -> list[str]:
    parts: list[str] = []
    if merchant_login is not None:
        parts.append(merchant_login)
    parts.append(out_sum)
    parts.append(_normalize_invoice_id(invoice_id))

    optional_parts = [
        receipt,
        _normalize_step_by_step(step_by_step),
        result_url,
        success_url,
        _normalize_url_method(success_url_method),
        fail_url,
        _normalize_url_method(fail_url_method),
        token,
    ]
    parts.extend(value for value in optional_parts if value is not None)
    parts.append(password)
    parts.extend(f"{key}={value}" for key, value in _normalize_shp(shp))
    return parts


def build_payment_signature(
    cfg: RobokassaConfig,
    *,
    out_sum: int | float | Decimal | str,
    invoice_id: int | str | None,
    receipt: str | None = None,
    step_by_step: bool | str | None = None,
    result_url: str | None = None,
    success_url: str | None = None,
    success_url_method: str | None = None,
    fail_url: str | None = None,
    fail_url_method: str | None = None,
    token: str | None = None,
    shp: Mapping[str, str] | None = None,
) -> str:
    out_sum_text = format_amount(out_sum)
    payload = ":".join(
        _signature_parts(
            merchant_login=cfg.merchant_login,
            out_sum=out_sum_text,
            invoice_id=invoice_id,
            receipt=receipt,
            step_by_step=step_by_step,
            result_url=result_url,
            success_url=success_url,
            success_url_method=success_url_method,
            fail_url=fail_url,
            fail_url_method=fail_url_method,
            token=token,
            password=cfg.password1,
            shp=shp,
        )
    )
    return _hash_hexdigest(cfg.hash_algorithm, payload)


def build_result_signature(
    cfg: RobokassaConfig,
    *,
    out_sum: int | float | Decimal | str,
    invoice_id: int | str | None,
    shp: Mapping[str, str] | None = None,
) -> str:
    out_sum_text = format_amount(out_sum)
    payload = ":".join(
        _signature_parts(
            out_sum=out_sum_text,
            invoice_id=invoice_id,
            password=cfg.password2,
            shp=shp,
        )
    )
    return _hash_hexdigest(cfg.hash_algorithm, payload)


def build_success_signature(
    cfg: RobokassaConfig,
    *,
    out_sum: int | float | Decimal | str,
    invoice_id: int | str | None,
    shp: Mapping[str, str] | None = None,
) -> str:
    out_sum_text = format_amount(out_sum)
    payload = ":".join(
        _signature_parts(
            out_sum=out_sum_text,
            invoice_id=invoice_id,
            password=cfg.password1,
            shp=shp,
        )
    )
    return _hash_hexdigest(cfg.hash_algorithm, payload)


def verify_result_signature(
    cfg: RobokassaConfig,
    *,
    signature: str,
    out_sum: int | float | Decimal | str,
    invoice_id: int | str | None,
    shp: Mapping[str, str] | None = None,
) -> bool:
    expected = build_result_signature(cfg, out_sum=out_sum, invoice_id=invoice_id, shp=shp)
    return hmac.compare_digest(signature.lower(), expected.lower())


def verify_success_signature(
    cfg: RobokassaConfig,
    *,
    signature: str,
    out_sum: int | float | Decimal | str,
    invoice_id: int | str | None,
    shp: Mapping[str, str] | None = None,
) -> bool:
    expected = build_success_signature(cfg, out_sum=out_sum, invoice_id=invoice_id, shp=shp)
    return hmac.compare_digest(signature.lower(), expected.lower())


def build_payment_link(
    cfg: RobokassaConfig,
    *,
    out_sum: int | float | Decimal | str,
    invoice_id: int | str | None,
    description: str,
    receipt: str | None = None,
    step_by_step: bool | str | None = None,
    result_url: str | None = None,
    success_url: str | None = None,
    success_url_method: str | None = None,
    fail_url: str | None = None,
    fail_url_method: str | None = None,
    token: str | None = None,
    email: str | None = None,
    culture: str | None = "ru",
    encoding: str | None = "utf-8",
    inc_curr_label: str | None = None,
    shp: Mapping[str, str] | None = None,
    payment_url: str = PAYMENT_URL,
) -> PaymentLink:
    out_sum_text = format_amount(out_sum)
    resolved_result_url = result_url or cfg.result_url or None
    resolved_success_url = success_url or cfg.success_url or None
    resolved_success_method = success_url_method or cfg.success_url_method
    resolved_fail_url = fail_url or cfg.fail_url or None
    resolved_fail_method = fail_url_method or cfg.fail_url_method

    signature = build_payment_signature(
        cfg,
        out_sum=out_sum_text,
        invoice_id=invoice_id,
        receipt=receipt,
        step_by_step=step_by_step,
        result_url=resolved_result_url,
        success_url=resolved_success_url,
        success_url_method=resolved_success_method if resolved_success_url else None,
        fail_url=resolved_fail_url,
        fail_url_method=resolved_fail_method if resolved_fail_url else None,
        token=token,
        shp=shp,
    )

    params: dict[str, str] = {
        "MerchantLogin": cfg.merchant_login,
        "OutSum": out_sum_text,
        "SignatureValue": signature,
        "Description": description,
    }
    invoice_id_text = _normalize_invoice_id(invoice_id)
    if invoice_id_text:
        params["InvId"] = invoice_id_text
    if receipt is not None:
        params["Receipt"] = receipt
    normalized_step = _normalize_step_by_step(step_by_step)
    if normalized_step is not None:
        params["StepByStep"] = normalized_step
    if resolved_result_url:
        params["ResultUrl2"] = resolved_result_url
    if resolved_success_url:
        params["SuccessUrl2"] = resolved_success_url
        params["SuccessUrl2Method"] = _normalize_url_method(resolved_success_method) or "GET"
    if resolved_fail_url:
        params["FailUrl2"] = resolved_fail_url
        params["FailUrl2Method"] = _normalize_url_method(resolved_fail_method) or "GET"
    if token is not None:
        params["Token"] = token
    if email:
        params["Email"] = email
    if culture:
        params["Culture"] = culture
    if encoding:
        params["Encoding"] = encoding
    if inc_curr_label:
        params["IncCurrLabel"] = inc_curr_label
    if cfg.is_test:
        params["IsTest"] = "1"
    for key, value in _normalize_shp(shp):
        params[key] = value

    return PaymentLink(
        url=f"{payment_url}?{urlencode(params)}",
        signature=signature,
        params=params,
    )
