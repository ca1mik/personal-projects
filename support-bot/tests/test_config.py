import pytest

from src.config import Settings


def test_settings_parse_admin_ids_and_tariffs() -> None:
    settings = Settings(
        app_env="test",
        admin_user_ids="1,2,3",
        plan_week_price_rub=390,
        yookassa_enable_receipts=False,
    )
    assert settings.admin_user_ids == [1, 2, 3]
    assert settings.plan_week_price_rub == 390


def test_settings_validate_checkin_hour() -> None:
    with pytest.raises(ValueError):
        Settings(app_env="test", checkin_hour_utc=30, yookassa_enable_receipts=False)


def test_settings_parse_bool_and_time_alias_variants() -> None:
    settings = Settings(
        app_env="test",
        debug="release",
        checkin_hour_utc="07:00",
        yookassa_enable_receipts=False,
    )
    assert settings.debug is False
    assert settings.checkin_hour_utc == 7


def test_runtime_validation_allows_mock_mode_outside_production() -> None:
    settings = Settings(
        app_env="test",
        llm_provider="mock",
        max_mock_mode=True,
        yookassa_enable_receipts=False,
    )
    settings.validate_runtime()


def test_default_local_settings_enable_demo_mode() -> None:
    settings = Settings()
    assert settings.llm_provider == "mock"
    assert settings.max_mock_mode is True
    assert settings.use_mock_yookassa is True
    assert settings.demo_mode is True
    assert settings.effective_admin_api_token == "demo-admin-secret"


def test_runtime_validation_rejects_mock_provider_in_production() -> None:
    settings = Settings(
        app_env="production",
        debug=False,
        telegram_bot_token="tg-token",
        max_mock_mode=True,
        webhook_base_url="https://bot.example.com",
        yookassa_shop_id="shop",
        yookassa_secret_key="secret",
        yookassa_return_url="https://bot.example.com/return",
        llm_provider="mock",
        yookassa_enable_receipts=False,
    )
    with pytest.raises(RuntimeError):
        settings.validate_runtime()


def test_runtime_validation_accepts_complete_production_settings() -> None:
    settings = Settings(
        app_env="production",
        debug=False,
        telegram_bot_token="tg-token",
        max_mock_mode=False,
        max_bot_token="Bearer token",
        webhook_base_url="https://bot.example.com",
        yookassa_shop_id="shop",
        yookassa_secret_key="secret",
        yookassa_return_url="https://bot.example.com/return",
        llm_provider="openai",
        openai_api_key="sk-openai",
        yookassa_enable_receipts=False,
    )
    settings.validate_runtime()
