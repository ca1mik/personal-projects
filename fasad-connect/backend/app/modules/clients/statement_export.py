"""Выписка по клиенту в XLSX — то, что заказчик ведёт руками в своей таблице.

Три листа в одном файле: сводка с балансом, разрез по заказам и лента
взаиморасчётов с бегущим остатком. Именно так устроен их «Ольга Ефимова.xlsx»:
сверху итог «сумма / оплата / разница», ниже строки по заказам и оплатам.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.xlsx import (
    Column,
    new_workbook,
    to_bytes,
    write_pairs,
    write_table,
    write_title,
)
from app.modules.clients.models import Client
from app.modules.clients.schemas import ClientStatementRead

ORDER_COLUMNS = [
    Column("Номер заказа", "order_number", width=16),
    Column("Дата", "created_at", "date", width=12),
    Column("Отгружен", "shipped_at", "date", width=12),
    Column("Направление", "direction_name", width=16),
    Column("Статус", "status_name", width=16),
    Column("Начислено", "charged", "money", width=14),
    Column("Оплачено", "paid", "money", width=14),
    Column("Долг", "due", "money", width=14),
    Column("Переплата", "overpaid", "money", width=14),
    Column("Оплат", "payments_count", "number", width=8),
]

LEDGER_COLUMNS = [
    Column("Дата", "happened_at", "datetime", width=18),
    Column("Событие", "kind_label", width=12),
    Column("Заказ", "order_number", width=14),
    Column("Начислено", "charged", "money", width=14),
    Column("Поступило", "paid", "money", width=14),
    Column("Откуда", "source", width=20),
    Column("Комментарий", "comment", width=32),
    Column("Баланс после", "balance_after", "money", width=15),
]


def _client_title(client: Client) -> str:
    return client.organization.strip() if client.organization else client.full_name


def statement_file_name(client: Client) -> str:
    return f"Взаиморасчёты {_client_title(client)}.xlsx"


def build_statement_xlsx(client: Client, statement: ClientStatementRead) -> bytes:
    balance = statement.balance
    book, sheet = new_workbook("Взаиморасчёты")

    row = write_title(sheet, 1, f"Взаиморасчёты: {_client_title(client)}")
    row = write_pairs(
        sheet,
        row + 1,
        [
            ("Клиент", client.full_name),
            ("Организация", client.organization or "—"),
            ("Телефон", client.phone or "—"),
            ("Почта", client.email or "—"),
            ("Заказов", balance.orders_count),
            ("Начислено", float(balance.charged)),
            ("Оплачено", float(balance.paid)),
            # Знак сохраняем как есть: минус читается как долг, и подменять его
            # словами в машинном файле нельзя — по колонке считают формулой.
            ("Разница", float(balance.balance)),
            ("Состояние", balance.status),
            ("Не закрыто заказов", balance.unpaid_orders),
            ("Долг по заказам", float(balance.due_total)),
        ],
    )

    row = write_title(sheet, row + 1, "Заказы", size=11)
    orders = [item.model_dump() for item in statement.orders]
    totals = {
        "order_number": "Итого",
        "charged": sum((Decimal(str(item["charged"])) for item in orders), Decimal("0")),
        "paid": sum((Decimal(str(item["paid"])) for item in orders), Decimal("0")),
        "due": sum((Decimal(str(item["due"])) for item in orders), Decimal("0")),
        "overpaid": sum((Decimal(str(item["overpaid"])) for item in orders), Decimal("0")),
    }
    row = write_table(sheet, row, ORDER_COLUMNS, orders, total_row=totals if orders else None)

    ledger_sheet = book.create_sheet("Лента расчётов")
    ledger_row = write_title(ledger_sheet, 1, "Начисления и поступления по времени")
    # В файле заказчика лента идёт сверху вниз от старых к новым, и «разница»
    # накапливается — так же и здесь, иначе бегущий остаток читается наоборот.
    ledger = [item.model_dump() for item in reversed(statement.ledger)]
    write_table(ledger_sheet, ledger_row + 1, LEDGER_COLUMNS, ledger)

    return to_bytes(book)
