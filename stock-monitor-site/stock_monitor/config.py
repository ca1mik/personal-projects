from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_decimal(value: str | None, default: str) -> Decimal:
    raw = value if value is not None and value.strip() else default
    return Decimal(raw)


def _as_tickers(value: str | None) -> tuple[str, ...]:
    raw = value or "AFLT,SBER,GAZP"
    tickers = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return tuple(dict.fromkeys(tickers)) or ("AFLT", "SBER", "GAZP")


@dataclass(slots=True)
class Settings:
    app_login: str
    app_password: str
    session_cookie_name: str
    cookie_secure: bool
    default_tickers: tuple[str, ...]
    default_change_percent: Decimal
    default_window_minutes: int
    default_rollback_percent: Decimal
    tinkoff_token: str
    force_mock_provider: bool
    app_timezone: timezone


def get_settings() -> Settings:
    return Settings(
        app_login=os.getenv("APP_LOGIN", "admin"),
        app_password=os.getenv("APP_PASSWORD", "admin"),
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "stock_monitor_sid"),
        cookie_secure=_as_bool(os.getenv("COOKIE_SECURE"), default=False),
        default_tickers=_as_tickers(os.getenv("DEFAULT_TICKERS")),
        default_change_percent=_as_decimal(os.getenv("DEFAULT_CHANGE_PERCENT"), "2"),
        default_window_minutes=int(os.getenv("DEFAULT_WINDOW_MINUTES", "5")),
        default_rollback_percent=_as_decimal(
            os.getenv("DEFAULT_ROLLBACK_PERCENT"),
            "33.33",
        ),
        tinkoff_token=os.getenv("TINKOFF_TOKEN", "").strip(),
        force_mock_provider=_as_bool(os.getenv("FORCE_MOCK_PROVIDER"), default=False),
        app_timezone=timezone(timedelta(hours=3)),
    )
