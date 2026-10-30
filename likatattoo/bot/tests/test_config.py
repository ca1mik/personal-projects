from __future__ import annotations

import pytest

from app.config import ConfigError, load_config


def test_placeholder_provider_token_does_not_enable_deposit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAYMENTS_PROVIDER_TOKEN", "вставь сюда provider token для реальной предоплаты сеанса")
    cfg = load_config()
    assert cfg.session_deposit_enabled is False


def test_invalid_whatsapp_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_URL", "telegram://broken")
    with pytest.raises(ConfigError):
        load_config()


def test_invalid_telegram_proxy_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "ftp://127.0.0.1:10808")
    with pytest.raises(ConfigError):
        load_config()


def test_valid_telegram_proxy_url_is_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "http://127.0.0.1:10808")
    cfg = load_config()
    assert cfg.telegram_proxy_url == "http://127.0.0.1:10808"


def test_invalid_free_generations_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FREE_GENERATIONS_ON_START", "-1")
    with pytest.raises(ConfigError):
        load_config()


def test_invalid_generation_pack_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENERATION_PACK_SMALL_CREDITS", "0")
    with pytest.raises(ConfigError):
        load_config()


def test_portfolio_promo_is_enabled_by_default() -> None:
    cfg = load_config()
    assert cfg.portfolio_promo_offer is not None
    assert any(offer.code == "portfolio" for offer in cfg.service_offers)


def test_invalid_portfolio_promo_enabled_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTFOLIO_PROMO_ENABLED", "maybe")
    with pytest.raises(ConfigError):
        load_config()


def test_invalid_robokassa_hash_algorithm_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROBOKASSA_HASH_ALGORITHM", "SHA1024")
    with pytest.raises(ConfigError):
        load_config()


def test_valid_robokassa_settings_are_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROBOKASSA_MERCHANT_LOGIN", "lika-demo")
    monkeypatch.setenv("ROBOKASSA_PASSWORD1", "one")
    monkeypatch.setenv("ROBOKASSA_PASSWORD2", "two")
    monkeypatch.setenv("ROBOKASSA_RESULT_URL", "https://example.com/result")
    monkeypatch.setenv("ROBOKASSA_SUCCESS_URL", "https://example.com/success")
    monkeypatch.setenv("ROBOKASSA_FAIL_URL", "https://example.com/fail")
    cfg = load_config()
    assert cfg.robokassa.ready is True
    assert cfg.robokassa.callback_urls_ready is True
    assert cfg.robokassa_enabled is True
    assert cfg.robokassa.bind_port == 8080


def test_google_sheets_settings_are_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "sheet-123")
    monkeypatch.setenv("GOOGLE_SHEETS_CONSUMABLES_RANGE", "Расходники!A:Z")
    monkeypatch.setenv("GOOGLE_SHEETS_BOOKING_RANGE", "Запись!A:Z")
    monkeypatch.setenv("GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE", "secrets/google.json")
    monkeypatch.setenv("GOOGLE_SHEETS_PUBLISHED_CSV_URL", "https://example.com/export.csv")
    monkeypatch.setenv("GOOGLE_CRM_SPREADSHEET_ID", "crm-123")
    monkeypatch.setenv("GOOGLE_CRM_TITLE", "PPDSTR CRM")
    monkeypatch.setenv("GOOGLE_CRM_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setenv("YANDEX_DISK_LOCAL_PATH", r"F:\Yandex.Disk\ppdstr")
    cfg = load_config()
    assert cfg.google_sheets_spreadsheet_id == "sheet-123"
    assert cfg.google_sheets_consumables_ready is True
    assert cfg.google_sheets_api_ready is True
    assert cfg.google_crm_ready is True
    assert cfg.google_crm_title == "PPDSTR CRM"
    assert cfg.google_crm_owner_email == "owner@example.com"
    assert cfg.yandex_disk_local_path == r"F:\Yandex.Disk\ppdstr"
