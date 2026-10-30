from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
BOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BOT_DIR.parent
DATA_DIR = BOT_DIR / "data"
GENERATED_DIR = DATA_DIR / "generated"
DB_PATH = DATA_DIR / "bot.db"
PORTFOLIO_ROOT = PROJECT_DIR / "assets" / "portfolio"

load_dotenv(BOT_DIR / ".env")


class ConfigError(ValueError):
    pass


OpenAIImageQuality = Literal["standard", "hd", "low", "medium", "high", "auto"]
RobokassaHttpMethod = Literal["GET", "POST"]


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = _env(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got: {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got: {value}")
    return value


def _env_optional_int(name: str) -> int | None:
    raw = _env(name)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got: {raw!r}") from None


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    truthy = {"1", "true", "yes", "y", "on"}
    falsy = {"0", "false", "no", "n", "off"}
    if raw in truthy:
        return True
    if raw in falsy:
        return False
    raise ConfigError(f"{name} must be a boolean-like value, got: {raw!r}")


def _env_http_method(name: str, default: RobokassaHttpMethod) -> RobokassaHttpMethod:
    value = _env(name, default).upper()
    allowed: set[RobokassaHttpMethod] = {"GET", "POST"}
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ConfigError(f"{name} must be one of: {allowed_values}. Got: {value!r}")
    return value


def _env_robokassa_hash_algorithm(name: str, default: str) -> str:
    value = _env(name, default).upper()
    allowed = {
        "MD5",
        "RIPEMD160",
        "SHA1",
        "HS1",
        "SHA256",
        "HS256",
        "SHA384",
        "HS384",
        "SHA512",
        "HS512",
    }
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ConfigError(f"{name} must be one of: {allowed_values}. Got: {value!r}")
    return value


def _env_url(name: str, default: str) -> str:
    value = _env(name, default)
    if value and not value.startswith(("http://", "https://")):
        raise ConfigError(f"{name} must start with http:// or https://, got: {value!r}")
    return value


def _env_proxy_url(name: str) -> str:
    value = _env(name)
    if value and not value.startswith(("http://", "https://", "socks5://", "socks5h://")):
        raise ConfigError(
            f"{name} must start with http://, https://, socks5:// or socks5h://, got: {value!r}"
        )
    return value


def _env_image_size(name: str, default: str) -> str:
    value = _env(name, default)
    if value != "auto" and not re.fullmatch(r"\d{3,4}x\d{3,4}", value):
        raise ConfigError(
            f"{name} must be in WIDTHxHEIGHT format or 'auto', got: {value!r}"
        )
    return value


def _env_image_quality(name: str, default: OpenAIImageQuality) -> OpenAIImageQuality:
    value = _env(name, default)
    allowed: set[OpenAIImageQuality] = {"standard", "hd", "low", "medium", "high", "auto"}
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ConfigError(f"{name} must be one of: {allowed_values}. Got: {value!r}")
    return value


def is_placeholder(value: str) -> bool:
    text = (value or "").lower()
    return not text or "вставь сюда" in text or "insert" in text


@dataclass(frozen=True)
class GenerationPack:
    code: str
    title: str
    credits: int
    price_xtr: int

    @property
    def payload(self) -> str:
        return f"pack:{self.code}"


@dataclass(frozen=True)
class ServiceOffer:
    code: str
    title: str
    amount_rub: int
    description: str

    @property
    def payload(self) -> str:
        return f"service:{self.code}"


@dataclass(frozen=True)
class RobokassaConfig:
    merchant_login: str
    password1: str
    password2: str
    hash_algorithm: str
    is_test: bool
    result_url: str
    success_url: str
    success_url_method: RobokassaHttpMethod
    fail_url: str
    fail_url_method: RobokassaHttpMethod
    bind_host: str
    bind_port: int

    @property
    def ready(self) -> bool:
        return (
            not is_placeholder(self.merchant_login)
            and not is_placeholder(self.password1)
            and not is_placeholder(self.password2)
        )

    @property
    def callback_urls_ready(self) -> bool:
        return all((self.result_url, self.success_url, self.fail_url))

    @property
    def enabled(self) -> bool:
        return self.ready and self.callback_urls_ready


@dataclass(frozen=True)
class Config:
    bot_token: str
    openai_api_key: str
    openai_base_url: str
    payments_provider_token: str
    admin_chat_id: int | None
    telegram_proxy_url: str
    free_generations_on_start: int
    openai_image_model: str
    openai_image_size: str
    openai_image_quality: OpenAIImageQuality
    vk_url: str
    telegram_channel_url: str
    whatsapp_url: str
    google_sheets_spreadsheet_id: str
    google_sheets_consumables_range: str
    google_sheets_booking_range: str
    google_sheets_service_account_file: str
    google_sheets_service_account_json: str
    google_sheets_published_csv_url: str
    google_crm_spreadsheet_id: str
    google_crm_title: str
    google_crm_owner_email: str
    yandex_disk_local_path: str
    session_deposit_rub: int
    session_deposit_title: str
    session_deposit_offer: ServiceOffer
    portfolio_promo_enabled: bool
    portfolio_promo_offer: ServiceOffer | None
    robokassa: RobokassaConfig
    generation_packs: tuple[GenerationPack, ...]
    data_dir: Path
    generated_dir: Path
    db_path: Path
    portfolio_root: Path

    @property
    def bot_token_ready(self) -> bool:
        return not is_placeholder(self.bot_token)

    @property
    def openai_key_ready(self) -> bool:
        return not is_placeholder(self.openai_api_key)

    @property
    def session_deposit_enabled(self) -> bool:
        return not is_placeholder(self.payments_provider_token)

    @property
    def google_sheets_api_ready(self) -> bool:
        return bool(
            self.google_sheets_spreadsheet_id
            and self.google_sheets_booking_range
            and (self.google_sheets_service_account_file or self.google_sheets_service_account_json)
        )

    @property
    def google_sheets_consumables_ready(self) -> bool:
        return bool(self.google_sheets_published_csv_url) or bool(
            self.google_sheets_spreadsheet_id
            and self.google_sheets_consumables_range
            and (self.google_sheets_service_account_file or self.google_sheets_service_account_json)
        )

    @property
    def google_crm_credentials_ready(self) -> bool:
        return bool(self.google_sheets_service_account_file or self.google_sheets_service_account_json)

    @property
    def google_crm_ready(self) -> bool:
        return bool(self.google_crm_spreadsheet_id and self.google_crm_credentials_ready)

    @property
    def service_offers(self) -> tuple[ServiceOffer, ...]:
        offers = [self.session_deposit_offer]
        if self.portfolio_promo_offer is not None:
            offers.append(self.portfolio_promo_offer)
        return tuple(offers)

    @property
    def robokassa_enabled(self) -> bool:
        return self.robokassa.enabled

    @property
    def service_payments_enabled(self) -> bool:
        return self.session_deposit_enabled or self.robokassa_enabled


def load_config() -> Config:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    session_deposit_rub = _env_int("SESSION_DEPOSIT_RUB", 1500, minimum=1)
    session_deposit_title = _env("SESSION_DEPOSIT_TITLE", "Предоплата за сеанс")
    portfolio_promo_enabled = _env_bool("PORTFOLIO_PROMO_ENABLED", True)
    portfolio_promo_rub = _env_int("PORTFOLIO_PROMO_RUB", 1500, minimum=1)
    portfolio_promo_title = _env(
        "PORTFOLIO_PROMO_TITLE",
        "Портфолио-сессия • только расходники",
    )

    return Config(
        bot_token=_env("TELEGRAM_BOT_TOKEN"),
        openai_api_key=_env("OPENAI_API_KEY"),
        openai_base_url=_env_url("OPENAI_BASE_URL", ""),
        payments_provider_token=_env("PAYMENTS_PROVIDER_TOKEN"),
        admin_chat_id=_env_optional_int("ADMIN_CHAT_ID"),
        telegram_proxy_url=_env_proxy_url("TELEGRAM_PROXY_URL"),
        free_generations_on_start=_env_int("FREE_GENERATIONS_ON_START", 5, minimum=0),
        openai_image_model=_env("OPENAI_IMAGE_MODEL", "gpt-image-2"),
        openai_image_size=_env_image_size("OPENAI_IMAGE_SIZE", "1024x1024"),
        openai_image_quality=_env_image_quality("OPENAI_IMAGE_QUALITY", "low"),
        vk_url=_env_url("VK_URL", "https://vk.com/ppdstr23"),
        telegram_channel_url=_env_url("TELEGRAM_CHANNEL_URL", "https://t.me/ppdstr_bot"),
        whatsapp_url=_env_url("WHATSAPP_URL", "https://wa.me/70000000000"),
        google_sheets_spreadsheet_id=_env("GOOGLE_SHEETS_SPREADSHEET_ID"),
        google_sheets_consumables_range=_env("GOOGLE_SHEETS_CONSUMABLES_RANGE", "Расходники!A:Z"),
        google_sheets_booking_range=_env("GOOGLE_SHEETS_BOOKING_RANGE", "Запись!A:Z"),
        google_sheets_service_account_file=_env("GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE"),
        google_sheets_service_account_json=_env("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON"),
        google_sheets_published_csv_url=_env_url("GOOGLE_SHEETS_PUBLISHED_CSV_URL", ""),
        google_crm_spreadsheet_id=_env("GOOGLE_CRM_SPREADSHEET_ID"),
        google_crm_title=_env("GOOGLE_CRM_TITLE", "PPDSTR CRM"),
        google_crm_owner_email=_env("GOOGLE_CRM_OWNER_EMAIL"),
        yandex_disk_local_path=_env("YANDEX_DISK_LOCAL_PATH"),
        session_deposit_rub=session_deposit_rub,
        session_deposit_title=session_deposit_title,
        session_deposit_offer=ServiceOffer(
            code="session",
            title=session_deposit_title,
            amount_rub=session_deposit_rub,
            description="Бронирование даты сеанса и фиксация слота в расписании.",
        ),
        portfolio_promo_enabled=portfolio_promo_enabled,
        portfolio_promo_offer=(
            ServiceOffer(
                code="portfolio",
                title=portfolio_promo_title,
                amount_rub=portfolio_promo_rub,
                description=(
                    "Промо-сессия для портфолио: клиент оплачивает только расходники, "
                    "а мастер берет работу в портфолио по согласованному формату."
                ),
            )
            if portfolio_promo_enabled
            else None
        ),
        robokassa=RobokassaConfig(
            merchant_login=_env("ROBOKASSA_MERCHANT_LOGIN"),
            password1=_env("ROBOKASSA_PASSWORD1"),
            password2=_env("ROBOKASSA_PASSWORD2"),
            hash_algorithm=_env_robokassa_hash_algorithm("ROBOKASSA_HASH_ALGORITHM", "MD5"),
            is_test=_env_bool("ROBOKASSA_IS_TEST", True),
            result_url=_env_url("ROBOKASSA_RESULT_URL", ""),
            success_url=_env_url("ROBOKASSA_SUCCESS_URL", ""),
            success_url_method=_env_http_method("ROBOKASSA_SUCCESS_URL_METHOD", "GET"),
            fail_url=_env_url("ROBOKASSA_FAIL_URL", ""),
            fail_url_method=_env_http_method("ROBOKASSA_FAIL_URL_METHOD", "GET"),
            bind_host=_env("ROBOKASSA_BIND_HOST", "127.0.0.1"),
            bind_port=_env_int("ROBOKASSA_BIND_PORT", 8080, minimum=1),
        ),
        generation_packs=(
            GenerationPack(
                code="starter",
                title="5 генераций",
                credits=_env_int("GENERATION_PACK_SMALL_CREDITS", 5, minimum=1),
                price_xtr=_env_int("GENERATION_PACK_SMALL_PRICE_XTR", 50, minimum=1),
            ),
            GenerationPack(
                code="creator",
                title="15 генераций",
                credits=_env_int("GENERATION_PACK_MEDIUM_CREDITS", 15, minimum=1),
                price_xtr=_env_int("GENERATION_PACK_MEDIUM_PRICE_XTR", 120, minimum=1),
            ),
        ),
        data_dir=DATA_DIR,
        generated_dir=GENERATED_DIR,
        db_path=DB_PATH,
        portfolio_root=PORTFOLIO_ROOT,
    )
