from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"Environment variable {name} is required.")
    return value.strip()


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


@dataclass(slots=True, frozen=True)
class UnlockRules:
    special_unlock_video_count: int
    final_unlock_video_count: int
    final_unlock_total_opened: int
    final_unlock_time: str


@dataclass(slots=True, frozen=True)
class Settings:
    bot_token: str
    bot_proxy: str | None
    openai_api_key: str | None
    openai_model: str
    openai_proxy: str | None
    style_export_path: Path | None
    style_source_author: str | None
    style_target_name: str | None
    admin_id: int
    lika_chat_id: int
    timezone: str
    birthday_date: date
    db_path: Path
    assets_dir: Path
    auto_scan_enabled: bool
    auto_scan_interval_minutes: int
    enable_scheduled_messages: bool
    total_surprises: int
    allow_guests: bool
    log_level: str
    unlock_rules: UnlockRules

    @property
    def videos_dir(self) -> Path:
        return self.assets_dir / "videos"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(override=True)

        birthday_raw = _require_env("BIRTHDAY_DATE")
        try:
            birthday_date = date.fromisoformat(birthday_raw)
        except ValueError as error:
            raise ValueError("BIRTHDAY_DATE must have YYYY-MM-DD format.") from error

        final_unlock_time = os.getenv("FINAL_UNLOCK_TIME", "22:00").strip()
        try:
            datetime.strptime(final_unlock_time, "%H:%M")
        except ValueError as error:
            raise ValueError("FINAL_UNLOCK_TIME must have HH:MM format.") from error

        style_export_raw = os.getenv("STYLE_EXPORT_PATH", "data/style/chat_export.zip").strip()
        style_export_path = _resolve_path(style_export_raw) if style_export_raw else None

        return cls(
            bot_token=_require_env("BOT_TOKEN"),
            bot_proxy=os.getenv("BOT_PROXY", "").strip() or None,
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip(),
            openai_proxy=os.getenv("OPENAI_PROXY", "").strip() or None,
            style_export_path=style_export_path,
            style_source_author=os.getenv("STYLE_SOURCE_AUTHOR", "").strip() or None,
            style_target_name=os.getenv("STYLE_TARGET_NAME", "Лика").strip() or None,
            admin_id=int(_require_env("ADMIN_ID")),
            lika_chat_id=int(_require_env("LIKA_CHAT_ID")),
            timezone=os.getenv("TIMEZONE", "Europe/Amsterdam").strip(),
            birthday_date=birthday_date,
            db_path=_resolve_path(os.getenv("DB_PATH", "data/lika_bot.sqlite3")),
            assets_dir=_resolve_path(os.getenv("ASSETS_DIR", "assets")),
            auto_scan_enabled=_parse_bool(os.getenv("AUTO_SCAN_ENABLED"), default=True),
            auto_scan_interval_minutes=int(os.getenv("AUTO_SCAN_INTERVAL_MINUTES", "30")),
            enable_scheduled_messages=_parse_bool(
                os.getenv("ENABLE_SCHEDULED_MESSAGES"),
                default=True,
            ),
            total_surprises=int(os.getenv("TOTAL_SURPRISES", "19")),
            allow_guests=_parse_bool(os.getenv("ALLOW_GUESTS"), default=False),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            unlock_rules=UnlockRules(
                special_unlock_video_count=int(os.getenv("SPECIAL_UNLOCK_VIDEO_COUNT", "3")),
                final_unlock_video_count=int(os.getenv("FINAL_UNLOCK_VIDEO_COUNT", "7")),
                final_unlock_total_opened=int(os.getenv("FINAL_UNLOCK_TOTAL_OPENED", "13")),
                final_unlock_time=final_unlock_time,
            ),
        )
