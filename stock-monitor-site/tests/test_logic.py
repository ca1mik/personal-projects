from datetime import datetime, timedelta, timezone
from decimal import Decimal

from stock_monitor.monitor import MonitoringProfile, TickerMonitorState
from stock_monitor.utils import (
    compute_change_percent,
    compute_rollback_levels,
    crossed_level,
    round_up_to_interval,
)


TZ = timezone(timedelta(hours=3))


def test_round_up_to_next_interval_even_on_boundary():
    moment = datetime(2026, 3, 25, 10, 5, 0, tzinfo=TZ)
    assert round_up_to_interval(moment, 5) == datetime(2026, 3, 25, 10, 10, 0, tzinfo=TZ)


def test_round_up_to_next_day():
    moment = datetime(2026, 3, 25, 23, 59, 30, tzinfo=TZ)
    assert round_up_to_interval(moment, 5) == datetime(2026, 3, 26, 0, 0, 0, tzinfo=TZ)


def test_compute_rollback_levels_formula():
    rollback_min, rollback_max = compute_rollback_levels(
        Decimal("90"),
        Decimal("100"),
        Decimal("33.33"),
    )
    assert rollback_min == Decimal("93.3330")
    assert rollback_max == Decimal("96.6670")


def test_crossed_level_detects_both_sides():
    assert crossed_level(Decimal("90"), Decimal("93.3330"), Decimal("93.3330"), Decimal("96.6670")) is True
    assert crossed_level(Decimal("100"), Decimal("96.6670"), Decimal("93.3330"), Decimal("96.6670")) is True
    assert crossed_level(Decimal("95"), Decimal("97"), Decimal("93.3330"), Decimal("96.6670")) is False
    assert crossed_level(Decimal("95"), Decimal("93"), Decimal("93.3330"), Decimal("96.6670")) is False


def test_compute_change_percent():
    result = compute_change_percent(Decimal("90"), Decimal("100"))
    assert result == Decimal("10")


def test_monitor_keeps_range_between_windows_until_rollback_touch():
    profile = MonitoringProfile(
        tickers=("AFLT",),
        change_percent=Decimal("2"),
        window_minutes=5,
        rollback_percent=Decimal("33.33"),
    )
    state = TickerMonitorState(ticker="AFLT", name="Aeroflot")

    state.advance(datetime(2026, 3, 25, 16, 41, 17, tzinfo=TZ), Decimal("100"), profile)
    assert state.next_window_start == datetime(2026, 3, 25, 16, 45, 0, tzinfo=TZ)

    state.advance(datetime(2026, 3, 25, 16, 45, 0, tzinfo=TZ), Decimal("100"), profile)
    state.advance(datetime(2026, 3, 25, 16, 47, 0, tzinfo=TZ), Decimal("90"), profile)
    state.advance(datetime(2026, 3, 25, 16, 50, 0, tzinfo=TZ), Decimal("100"), profile)

    assert state.min_price == Decimal("90")
    assert state.max_price == Decimal("100")
    assert state.change_percent == Decimal("10")
    assert state.rollback_min == Decimal("93.3330")
    assert state.rollback_max == Decimal("96.6670")
    assert state.window_start == datetime(2026, 3, 25, 16, 45, 0, tzinfo=TZ)
    assert state.window_end == datetime(2026, 3, 25, 16, 55, 0, tzinfo=TZ)

    state.advance(datetime(2026, 3, 25, 16, 52, 0, tzinfo=TZ), Decimal("101"), profile)
    state.advance(datetime(2026, 3, 25, 16, 55, 0, tzinfo=TZ), Decimal("100.5"), profile)

    assert state.min_price == Decimal("90")
    assert state.max_price == Decimal("101")
    assert state.rollback_min == Decimal("93.6663")
    assert state.rollback_max == Decimal("97.3337")
    assert state.window_end == datetime(2026, 3, 25, 17, 0, 0, tzinfo=TZ)


def test_monitor_resets_after_rollback_touch():
    profile = MonitoringProfile(
        tickers=("AFLT",),
        change_percent=Decimal("2"),
        window_minutes=5,
        rollback_percent=Decimal("33.33"),
    )
    state = TickerMonitorState(ticker="AFLT", name="Aeroflot")

    state.advance(datetime(2026, 3, 25, 16, 41, 17, tzinfo=TZ), Decimal("90"), profile)
    state.advance(datetime(2026, 3, 25, 16, 45, 0, tzinfo=TZ), Decimal("90"), profile)
    state.advance(datetime(2026, 3, 25, 16, 47, 0, tzinfo=TZ), Decimal("100"), profile)
    state.advance(datetime(2026, 3, 25, 16, 50, 0, tzinfo=TZ), Decimal("100"), profile)
    state.advance(datetime(2026, 3, 25, 16, 50, 1, tzinfo=TZ), Decimal("96.6670"), profile)

    assert state.window_start is None
    assert state.window_end is None
    assert state.next_window_start == datetime(2026, 3, 25, 16, 55, 0, tzinfo=TZ)
    assert state.min_price is None
    assert state.max_price is None
    assert state.rollback_min is None
    assert state.rollback_max is None
    assert state.last_reset_reason == "Цена задела уровень отката. Цикл перезапущен."
