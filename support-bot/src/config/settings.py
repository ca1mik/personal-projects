from __future__ import annotations

import base64
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(
        default="Support Bot", validation_alias=AliasChoices("APP_NAME")
    )
    app_env: Literal["local", "staging", "production", "test"] = Field(
        default="local",
        validation_alias=AliasChoices("APP_ENV"),
    )
    debug: bool = Field(default=False, validation_alias=AliasChoices("DEBUG"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    log_json: bool = Field(default=True, validation_alias=AliasChoices("LOG_JSON"))
    timezone: str = Field(
        default="Europe/Moscow", validation_alias=AliasChoices("TIMEZONE")
    )

    telegram_bot_token: str = Field(
        default="", validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN")
    )
    telegram_webhook_url: str | None = Field(
        default=None, validation_alias=AliasChoices("TELEGRAM_WEBHOOK_URL")
    )
    telegram_provider_token: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TELEGRAM_PAYMENT_PROVIDER_TOKEN", "TELEGRAM_PROVIDER_TOKEN"
        ),
    )

    max_bot_token: str = Field(
        default="", validation_alias=AliasChoices("MAX_API_TOKEN", "MAX_BOT_TOKEN")
    )
    max_webhook_secret: str = Field(
        default="", validation_alias=AliasChoices("MAX_WEBHOOK_SECRET")
    )
    max_base_url: str = Field(
        default="https://platform-api.max.ru",
        validation_alias=AliasChoices("MAX_API_BASE_URL", "MAX_BASE_URL"),
    )
    max_mock_mode: bool = Field(
        default=False, validation_alias=AliasChoices("MAX_MOCK_MODE")
    )

    yookassa_shop_id: str = Field(
        default="", validation_alias=AliasChoices("YOOKASSA_SHOP_ID")
    )
    yookassa_secret_key: str = Field(
        default="", validation_alias=AliasChoices("YOOKASSA_SECRET_KEY")
    )
    yookassa_return_url: str = Field(
        default="", validation_alias=AliasChoices("YOOKASSA_RETURN_URL")
    )
    yookassa_webhook_secret: str = Field(
        default="", validation_alias=AliasChoices("YOOKASSA_WEBHOOK_SECRET")
    )
    yookassa_enable_receipts: bool = Field(
        default=False, validation_alias=AliasChoices("YOOKASSA_ENABLE_RECEIPTS")
    )
    yookassa_receipt_default_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices("YOOKASSA_RECEIPT_DEFAULT_EMAIL"),
    )
    yookassa_receipt_vat_code: int = Field(
        default=1, validation_alias=AliasChoices("YOOKASSA_RECEIPT_VAT_CODE")
    )
    yookassa_receipt_tax_system_code: int | None = Field(
        default=None,
        validation_alias=AliasChoices("YOOKASSA_RECEIPT_TAX_SYSTEM_CODE"),
    )

    llm_provider: Literal["openai", "anthropic", "yandexgpt", "gigachat", "mock"] = (
        Field(
            default="mock",
            validation_alias=AliasChoices("LLM_PROVIDER"),
        )
    )
    llm_api_key: str = Field(default="", validation_alias=AliasChoices("LLM_API_KEY"))
    openai_api_key: str = Field(
        default="", validation_alias=AliasChoices("OPENAI_API_KEY")
    )
    anthropic_api_key: str = Field(
        default="", validation_alias=AliasChoices("ANTHROPIC_API_KEY")
    )
    yandexgpt_api_key: str = Field(
        default="", validation_alias=AliasChoices("YANDEXGPT_API_KEY")
    )
    gigachat_client_id: str = Field(
        default="", validation_alias=AliasChoices("GIGACHAT_CLIENT_ID")
    )
    gigachat_client_secret: str = Field(
        default="", validation_alias=AliasChoices("GIGACHAT_CLIENT_SECRET")
    )
    llm_model: str = Field(
        default="gpt-5.4-mini", validation_alias=AliasChoices("LLM_MODEL")
    )
    llm_base_url: str | None = Field(
        default=None, validation_alias=AliasChoices("LLM_BASE_URL")
    )
    llm_timeout_seconds: int = Field(
        default=60, validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS")
    )
    llm_max_retries: int = Field(
        default=3, validation_alias=AliasChoices("LLM_MAX_RETRIES")
    )
    llm_anthropic_version: str = Field(
        default="2023-06-01", validation_alias=AliasChoices("LLM_ANTHROPIC_VERSION")
    )
    llm_openai_reasoning_effort: Literal["low", "medium", "high"] = Field(
        default="low",
        validation_alias=AliasChoices("LLM_OPENAI_REASONING_EFFORT"),
    )
    llm_yandex_api_url: str = Field(
        default="https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
        validation_alias=AliasChoices("YANDEXGPT_API_URL", "LLM_YANDEX_API_URL"),
    )
    llm_yandex_folder_id: str = Field(
        default="",
        validation_alias=AliasChoices("YANDEXGPT_FOLDER_ID", "LLM_YANDEX_FOLDER_ID"),
    )
    llm_yandex_auth_scheme: Literal["Bearer", "Api-Key"] = Field(
        default="Bearer",
        validation_alias=AliasChoices(
            "YANDEXGPT_AUTH_SCHEME", "LLM_YANDEX_AUTH_SCHEME"
        ),
    )
    llm_gigachat_auth_url: str = Field(
        default="https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        validation_alias=AliasChoices("GIGACHAT_AUTH_URL", "LLM_GIGACHAT_AUTH_URL"),
    )
    llm_gigachat_api_url: str = Field(
        default="https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        validation_alias=AliasChoices("GIGACHAT_API_URL", "LLM_GIGACHAT_API_URL"),
    )
    llm_gigachat_scope: str = Field(
        default="GIGACHAT_API_B2B",
        validation_alias=AliasChoices("GIGACHAT_SCOPE", "LLM_GIGACHAT_SCOPE"),
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./app.db",
        validation_alias=AliasChoices("DATABASE_URL"),
    )
    redis_url: str = Field(
        default="redis://redis:6379/0", validation_alias=AliasChoices("REDIS_URL")
    )

    admin_user_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list, validation_alias=AliasChoices("ADMIN_USER_IDS")
    )
    admin_api_token: str = Field(
        default="", validation_alias=AliasChoices("ADMIN_API_SECRET", "ADMIN_API_TOKEN")
    )
    support_contact: str = Field(
        default="@support", validation_alias=AliasChoices("SUPPORT_CONTACT")
    )
    webhook_base_url: str = Field(
        default="", validation_alias=AliasChoices("WEBHOOK_BASE_URL")
    )

    checkin_enabled: bool = Field(
        default=True, validation_alias=AliasChoices("CHECKIN_ENABLED")
    )
    preview_user_messages: int = Field(
        default=3, validation_alias=AliasChoices("PREVIEW_USER_MESSAGES")
    )
    rolling_window_messages: int = Field(
        default=8, validation_alias=AliasChoices("ROLLING_WINDOW_MESSAGES")
    )
    summary_threshold_messages: int = Field(
        default=12, validation_alias=AliasChoices("SUMMARY_THRESHOLD_MESSAGES")
    )
    checkin_hour_utc: int = Field(
        default=7,
        validation_alias=AliasChoices("CHECKIN_DEFAULT_TIME", "CHECKIN_HOUR_UTC"),
    )
    daily_checkin_message: str = Field(
        default="Привет.\nКак ты сегодня?\nЧто чувствуешь?",
        validation_alias=AliasChoices("DAILY_CHECKIN_MESSAGE"),
    )

    legal_doc_version: str | None = Field(
        default=None, validation_alias=AliasChoices("LEGAL_DOC_VERSION")
    )
    privacy_policy_version: str | None = Field(
        default=None, validation_alias=AliasChoices("PRIVACY_POLICY_VERSION")
    )
    offer_version: str | None = Field(
        default=None, validation_alias=AliasChoices("OFFER_VERSION")
    )
    disclaimer_version: str | None = Field(
        default=None, validation_alias=AliasChoices("DISCLAIMER_VERSION")
    )

    plan_week_title: str = Field(
        default="Неделя поддержки", validation_alias=AliasChoices("PLAN_WEEK_TITLE")
    )
    plan_week_price_rub: float = Field(
        default=390.0, validation_alias=AliasChoices("PLAN_WEEK_PRICE_RUB")
    )
    plan_week_days: int = Field(
        default=7, validation_alias=AliasChoices("PLAN_WEEK_DAYS")
    )
    plan_week_auto_renew: bool = Field(
        default=False, validation_alias=AliasChoices("PLAN_WEEK_AUTO_RENEW")
    )
    plan_week_description: str = Field(
        default="7 дней поддержки без автопродления",
        validation_alias=AliasChoices("PLAN_WEEK_DESCRIPTION"),
    )

    plan_month_title: str = Field(
        default="Месяц рядом", validation_alias=AliasChoices("PLAN_MONTH_TITLE")
    )
    plan_month_price_rub: float = Field(
        default=990.0, validation_alias=AliasChoices("PLAN_MONTH_PRICE_RUB")
    )
    plan_month_days: int = Field(
        default=30, validation_alias=AliasChoices("PLAN_MONTH_DAYS")
    )
    plan_month_auto_renew: bool = Field(
        default=True, validation_alias=AliasChoices("PLAN_MONTH_AUTO_RENEW")
    )
    plan_month_description: str = Field(
        default="30 дней поддержки с автопродлением",
        validation_alias=AliasChoices("PLAN_MONTH_DESCRIPTION"),
    )

    plan_quarter_title: str = Field(
        default="Квартал заботы", validation_alias=AliasChoices("PLAN_QUARTER_TITLE")
    )
    plan_quarter_price_rub: float = Field(
        default=2490.0, validation_alias=AliasChoices("PLAN_QUARTER_PRICE_RUB")
    )
    plan_quarter_days: int = Field(
        default=90, validation_alias=AliasChoices("PLAN_QUARTER_DAYS")
    )
    plan_quarter_auto_renew: bool = Field(
        default=True, validation_alias=AliasChoices("PLAN_QUARTER_AUTO_RENEW")
    )
    plan_quarter_description: str = Field(
        default="90 дней поддержки с автопродлением и скидкой",
        validation_alias=AliasChoices("PLAN_QUARTER_DESCRIPTION"),
    )

    @field_validator(
        "debug",
        "log_json",
        "max_mock_mode",
        "yookassa_enable_receipts",
        "checkin_enabled",
        mode="before",
    )
    @classmethod
    def parse_bool_variants(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on", "debug", "development", "dev"}:
            return True
        if normalized in {
            "0",
            "false",
            "no",
            "n",
            "off",
            "release",
            "production",
            "prod",
        }:
            return False
        return value

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> list[int]:
        if value in (None, "", []):
            return []
        if isinstance(value, list):
            return [int(item) for item in value]
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        raise ValueError("Unsupported ADMIN_USER_IDS format")

    @field_validator("yookassa_receipt_tax_system_code", mode="before")
    @classmethod
    def parse_optional_int(cls, value: object) -> int | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, str, bytes, bytearray)):
            return int(value)
        raise ValueError("Expected integer-compatible value")

    @field_validator("checkin_hour_utc", mode="before")
    @classmethod
    def parse_checkin_hour(cls, value: object) -> int:
        if isinstance(value, str) and ":" in value:
            value = value.split(":", maxsplit=1)[0]
        if isinstance(value, (int, str, bytes, bytearray)):
            return int(value)
        raise ValueError("Expected integer-compatible value")

    @field_validator("checkin_hour_utc")
    @classmethod
    def validate_checkin_hour(cls, value: int) -> int:
        if not 0 <= value <= 23:
            raise ValueError(
                "CHECKIN_DEFAULT_TIME/CHECKIN_HOUR_UTC must be between 0 and 23"
            )
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def public_legal_base_url(self) -> str:
        base = self.webhook_base_url.rstrip("/")
        return f"{base}/legal" if base else "/legal"

    @property
    def resolved_telegram_webhook_url(self) -> str:
        if self.telegram_webhook_url:
            return self.telegram_webhook_url
        base = self.webhook_base_url.rstrip("/")
        return f"{base}/webhooks/telegram" if base else ""

    @property
    def resolved_openai_api_key(self) -> str:
        return self.openai_api_key or self.llm_api_key

    @property
    def resolved_anthropic_api_key(self) -> str:
        return self.anthropic_api_key or self.llm_api_key

    @property
    def resolved_yandexgpt_api_key(self) -> str:
        return self.yandexgpt_api_key or self.llm_api_key

    @property
    def resolved_gigachat_basic_token(self) -> str:
        if self.gigachat_client_id and self.gigachat_client_secret:
            raw = f"{self.gigachat_client_id}:{self.gigachat_client_secret}".encode(
                "utf-8"
            )
            return base64.b64encode(raw).decode("ascii")
        return self.llm_api_key

    @property
    def use_mock_yookassa(self) -> bool:
        return not self.is_production and not (
            self.yookassa_shop_id and self.yookassa_secret_key
        )

    @property
    def telegram_payments_enabled(self) -> bool:
        return bool(self.telegram_provider_token)

    @property
    def demo_mode(self) -> bool:
        return (
            not self.is_production
            and self.llm_provider == "mock"
            and self.max_mock_mode
            and self.use_mock_yookassa
        )

    @property
    def effective_admin_api_token(self) -> str:
        if self.admin_api_token:
            return self.admin_api_token
        if self.demo_mode:
            return "demo-admin-secret"
        return ""

    def validate_runtime(self) -> None:
        if not self.is_production:
            return

        missing: list[str] = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if self.max_mock_mode:
            missing.append("MAX_API_TOKEN (MAX_MOCK_MODE is not allowed in production)")
        elif not self.max_bot_token:
            missing.append("MAX_API_TOKEN")
        if not self.webhook_base_url:
            missing.append("WEBHOOK_BASE_URL")
        if not all(
            [self.yookassa_shop_id, self.yookassa_secret_key, self.yookassa_return_url]
        ):
            missing.append(
                "YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY / YOOKASSA_RETURN_URL"
            )
        if self.llm_provider == "mock":
            missing.append(
                "real LLM provider credentials (LLM_PROVIDER=mock is not allowed in production)"
            )
        if self.llm_provider == "openai" and not self.resolved_openai_api_key:
            missing.append("OPENAI_API_KEY or LLM_API_KEY")
        if self.llm_provider == "anthropic" and not self.resolved_anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY or LLM_API_KEY")
        if self.llm_provider == "yandexgpt" and not self.resolved_yandexgpt_api_key:
            missing.append("YANDEXGPT_API_KEY or LLM_API_KEY")
        if self.llm_provider == "gigachat" and not self.resolved_gigachat_basic_token:
            missing.append("GIGACHAT_CLIENT_ID / GIGACHAT_CLIENT_SECRET or LLM_API_KEY")
        if missing:
            raise RuntimeError(
                f"Production configuration is incomplete: {', '.join(missing)}"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
