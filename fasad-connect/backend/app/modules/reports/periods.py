"""Периоды отчётности: неделя, месяц, квартал, год.

ТЗ требует одни и те же цифры за неделю, месяц, квартал и год. Логика границ
периода живёт здесь одна на все отчёты, чтобы «месяц» в отчёте по объёмам и
«месяц» в отчёте по клиентам не разошлись.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

PeriodCode = Literal["week", "month", "quarter", "year", "all", "custom"]

PERIOD_LABELS: dict[str, str] = {
    "week": "Неделя",
    "month": "Месяц",
    "quarter": "Квартал",
    "year": "Год",
    "all": "За всё время",
    "custom": "Произвольный период",
}


@dataclass(frozen=True)
class Period:
    code: str
    label: str
    date_from: datetime | None
    date_to: datetime | None

    def contains(self, moment: datetime | None) -> bool:
        if moment is None:
            return False
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        if self.date_from is not None and moment < self.date_from:
            return False
        if self.date_to is not None and moment > self.date_to:
            return False
        return True


def _start_of_day(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _end_of_day(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, 23, 59, 59, 999999, tzinfo=UTC)


def resolve_period(
    code: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
    *,
    now: datetime | None = None,
) -> Period:
    """Границы периода.

    Явные ``date_from``/``date_to`` всегда сильнее кода периода: менеджер выбрал
    даты руками — значит ему нужны именно они.
    """
    moment = now or datetime.now(UTC)
    today = moment.date()

    if date_from or date_to:
        return Period(
            code="custom",
            label=PERIOD_LABELS["custom"],
            date_from=_start_of_day(date_from) if date_from else None,
            date_to=_end_of_day(date_to) if date_to else None,
        )

    if code == "all":
        return Period(code="all", label=PERIOD_LABELS["all"], date_from=None, date_to=None)

    if code == "week":
        # Неделя с понедельника, как её считают на производстве.
        start = today - timedelta(days=today.weekday())
    elif code == "quarter":
        first_month = 3 * ((today.month - 1) // 3) + 1
        start = date(today.year, first_month, 1)
    elif code == "year":
        start = date(today.year, 1, 1)
    else:
        code = "month"
        start = date(today.year, today.month, 1)

    return Period(
        code=code,
        label=PERIOD_LABELS.get(code, PERIOD_LABELS["month"]),
        date_from=_start_of_day(start),
        date_to=_end_of_day(today),
    )


def month_bucket(moment: datetime) -> str:
    """Ключ месяца «2026-08» для разбивки по месяцам."""
    return f"{moment.year:04d}-{moment.month:02d}"


MONTH_NAMES_RU = [
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
]


def month_label(bucket: str) -> str:
    """«2026-08» → «август 2026»."""
    try:
        year, month = bucket.split("-")
        return f"{MONTH_NAMES_RU[int(month) - 1]} {year}"
    except (ValueError, IndexError):
        return bucket


def days_in_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]
