from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Fasad Production Platform"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://fasad:fasad@db:5432/fasad"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    local_storage_path: Path = BASE_DIR / "storage_data"
    default_currency: str = "RUB"
    first_superuser_login: str = "admin"
    first_superuser_password: str = "admin123"
    # Shared secret for external intake/webhooks; without it those routes fail closed.
    public_intake_secret: str = ""
    backup_mirror_path: Path | None = None

    channel_secret_key: str = "change-me"
    channel_poll_default_interval_seconds: int = 120
    channel_poll_min_interval_seconds: int = 30
    channel_scheduler_tick_seconds: int = 15
    # Run polls inside the scheduler process instead of pushing them to RQ.
    # Needed for local dev on Windows, where rq cannot be imported at all.
    channel_poll_inline: bool = False
    email_poll_batch_limit: int = 25
    email_max_attachment_mb: int = 15
    email_connect_timeout_seconds: int = 20
    # Файлы, которые менеджер прикладывает к заказу руками: эскизы, замеры,
    # сканы договоров. Лимит больше почтового — эскиз в PDF бывает тяжёлым.
    order_file_max_mb: int = 25
    # Потолок холодных писем в сутки с одного ящика. Выше 25-30 почтовые
    # провайдеры начинают считать отправителя рассыльщиком и режут доставку.
    outreach_daily_limit: int = 25

    # Привязка портативной сборки к одному компьютеру (см. app/core/license.py).
    # По умолчанию выключено: обычная разработка и docker-прод её не видят,
    # включает флаг только build-portable.ps1 в .env портативной сборки.
    license_lock_enabled: bool = False
    license_file_path: Path = BASE_DIR / "license.key"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("debug", "license_lock_enabled", mode="before")
    @classmethod
    def parse_debug(cls, value: bool | str) -> bool:
        if isinstance(value, bool):
            return value
        return value.strip().lower() in {"1", "true", "yes", "on", "debug", "development"}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment.lower() in {"production", "prod"}:
        if settings.debug:
            raise RuntimeError("DEBUG must be disabled in production")
        for name, value in (("JWT_SECRET_KEY", settings.jwt_secret_key), ("CHANNEL_SECRET_KEY", settings.channel_secret_key)):
            if len(value) < 32 or value == "change-me":
                raise RuntimeError(f"{name} must contain at least 32 random characters in production")
        if settings.public_intake_secret and len(settings.public_intake_secret) < 32:
            raise RuntimeError("PUBLIC_INTAKE_SECRET must contain at least 32 random characters in production")
    settings.local_storage_path.mkdir(parents=True, exist_ok=True)
    return settings
