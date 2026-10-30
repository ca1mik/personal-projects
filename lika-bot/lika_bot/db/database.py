from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Iterable

import aiosqlite

from lika_bot.db.schema import SCHEMA_SQL


class Database:
    """Thin async wrapper around a single SQLite connection."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self._path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON;")
        await self._connection.execute("PRAGMA journal_mode = WAL;")
        await self._connection.execute("PRAGMA busy_timeout = 3000;")
        await self._connection.commit()
        await self.execute_script(SCHEMA_SQL)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def execute(self, query: str, parameters: Iterable[Any] = ()) -> aiosqlite.Cursor:
        async with self._lock:
            connection = self._ensure_connection()
            cursor = await connection.execute(query, tuple(parameters))
            await connection.commit()
            return cursor

    async def executemany(self, query: str, seq_of_parameters: Iterable[Iterable[Any]]) -> None:
        async with self._lock:
            connection = self._ensure_connection()
            await connection.executemany(query, [tuple(item) for item in seq_of_parameters])
            await connection.commit()

    async def execute_script(self, script: str) -> None:
        async with self._lock:
            connection = self._ensure_connection()
            await connection.executescript(script)
            await connection.commit()

    async def fetchone(self, query: str, parameters: Iterable[Any] = ()) -> aiosqlite.Row | None:
        async with self._lock:
            connection = self._ensure_connection()
            cursor = await connection.execute(query, tuple(parameters))
            return await cursor.fetchone()

    async def fetchall(self, query: str, parameters: Iterable[Any] = ()) -> list[aiosqlite.Row]:
        async with self._lock:
            connection = self._ensure_connection()
            cursor = await connection.execute(query, tuple(parameters))
            return await cursor.fetchall()

    async def fetchval(self, query: str, parameters: Iterable[Any] = ()) -> Any:
        row = await self.fetchone(query, parameters)
        if row is None:
            return None
        return row[0]

    def _ensure_connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database connection is not initialized.")
        return self._connection
