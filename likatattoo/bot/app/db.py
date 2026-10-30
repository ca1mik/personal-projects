from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite


@dataclass(frozen=True)
class PackPaymentResult:
    applied: bool
    balance: int


@dataclass(frozen=True)
class DepositPaymentResult:
    applied: bool


@dataclass(frozen=True)
class BookingRequestResult:
    request_id: int


@dataclass(frozen=True)
class BookingRequestRecord:
    request_id: int
    user_id: int
    username: str | None
    full_name: str | None
    idea: str
    size: str
    placement: str
    preferred_date: str
    contact: str
    status: str
    source: str
    details_json: str
    created_at: str
    status_updated_at: str | None


@dataclass(frozen=True)
class CrmStatsRecord:
    status_counts: dict[str, int]
    total: int
    stale_leads: list[dict[str, Any]]  # без движения >7 дней


@dataclass(frozen=True)
class PaymentSummaryRecord:
    payment_id: int
    user_id: int
    channel: str  # robokassa | telegram-stars
    offer_title: str
    amount_rub: int
    status: str
    paid_at: str | None
    created_at: str


@dataclass(frozen=True)
class RobokassaInvoiceRecord:
    invoice_id: int
    user_id: int
    offer_code: str
    offer_title: str
    description: str
    amount_rub: int
    amount_text: str
    receipt_json: str
    payment_url: str
    signature_value: str
    status: str
    email: str | None
    payment_method: str | None
    op_key: str | None
    shp_json: str
    callback_raw_json: str | None
    created_at: str
    updated_at: str
    paid_at: str | None


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    sketch_balance INTEGER NOT NULL DEFAULT 0,
                    free_generations_granted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    credits_added INTEGER NOT NULL DEFAULT 0,
                    provider_charge_id TEXT,
                    telegram_charge_id TEXT,
                    raw_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    user_prompt TEXT NOT NULL,
                    final_prompt TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    offer_code TEXT NOT NULL DEFAULT 'session',
                    offer_title TEXT NOT NULL DEFAULT 'Предоплата за сеанс',
                    amount_rub INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    telegram_charge_id TEXT,
                    provider_charge_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS booking_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    idea TEXT NOT NULL,
                    size TEXT NOT NULL,
                    placement TEXT NOT NULL,
                    preferred_date TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    source TEXT NOT NULL DEFAULT 'telegram-bot',
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    status_updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS robokassa_invoices (
                    invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    offer_code TEXT NOT NULL,
                    offer_title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount_rub INTEGER NOT NULL,
                    amount_text TEXT NOT NULL DEFAULT '',
                    receipt_json TEXT NOT NULL DEFAULT '',
                    payment_url TEXT NOT NULL DEFAULT '',
                    signature_value TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'created',
                    email TEXT,
                    payment_method TEXT,
                    op_key TEXT,
                    shp_json TEXT NOT NULL DEFAULT '{}',
                    callback_raw_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    paid_at TEXT
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_telegram_charge
                ON payments(telegram_charge_id)
                WHERE telegram_charge_id IS NOT NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_provider_charge
                ON payments(provider_charge_id)
                WHERE provider_charge_id IS NOT NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS idx_deposits_telegram_charge
                ON deposits(telegram_charge_id)
                WHERE telegram_charge_id IS NOT NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS idx_deposits_provider_charge
                ON deposits(provider_charge_id)
                WHERE provider_charge_id IS NOT NULL;

                CREATE UNIQUE INDEX IF NOT EXISTS idx_robokassa_invoices_op_key
                ON robokassa_invoices(op_key)
                WHERE op_key IS NOT NULL;
                """
            )
            await self._ensure_column(
                db,
                table_name="users",
                column_name="free_generations_granted",
                column_definition="INTEGER NOT NULL DEFAULT 0",
            )
            await self._ensure_column(
                db,
                table_name="deposits",
                column_name="offer_code",
                column_definition="TEXT NOT NULL DEFAULT 'session'",
            )
            await self._ensure_column(
                db,
                table_name="deposits",
                column_name="offer_title",
                column_definition="TEXT NOT NULL DEFAULT 'Предоплата за сеанс'",
            )
            await self._ensure_column(
                db,
                table_name="booking_requests",
                column_name="source",
                column_definition="TEXT NOT NULL DEFAULT 'telegram-bot'",
            )
            await self._ensure_column(
                db,
                table_name="booking_requests",
                column_name="details_json",
                column_definition="TEXT NOT NULL DEFAULT '{}'",
            )
            await self._ensure_column(
                db,
                table_name="booking_requests",
                column_name="status_updated_at",
                column_definition="TEXT",
            )
            await db.commit()

    async def upsert_user(
        self,
        user_id: int,
        username: str | None,
        full_name: str | None,
        *,
        starter_credits: int = 0,
    ) -> None:
        should_grant_free = 1 if starter_credits > 0 else 0
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO users (
                    user_id, username, full_name, sketch_balance, free_generations_granted
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    sketch_balance = CASE
                        WHEN users.free_generations_granted = 0
                        THEN users.sketch_balance + excluded.sketch_balance
                        ELSE users.sketch_balance
                    END,
                    free_generations_granted = CASE
                        WHEN users.free_generations_granted = 0
                        THEN excluded.free_generations_granted
                        ELSE users.free_generations_granted
                    END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, username, full_name, starter_credits, should_grant_free),
            )
            await db.commit()

    async def get_balance(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            return await self._get_balance_on_connection(db, user_id)

    async def add_credits(self, user_id: int, credits: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, sketch_balance)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    sketch_balance = sketch_balance + excluded.sketch_balance,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, credits),
            )
            await db.commit()
            return await self._get_balance_on_connection(db, user_id)

    async def consume_credit(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                UPDATE users
                SET sketch_balance = sketch_balance - 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND sketch_balance > 0
                """,
                (user_id,),
            )
            updated = cursor.rowcount > 0
            balance = await self._get_balance_on_connection(db, user_id)
            await db.commit()
            return balance if updated else max(balance, 0)

    async def apply_pack_payment(
        self,
        *,
        user_id: int,
        payload: str,
        amount: int,
        currency: str,
        credits_added: int,
        provider_charge_id: str | None,
        telegram_charge_id: str | None,
        raw: dict[str, Any],
    ) -> PackPaymentResult:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            if await self._payment_already_processed(db, telegram_charge_id, provider_charge_id):
                balance = await self._get_balance_on_connection(db, user_id)
                await db.commit()
                return PackPaymentResult(applied=False, balance=balance)

            await db.execute(
                """
                INSERT INTO users (user_id, sketch_balance)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    sketch_balance = sketch_balance + excluded.sketch_balance,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, credits_added),
            )
            await db.execute(
                """
                INSERT INTO payments (
                    user_id, payload, amount, currency, credits_added,
                    provider_charge_id, telegram_charge_id, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    payload,
                    amount,
                    currency,
                    credits_added,
                    provider_charge_id,
                    telegram_charge_id,
                    json.dumps(raw, ensure_ascii=False),
                ),
            )
            balance = await self._get_balance_on_connection(db, user_id)
            await db.commit()
            return PackPaymentResult(applied=True, balance=balance)

    async def record_deposit_payment(
        self,
        *,
        user_id: int,
        payload: str,
        offer_code: str,
        offer_title: str,
        amount: int,
        currency: str,
        amount_rub: int,
        status: str,
        telegram_charge_id: str | None,
        provider_charge_id: str | None,
        raw: dict[str, Any],
    ) -> DepositPaymentResult:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            if await self._deposit_already_processed(db, telegram_charge_id, provider_charge_id):
                await db.commit()
                return DepositPaymentResult(applied=False)

            await db.execute(
                """
                INSERT INTO deposits (
                    user_id, offer_code, offer_title, amount_rub, status, telegram_charge_id, provider_charge_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    offer_code,
                    offer_title,
                    amount_rub,
                    status,
                    telegram_charge_id,
                    provider_charge_id,
                ),
            )
            await db.execute(
                """
                INSERT INTO payments (
                    user_id, payload, amount, currency, credits_added,
                    provider_charge_id, telegram_charge_id, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    payload,
                    amount,
                    currency,
                    0,
                    provider_charge_id,
                    telegram_charge_id,
                    json.dumps(raw, ensure_ascii=False),
                ),
            )
            await db.commit()
            return DepositPaymentResult(applied=True)

    async def log_generation(
        self,
        *,
        user_id: int,
        user_prompt: str,
        final_prompt: str,
        image_path: Path,
        model: str,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO generations (user_id, user_prompt, final_prompt, image_path, model)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, user_prompt, final_prompt, str(image_path), model),
            )
            await db.commit()

    async def create_booking_request(
        self,
        *,
        user_id: int,
        username: str | None,
        full_name: str | None,
        idea: str,
        size: str,
        placement: str,
        preferred_date: str,
        contact: str,
        status: str = "new",
        source: str = "telegram-bot",
        details_json: str = "{}",
    ) -> BookingRequestResult:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO booking_requests (
                    user_id, username, full_name, idea, size, placement,
                    preferred_date, contact, status, source, details_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    full_name,
                    idea,
                    size,
                    placement,
                    preferred_date,
                    contact,
                    status,
                    source,
                    details_json,
                ),
            )
            await db.commit()
            request_id = cursor.lastrowid
            if request_id is None:
                raise RuntimeError("Booking request ID was not returned by SQLite.")
            return BookingRequestResult(request_id=request_id)

    async def create_robokassa_invoice_draft(
        self,
        *,
        user_id: int,
        offer_code: str,
        offer_title: str,
        description: str,
        amount_rub: int,
        amount_text: str,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO robokassa_invoices (
                    user_id, offer_code, offer_title, description, amount_rub, amount_text
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, offer_code, offer_title, description, amount_rub, amount_text),
            )
            await db.commit()
            invoice_id = cursor.lastrowid
            if invoice_id is None:
                raise RuntimeError("Robokassa invoice ID was not returned by SQLite.")
            return int(invoice_id)

    async def finalize_robokassa_invoice(
        self,
        *,
        invoice_id: int,
        receipt_json: str,
        payment_url: str,
        signature_value: str,
        shp_json: str,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE robokassa_invoices
                SET receipt_json = ?,
                    payment_url = ?,
                    signature_value = ?,
                    shp_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE invoice_id = ?
                """,
                (receipt_json, payment_url, signature_value, shp_json, invoice_id),
            )
            await db.commit()

    async def get_robokassa_invoice(self, invoice_id: int) -> RobokassaInvoiceRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT
                    invoice_id, user_id, offer_code, offer_title, description, amount_rub, amount_text,
                    receipt_json, payment_url, signature_value, status, email, payment_method, op_key,
                    shp_json, callback_raw_json, created_at, updated_at, paid_at
                FROM robokassa_invoices
                WHERE invoice_id = ?
                LIMIT 1
                """,
                (invoice_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return RobokassaInvoiceRecord(
            invoice_id=int(row[0]),
            user_id=int(row[1]),
            offer_code=str(row[2]),
            offer_title=str(row[3]),
            description=str(row[4]),
            amount_rub=int(row[5]),
            amount_text=str(row[6]),
            receipt_json=str(row[7]),
            payment_url=str(row[8]),
            signature_value=str(row[9]),
            status=str(row[10]),
            email=str(row[11]) if row[11] is not None else None,
            payment_method=str(row[12]) if row[12] is not None else None,
            op_key=str(row[13]) if row[13] is not None else None,
            shp_json=str(row[14]),
            callback_raw_json=str(row[15]) if row[15] is not None else None,
            created_at=str(row[16]),
            updated_at=str(row[17]),
            paid_at=str(row[18]) if row[18] is not None else None,
        )

    async def apply_robokassa_result(
        self,
        *,
        invoice_id: int,
        out_sum_minor: int,
        currency: str,
        email: str | None,
        payment_method: str | None,
        op_key: str | None,
        callback_payload: dict[str, Any],
    ) -> DepositPaymentResult:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")

            cursor = await db.execute(
                """
                SELECT
                    invoice_id, user_id, offer_code, offer_title, amount_rub, status
                FROM robokassa_invoices
                WHERE invoice_id = ?
                LIMIT 1
                """,
                (invoice_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                await db.commit()
                return DepositPaymentResult(applied=False)

            stored_amount_rub = int(row[4])
            if out_sum_minor != stored_amount_rub * 100 or str(row[5]) == "paid":
                await db.commit()
                return DepositPaymentResult(applied=False)

            provider_charge_id = op_key or f"robokassa-invoice-{invoice_id}"
            if await self._deposit_already_processed(db, None, provider_charge_id):
                await db.execute(
                    """
                    UPDATE robokassa_invoices
                    SET status = 'paid',
                        email = COALESCE(?, email),
                        payment_method = COALESCE(?, payment_method),
                        op_key = COALESCE(?, op_key),
                        callback_raw_json = ?,
                        paid_at = COALESCE(paid_at, CURRENT_TIMESTAMP),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE invoice_id = ?
                    """,
                    (
                        email,
                        payment_method,
                        op_key,
                        json.dumps(callback_payload, ensure_ascii=False),
                        invoice_id,
                    ),
                )
                await db.commit()
                return DepositPaymentResult(applied=False)

            user_id = int(row[1])
            offer_code = str(row[2])
            offer_title = str(row[3])
            await db.execute(
                """
                INSERT INTO deposits (
                    user_id, offer_code, offer_title, amount_rub, status, telegram_charge_id, provider_charge_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, offer_code, offer_title, stored_amount_rub, "paid", None, provider_charge_id),
            )
            await db.execute(
                """
                INSERT INTO payments (
                    user_id, payload, amount, currency, credits_added,
                    provider_charge_id, telegram_charge_id, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    f"service:{offer_code}",
                    out_sum_minor,
                    currency,
                    0,
                    provider_charge_id,
                    None,
                    json.dumps(callback_payload, ensure_ascii=False),
                ),
            )
            await db.execute(
                """
                UPDATE robokassa_invoices
                SET status = 'paid',
                    email = COALESCE(?, email),
                    payment_method = COALESCE(?, payment_method),
                    op_key = COALESCE(?, op_key),
                    callback_raw_json = ?,
                    paid_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE invoice_id = ?
                """,
                (
                    email,
                    payment_method,
                    op_key,
                    json.dumps(callback_payload, ensure_ascii=False),
                    invoice_id,
                ),
            )
            await db.commit()
            return DepositPaymentResult(applied=True)

    async def list_booking_requests(self, *, limit: int = 10) -> list[BookingRequestRecord]:
        safe_limit = max(limit, 1)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT
                    id, user_id, username, full_name, idea, size, placement,
                    preferred_date, contact, status, source, details_json, created_at,
                    status_updated_at
                FROM booking_requests
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
            rows = await cursor.fetchall()

        return [
            BookingRequestRecord(
                request_id=int(row[0]),
                user_id=int(row[1]),
                username=str(row[2]) if row[2] is not None else None,
                full_name=str(row[3]) if row[3] is not None else None,
                idea=str(row[4]),
                size=str(row[5]),
                placement=str(row[6]),
                preferred_date=str(row[7]),
                contact=str(row[8]),
                status=str(row[9]),
                source=str(row[10]),
                details_json=str(row[11]),
                created_at=str(row[12]),
                status_updated_at=str(row[13]) if row[13] is not None else None,
            )
            for row in rows
        ]

    async def count_booking_requests_by_status(self) -> dict[str, int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT status, COUNT(*)
                FROM booking_requests
                GROUP BY status
                ORDER BY status
                """
            )
            rows = await cursor.fetchall()
        return {str(status): int(count) for status, count in rows}

    async def update_booking_request_status(self, request_id: int, status: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE booking_requests
                SET status = ?, status_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, request_id),
            )
            await db.commit()
        return cursor.rowcount > 0

    async def get_crm_stats(self) -> CrmStatsRecord:
        """Агрегат по статусам + список лидов без движения >7 дней."""
        async with aiosqlite.connect(self.db_path) as db:
            # Подсчёт по статусам
            cursor = await db.execute(
                """
                SELECT status, COUNT(*) FROM booking_requests GROUP BY status
                """
            )
            rows = await cursor.fetchall()
            status_counts: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
            total = sum(status_counts.values())

            # Лиды без движения >7 дней (не в архиве и не done)
            cursor = await db.execute(
                """
                SELECT id, COALESCE(full_name, username, 'Без имени'), status,
                       contact, idea,
                       COALESCE(status_updated_at, created_at) AS last_touch,
                       CAST(julianday('now') - julianday(COALESCE(status_updated_at, created_at)) AS INTEGER) AS days_stale
                FROM booking_requests
                WHERE status NOT IN ('done', 'archive')
                  AND CAST(julianday('now') - julianday(COALESCE(status_updated_at, created_at)) AS INTEGER) > 7
                ORDER BY days_stale DESC
                LIMIT 20
                """
            )
            stale_rows = await cursor.fetchall()

        stale_leads = [
            {
                "id": int(r[0]),
                "name": str(r[1]),
                "status": str(r[2]),
                "contact": str(r[3]),
                "idea": str(r[4]),
                "last_touch": str(r[5]),
                "days_stale": int(r[6]),
            }
            for r in stale_rows
        ]
        return CrmStatsRecord(
            status_counts=status_counts,
            total=total,
            stale_leads=stale_leads,
        )

    async def list_payments_for_crm(self, *, limit: int = 50) -> list[PaymentSummaryRecord]:
        """Объединяет платежи из deposits (Stars + Telegram) и robokassa_invoices."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT
                    d.id,
                    d.user_id,
                    'telegram-stars' AS channel,
                    d.offer_title,
                    d.amount_rub,
                    d.status,
                    NULL AS paid_at,
                    d.created_at
                FROM deposits d
                WHERE d.offer_code != 'robokassa'

                UNION ALL

                SELECT
                    ri.invoice_id,
                    ri.user_id,
                    'robokassa' AS channel,
                    ri.offer_title,
                    ri.amount_rub,
                    ri.status,
                    ri.paid_at,
                    ri.created_at
                FROM robokassa_invoices ri

                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()

        return [
            PaymentSummaryRecord(
                payment_id=int(r[0]),
                user_id=int(r[1]),
                channel=str(r[2]),
                offer_title=str(r[3]),
                amount_rub=int(r[4]),
                status=str(r[5]),
                paid_at=str(r[6]) if r[6] is not None else None,
                created_at=str(r[7]),
            )
            for r in rows
        ]

    async def _get_balance_on_connection(self, db: aiosqlite.Connection, user_id: int) -> int:
        cursor = await db.execute(
            "SELECT sketch_balance FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def _payment_already_processed(
        self,
        db: aiosqlite.Connection,
        telegram_charge_id: str | None,
        provider_charge_id: str | None,
    ) -> bool:
        cursor = await db.execute(
            """
            SELECT 1
            FROM payments
            WHERE (? IS NOT NULL AND telegram_charge_id = ?)
               OR (? IS NOT NULL AND provider_charge_id = ?)
            LIMIT 1
            """,
            (
                telegram_charge_id,
                telegram_charge_id,
                provider_charge_id,
                provider_charge_id,
            ),
        )
        return await cursor.fetchone() is not None

    async def _deposit_already_processed(
        self,
        db: aiosqlite.Connection,
        telegram_charge_id: str | None,
        provider_charge_id: str | None,
    ) -> bool:
        cursor = await db.execute(
            """
            SELECT 1
            FROM deposits
            WHERE (? IS NOT NULL AND telegram_charge_id = ?)
               OR (? IS NOT NULL AND provider_charge_id = ?)
            LIMIT 1
            """,
            (
                telegram_charge_id,
                telegram_charge_id,
                provider_charge_id,
                provider_charge_id,
            ),
        )
        return await cursor.fetchone() is not None

    async def _ensure_column(
        self,
        db: aiosqlite.Connection,
        *,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        cursor = await db.execute(f"PRAGMA table_info({table_name})")
        columns = await cursor.fetchall()
        column_names = {str(column[1]) for column in columns}
        if column_name not in column_names:
            await db.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )
