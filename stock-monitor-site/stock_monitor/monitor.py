from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .config import Settings
from .providers import PriceProvider, build_price_provider
from .schemas import StartMonitoringRequest
from .utils import (
    ZERO,
    compute_change_percent,
    compute_rollback_levels,
    crossed_level,
    format_datetime,
    format_decimal,
    round_up_to_interval,
)


@dataclass(slots=True)
class MonitoringProfile:
    tickers: tuple[str, ...]
    change_percent: Decimal
    window_minutes: int
    rollback_percent: Decimal


@dataclass(slots=True)
class TickerMonitorState:
    ticker: str
    name: str
    current_price: Decimal | None = None
    previous_price: Decimal | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    change_percent: Decimal = ZERO
    rollback_min: Decimal | None = None
    rollback_max: Decimal | None = None
    status: str = "ожидание запуска"
    next_window_start: datetime | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    last_reset_reason: str = ""
    target_reached: bool = False

    def schedule_initial(self, now: datetime, window_minutes: int) -> None:
        self.status = "ожидание окна"
        self.next_window_start = round_up_to_interval(now, window_minutes)
        self.window_start = None
        self.window_end = None
        self.min_price = None
        self.max_price = None
        self.change_percent = ZERO
        self.rollback_min = None
        self.rollback_max = None
        self.target_reached = False
        self.last_reset_reason = ""

    def reset_for_restart(self, now: datetime, window_minutes: int, reason: str) -> None:
        self.status = "ожидание окна"
        self.next_window_start = round_up_to_interval(now, window_minutes)
        self.window_start = None
        self.window_end = None
        self.min_price = None
        self.max_price = None
        self.change_percent = ZERO
        self.rollback_min = None
        self.rollback_max = None
        self.target_reached = False
        self.last_reset_reason = reason

    def stop(self) -> None:
        self.status = "остановлено"
        self.next_window_start = None
        self.window_start = None
        self.window_end = None

    def advance(self, now: datetime, price: Decimal | None, profile: MonitoringProfile) -> None:
        if price is not None:
            self.previous_price = self.current_price
            self.current_price = price

        if self.next_window_start is None and self.window_start is None:
            self.schedule_initial(now, profile.window_minutes)

        if self.window_start is None and self.next_window_start is not None and now >= self.next_window_start:
            self._begin_window(profile.window_minutes)

        if self.window_start is not None and self.window_end is not None and price is not None:
            if crossed_level(
                self.previous_price,
                self.current_price,
                self.rollback_min,
                self.rollback_max,
            ):
                self.reset_for_restart(
                    now,
                    profile.window_minutes,
                    "Цена задела уровень отката. Цикл перезапущен.",
                )
                return
            self._apply_price(price, profile.change_percent)

        while self.window_end is not None and now >= self.window_end:
            self._finalize_window(profile.rollback_percent)
            self.window_end += timedelta(minutes=profile.window_minutes)

        self._refresh_status()

    def to_payload(self) -> dict[str, str | bool | None]:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "current_price": format_decimal(self.current_price),
            "min_price": format_decimal(self.min_price),
            "max_price": format_decimal(self.max_price),
            "change_percent": format_decimal(self.change_percent),
            "rollback_min": format_decimal(self.rollback_min),
            "rollback_max": format_decimal(self.rollback_max),
            "status": self.status,
            "window_start": format_datetime(self.window_start),
            "window_end": format_datetime(self.window_end),
            "next_window_start": format_datetime(self.next_window_start),
            "last_reset_reason": self.last_reset_reason or None,
            "target_reached": self.target_reached,
        }

    def _begin_window(self, window_minutes: int) -> None:
        self.window_start = self.next_window_start
        self.window_end = self.window_start + timedelta(minutes=window_minutes)
        self.next_window_start = None
        self.min_price = None
        self.max_price = None
        self.change_percent = ZERO
        self.rollback_min = None
        self.rollback_max = None
        self.target_reached = False
        self.last_reset_reason = ""

    def _apply_price(self, price: Decimal, change_target: Decimal) -> None:
        if self.min_price is None or price < self.min_price:
            self.min_price = price
        if self.max_price is None or price > self.max_price:
            self.max_price = price

        if self.min_price is not None and self.max_price is not None:
            self.change_percent = compute_change_percent(self.min_price, self.max_price)
            self.target_reached = self.change_percent >= change_target

    def _finalize_window(self, rollback_percent: Decimal) -> None:
        if self.min_price is None or self.max_price is None:
            return
        self.rollback_min, self.rollback_max = compute_rollback_levels(
            self.min_price,
            self.max_price,
            rollback_percent,
        )

    def _refresh_status(self) -> None:
        if self.window_start is None:
            if self.status != "остановлено":
                self.status = "ожидание окна"
            return

        if self.rollback_min is not None and self.rollback_max is not None:
            base_status = "контроль отката"
        else:
            base_status = "сбор диапазона"

        if self.target_reached:
            self.status = f"порог изменения достигнут, {base_status}"
        else:
            self.status = base_status


class MonitoringService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.profile = MonitoringProfile(
            tickers=settings.default_tickers,
            change_percent=settings.default_change_percent,
            window_minutes=settings.default_window_minutes,
            rollback_percent=settings.default_rollback_percent,
        )
        self._provider: PriceProvider | None = None
        self._provider_mode = "mock"
        self._provider_note = "Ожидание запуска мониторинга."
        self._rows: dict[str, TickerMonitorState] = {
            ticker: TickerMonitorState(ticker=ticker, name=ticker)
            for ticker in settings.default_tickers
        }
        self._task: asyncio.Task | None = None
        self._running = False

    async def start_monitoring(self, request: StartMonitoringRequest) -> None:
        await self._stop_loop()

        self.profile = MonitoringProfile(
            tickers=tuple(request.tickers),
            change_percent=request.change_percent,
            window_minutes=request.window_minutes,
            rollback_percent=request.rollback_percent,
        )

        provider, names, note = await build_price_provider(
            tickers=self.profile.tickers,
            tinkoff_token=self._settings.tinkoff_token,
            force_mock_provider=self._settings.force_mock_provider,
        )
        self._provider = provider
        self._provider_mode = provider.mode
        self._provider_note = note

        now = self._now()
        self._rows = {}
        for ticker in self.profile.tickers:
            row = TickerMonitorState(ticker=ticker, name=names.get(ticker, ticker))
            row.schedule_initial(now, self.profile.window_minutes)
            self._rows[ticker] = row

        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop_monitoring(self) -> None:
        await self._stop_loop()
        self._provider_mode = "mock"
        self._provider_note = "Мониторинг остановлен."
        for row in self._rows.values():
            row.stop()

    async def shutdown(self) -> None:
        await self._stop_loop()

    def snapshot(self) -> dict[str, object]:
        return {
            "server_time": format_datetime(self._now()),
            "mode": self._provider_mode,
            "mode_note": self._provider_note,
            "running": self._running,
            "settings": {
                "tickers": list(self.profile.tickers),
                "change_percent": format_decimal(self.profile.change_percent),
                "window_minutes": self.profile.window_minutes,
                "rollback_percent": format_decimal(self.profile.rollback_percent),
            },
            "rows": [row.to_payload() for row in self._rows.values()],
        }

    async def _run_loop(self) -> None:
        try:
            while self._running and self._provider is not None:
                prices = await self._safe_get_prices()
                now = self._now()
                for ticker, row in self._rows.items():
                    row.advance(now, prices.get(ticker), self.profile)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise

    async def _safe_get_prices(self) -> dict[str, Decimal]:
        if self._provider is None:
            return {}

        try:
            return await self._provider.get_prices()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._provider.close()
            provider, names, note = await build_price_provider(
                tickers=self.profile.tickers,
                tinkoff_token="",
                force_mock_provider=True,
            )
            self._provider = provider
            self._provider_mode = provider.mode
            self._provider_note = f"Провайдер переключён на mock после ошибки: {exc}. {note}"
            for ticker, row in self._rows.items():
                row.name = names.get(ticker, row.name)
            return await self._provider.get_prices()

    async def _stop_loop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._provider is not None:
            await self._provider.close()
            self._provider = None

    def _now(self) -> datetime:
        return datetime.now(self._settings.app_timezone)
