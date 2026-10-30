"""Взаиморасчёты с клиентом: баланс, история и выписка.

Заказчик ведёт это в тетради-таблице (файл «Ольга Ефимова.xlsx»): столбцы
«сумма / оплата / разница», и сверху общий итог. Здесь то же самое, только
считается само и не расходится с заказами.

Правило одно: **заказ начисляет долг, оплата его гасит**. Баланс — оплачено
минус начислено. Плюс значит аванс или переплату, минус — долг клиента.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.clients.models import Client
from app.modules.clients.models import ClientDepositMovement
from app.modules.clients.schemas import (
    ClientBalanceRead,
    ClientLedgerEntry,
    ClientOrderSettlement,
    ClientStatementRead,
)
from app.modules.orders.models import Order
from app.modules.orders.payments import payment_method_label

MONEY = Decimal("0.01")


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (ArithmeticError, TypeError, ValueError):
        return Decimal("0")


def _as_utc(moment: datetime | None) -> datetime:
    """Единая шкала времени для сортировки.

    В базе часть дат приходит без часового пояса. Складывать их с датами в UTC
    напрямую нельзя — сравнение падает, а лента взаиморасчётов должна строиться
    строго по времени.
    """
    if moment is None:
        return datetime.min.replace(tzinfo=UTC)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class ClientStatementService:
    @staticmethod
    def _orders(db: Session, client_id: uuid.UUID) -> list[Order]:
        return list(
            db.scalars(
                select(Order)
                .options(
                    selectinload(Order.payments),
                    joinedload(Order.status),
                    joinedload(Order.direction),
                )
                .where(Order.client_id == client_id, Order.deleted_at.is_(None))
                .order_by(Order.created_at.asc())
            )
            .unique()
            .all()
        )

    @staticmethod
    def build(db: Session, client: Client) -> ClientStatementRead:
        orders = ClientStatementService._orders(db, client.id)

        # --- лента событий: начисления и поступления вперемешку, по времени ---
        events: list[tuple[datetime, int, ClientLedgerEntry]] = []
        for order in orders:
            charged = _money(order.final_amount)
            events.append(
                (
                    _as_utc(order.created_at),
                    0,  # заказ идёт раньше оплаты той же секунды: сначала долг
                    ClientLedgerEntry(
                        kind="order",
                        kind_label="Заказ",
                        happened_at=_as_utc(order.created_at),
                        order_id=order.id,
                        order_number=order.order_number,
                        charged=charged,
                        paid=Decimal("0"),
                        source=order.direction.name if order.direction else None,
                        comment=order.status.name if order.status else None,
                    ),
                )
            )
            for payment in order.payments:
                events.append(
                    (
                        _as_utc(payment.paid_at),
                        1,
                        ClientLedgerEntry(
                            kind="payment",
                            kind_label="Оплата",
                            happened_at=_as_utc(payment.paid_at),
                            order_id=order.id,
                            order_number=order.order_number,
                            charged=Decimal("0"),
                            paid=Decimal("0") if payment.method == "deposit" else _money(payment.amount),
                            # «откуда поступление» — способ оплаты по-русски
                            source=payment_method_label(payment.method),
                            comment=(f"Списано с депозита: {payment.amount}" if payment.method == "deposit" else payment.comment),
                        ),
                    )
                )

        deposits = list(db.scalars(select(ClientDepositMovement).where(
            ClientDepositMovement.client_id == client.id,
            ClientDepositMovement.kind.in_(("topup", "withdrawal")),
        )))
        for deposit in deposits:
            outgoing = deposit.kind == "withdrawal"
            events.append((
                _as_utc(deposit.created_at), 1,
                ClientLedgerEntry(
                    kind="deposit_withdrawal" if outgoing else "deposit",
                    kind_label="Корректировка депозита" if outgoing else "Депозит",
                    happened_at=_as_utc(deposit.created_at),
                    paid=-_money(deposit.amount) if outgoing else _money(deposit.amount),
                    source=payment_method_label(deposit.method or "other"),
                    comment=deposit.comment,
                ),
            ))

        events.sort(key=lambda item: (item[0], item[1]))

        running = Decimal("0")
        ledger: list[ClientLedgerEntry] = []
        for _, _, entry in events:
            # Баланс после события: оплата поднимает, заказ опускает. Именно эту
            # колонку заказчик ведёт руками как «разница».
            running += entry.paid - entry.charged
            entry.balance_after = running
            ledger.append(entry)

        # --- разрез по заказам: сколько начислено, сколько закрыто ---
        settlements: list[ClientOrderSettlement] = []
        for order in orders:
            charged = _money(order.final_amount)
            paid = _money(sum((Decimal(str(item.amount)) for item in order.payments), Decimal("0")))
            settlements.append(
                ClientOrderSettlement(
                    order_id=order.id,
                    order_number=order.order_number,
                    created_at=_as_utc(order.created_at),
                    shipped_at=_as_utc(order.shipped_at) if order.shipped_at else None,
                    status_name=order.status.name if order.status else None,
                    direction_name=order.direction.name if order.direction else None,
                    charged=charged,
                    paid=paid,
                    # По заказу показываем именно остаток к оплате, а не баланс:
                    # переплата по одному заказу не гасит долг по другому сама
                    # собой, это решает менеджер. Через _money — чтобы ноль
                    # выглядел как «0.00», а не «0»: колонку читают как деньги.
                    due=_money(max(charged - paid, Decimal("0"))),
                    overpaid=_money(max(paid - charged, Decimal("0"))),
                    payments_count=len(order.payments),
                    currency=order.currency,
                )
            )
        settlements.sort(key=lambda item: item.created_at, reverse=True)

        charged_total = _money(sum((item.charged for item in settlements), Decimal("0")))
        paid_total = _money(
            sum((payment.amount for order in orders for payment in order.payments if payment.method != "deposit"), Decimal("0"))
            + sum(((-deposit.amount if deposit.kind == "withdrawal" else deposit.amount) for deposit in deposits), Decimal("0"))
        )
        balance = _money(paid_total - charged_total)

        if balance > 0:
            status = "Аванс"
        elif balance < 0:
            status = "Долг"
        else:
            status = "Расчёты закрыты" if charged_total > 0 else "Нет расчётов"

        currency = next((item.currency for item in settlements if item.currency), "RUB")

        return ClientStatementRead(
            balance=ClientBalanceRead(
                charged=charged_total,
                paid=paid_total,
                balance=balance,
                status=status,
                currency=currency,
                orders_count=len(settlements),
                unpaid_orders=sum(1 for item in settlements if item.due > 0),
                due_total=_money(sum((item.due for item in settlements), Decimal("0"))),
            ),
            orders=settlements,
            ledger=list(reversed(ledger)),
        )
