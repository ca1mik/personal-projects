from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_in_timezone(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name))


def combine_local_date_and_time(day: date, hh_mm: str, timezone_name: str) -> datetime:
    hour, minute = [int(part) for part in hh_mm.split(":", maxsplit=1)]
    return datetime.combine(day, time(hour=hour, minute=minute), tzinfo=ZoneInfo(timezone_name))
