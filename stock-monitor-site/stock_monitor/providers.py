from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from random import Random
from typing import Sequence


class PriceProvider(ABC):
    mode = "unknown"

    @abstractmethod
    async def connect(self, tickers: Sequence[str]) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    async def get_prices(self) -> dict[str, Decimal]:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class MockPriceProvider(PriceProvider):
    mode = "mock"

    def __init__(self, seed: int = 7) -> None:
        self._rng = Random(seed)
        self._prices: dict[str, Decimal] = {}

    async def connect(self, tickers: Sequence[str]) -> dict[str, str]:
        self._prices.clear()
        names: dict[str, str] = {}

        for index, ticker in enumerate(tickers, start=1):
            base = Decimal("90") + Decimal(index * 11)
            offset = Decimal(str(self._rng.uniform(-3.0, 3.0)))
            self._prices[ticker] = base + offset
            names[ticker] = ticker

        return names

    async def get_prices(self) -> dict[str, Decimal]:
        prices: dict[str, Decimal] = {}

        for ticker, current in self._prices.items():
            drift = Decimal(str(self._rng.uniform(-0.75, 0.75)))
            next_price = current + drift
            if next_price <= Decimal("0"):
                next_price = Decimal("1")
            self._prices[ticker] = next_price
            prices[ticker] = next_price

        return prices

    async def close(self) -> None:
        self._prices.clear()


class TinkoffPriceProvider(PriceProvider):
    mode = "tinkoff"

    def __init__(self, token: str) -> None:
        self._token = token
        self._client_context = None
        self._client = None
        self._instrument_ids: dict[str, str] = {}
        self._instrument_names: dict[str, str] = {}
        self._quotation_to_decimal = None

    async def connect(self, tickers: Sequence[str]) -> dict[str, str]:
        try:
            from tinkoff.invest import AsyncClient
            from tinkoff.invest.utils import quotation_to_decimal
        except ImportError as exc:
            raise RuntimeError("Tinkoff SDK не установлен") from exc

        self._quotation_to_decimal = quotation_to_decimal
        self._client_context = AsyncClient(self._token)

        try:
            self._client = await self._client_context.__aenter__()
            for ticker in tickers:
                response = await self._client.instruments.find_instrument(query=ticker)
                instrument = next(
                    (
                        item
                        for item in response.instruments
                        if item.ticker.upper() == ticker.upper()
                    ),
                    None,
                )
                if instrument is None:
                    raise RuntimeError(f"Тикер {ticker} не найден в Tinkoff Invest API")

                instrument_id = instrument.uid or instrument.figi
                if not instrument_id:
                    raise RuntimeError(f"Не удалось определить instrument_id для {ticker}")

                self._instrument_ids[ticker] = instrument_id
                self._instrument_names[ticker] = instrument.name or ticker
        except Exception:
            await self.close()
            raise

        return dict(self._instrument_names)

    async def get_prices(self) -> dict[str, Decimal]:
        if self._client is None or self._quotation_to_decimal is None:
            raise RuntimeError("Tinkoff provider не подключен")

        response = await self._client.market_data.get_last_prices(
            instrument_id=list(self._instrument_ids.values())
        )

        price_by_instrument: dict[str, Decimal] = {}
        for last_price in response.last_prices:
            instrument_id = last_price.instrument_uid or last_price.figi
            if not instrument_id:
                continue
            price_by_instrument[instrument_id] = Decimal(
                str(self._quotation_to_decimal(last_price.price))
            )

        prices: dict[str, Decimal] = {}
        for ticker, instrument_id in self._instrument_ids.items():
            price = price_by_instrument.get(instrument_id)
            if price is not None:
                prices[ticker] = price

        return prices

    async def close(self) -> None:
        if self._client_context is not None:
            await self._client_context.__aexit__(None, None, None)
        self._client_context = None
        self._client = None
        self._quotation_to_decimal = None
        self._instrument_ids.clear()
        self._instrument_names.clear()


async def build_price_provider(
    tickers: Sequence[str],
    tinkoff_token: str,
    force_mock_provider: bool,
) -> tuple[PriceProvider, dict[str, str], str]:
    if tinkoff_token and not force_mock_provider:
        provider = TinkoffPriceProvider(tinkoff_token)
        try:
            names = await provider.connect(tickers)
            return provider, names, "Подключение к Tinkoff Invest API активно."
        except Exception as exc:
            await provider.close()
            fallback = MockPriceProvider()
            names = await fallback.connect(tickers)
            return fallback, names, f"Tinkoff недоступен, включён mock-режим: {exc}"

    provider = MockPriceProvider()
    names = await provider.connect(tickers)
    note = "Токен не задан или mock-режим принудительно включён."
    return provider, names, note
