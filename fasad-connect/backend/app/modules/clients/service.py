from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.exceptions import NotFoundError
from app.core.pagination import PageParams, pagination_meta
from app.modules.clients.models import Client, ClientDepositMovement
from app.modules.clients.phones import digits_only, phone_digits_expr, phone_variants
from app.modules.clients.repository import ClientRepository
from app.modules.clients.schemas import (
    ClientCalculationItem,
    ClientCreate,
    ClientOrderHistoryItem,
    ClientPurchaseTotals,
    ClientRead,
    ClientUpdate,
)
from app.modules.leads.models import Lead
from app.modules.leads.service import LeadService
from app.modules.leads.statuses import lead_status_label
from app.modules.orders.models import Order, OrderItem, OrderPayment

ITEMS_SUMMARY_LIMIT = 3


class ClientService:
    @staticmethod
    def list_clients(
        db: Session, params: PageParams, search: str | None
    ) -> tuple[list[Client], dict]:
        stmt = select(Client).order_by(Client.created_at.desc())
        count_stmt = select(func.count()).select_from(Client)
        if search:
            term = search.strip()
            pattern = f"%{term.lower()}%"
            conditions = [
                func.lower(Client.full_name).like(pattern),
                func.lower(func.coalesce(Client.organization, "")).like(pattern),
                func.lower(func.coalesce(Client.email, "")).like(pattern),
                func.lower(func.coalesce(Client.phone, "")).like(pattern),
                # Адрес спрашивают ради одного — «куда везти». Значит и искать
                # по нему будут так же: «кто у нас на Рахимова», когда машина
                # уже собирается в ту сторону.
                func.lower(func.coalesce(Client.address, "")).like(pattern),
            ]
            # Номер в базе и номер, набранный менеджером, почти никогда не
            # совпадают по строке: сравниваем отдельно по одним цифрам, иначе
            # подсказка по «8999…» не находит клиента, записанного как «+7999…».
            digits = digits_only(term)
            if len(digits) >= 3:
                stored_digits = phone_digits_expr()
                conditions.extend(
                    stored_digits.like(f"%{variant}%") for variant in phone_variants(digits)
                )
            criteria = or_(*conditions)
            stmt = stmt.where(criteria)
            count_stmt = count_stmt.where(criteria)
        total = db.scalar(count_stmt) or 0
        clients = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return clients, pagination_meta(total, params)

    @staticmethod
    def _batch_order_summaries(
        db: Session, client_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[datetime, Decimal, Decimal]]:
        """Дата последнего заказа и деньги (начислено/оплачено) по клиентам списком.

        Заказчик: «по клиентам больше инфы дай — когда заказ был последний,
        баланс». Одним запросом на всю страницу, а не по клиенту — иначе
        список из полусотни клиентов давал бы полсотни лишних запросов к базе
        (см. тот же приём в `ReportService.client_activity_report`).

        Возвращает `{client_id: (последний заказ, начислено, оплачено)}`.
        """
        if not client_ids:
            return {}

        orders_stmt = (
            select(
                Order.client_id,
                func.max(Order.created_at),
                func.coalesce(func.sum(Order.final_amount), 0),
            )
            .where(Order.client_id.in_(client_ids), Order.deleted_at.is_(None))
            .group_by(Order.client_id)
        )
        by_client: dict[uuid.UUID, tuple[datetime, Decimal, Decimal]] = {
            client_id: (last_order_at, Decimal(str(charged)), Decimal("0"))
            for client_id, last_order_at, charged in db.execute(orders_stmt).all()
        }

        paid_stmt = (
            select(Order.client_id, func.coalesce(func.sum(OrderPayment.amount), 0))
            .join(OrderPayment, OrderPayment.order_id == Order.id)
            .where(Order.client_id.in_(client_ids), Order.deleted_at.is_(None), OrderPayment.method != "deposit")
            .group_by(Order.client_id)
        )
        for client_id, paid in db.execute(paid_stmt).all():
            last_order_at, charged, _ = by_client[client_id]
            by_client[client_id] = (last_order_at, charged, Decimal(str(paid)))

        deposit_stmt = (
            select(
                ClientDepositMovement.client_id,
                ClientDepositMovement.kind,
                func.coalesce(func.sum(ClientDepositMovement.amount), 0),
            )
            .where(
                ClientDepositMovement.client_id.in_(client_ids),
                ClientDepositMovement.kind.in_(("topup", "withdrawal")),
            )
            .group_by(ClientDepositMovement.client_id, ClientDepositMovement.kind)
        )
        for client_id, kind, deposited in db.execute(deposit_stmt).all():
            last_order_at, charged, paid = by_client.get(client_id, (None, Decimal("0"), Decimal("0")))
            delta = Decimal(str(deposited)) * (-1 if kind == "withdrawal" else 1)
            by_client[client_id] = (last_order_at, charged, paid + delta)

        return by_client

    @staticmethod
    def balance_status_label(charged: Decimal, paid: Decimal) -> str:
        """Та же подпись, что и в полной выписке (`ClientStatementService`)."""
        balance = paid - charged
        if balance > 0:
            return "Аванс"
        if balance < 0:
            return "Долг"
        return "Расчёты закрыты" if charged > 0 else "Нет расчётов"

    @staticmethod
    def list_clients_with_summary(
        db: Session, params: PageParams, search: str | None
    ) -> tuple[list[ClientRead], dict]:
        clients, meta = ClientService.list_clients(db, params, search)
        summaries = ClientService._batch_order_summaries(db, [item.id for item in clients])

        result: list[ClientRead] = []
        for client in clients:
            data = ClientRead.model_validate(client)
            summary = summaries.get(client.id)
            if summary:
                last_order_at, charged, paid = summary
                data.last_order_at = last_order_at
                data.balance_status = ClientService.balance_status_label(charged, paid)
            result.append(data)
        return result, meta

    @staticmethod
    def create_client(db: Session, payload: ClientCreate) -> Client:
        client = Client(**payload.model_dump())
        db.add(client)
        db.commit()
        db.refresh(client)
        return client

    @staticmethod
    def update_client(db: Session, client_id: uuid.UUID, payload: ClientUpdate) -> Client:
        client = ClientService.get_client(db, client_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(client, key, value)
        db.commit()
        db.refresh(client)
        return client

    @staticmethod
    def get_client(db: Session, client_id: uuid.UUID) -> Client:
        client = ClientRepository.get_by_id(db, client_id)
        if not client:
            raise NotFoundError("Клиент не найден")
        return client

    @staticmethod
    def _items_summary(items: list[OrderItem]) -> str:
        """Состав заказа одной строкой: «Фасад 716×396, Фасад 716×296 и ещё 4»."""
        if not items:
            return ""
        head = [
            f"{item.name} {int(item.width)}×{int(item.height)}"
            for item in items[:ITEMS_SUMMARY_LIMIT]
        ]
        rest = len(items) - len(head)
        summary = ", ".join(head)
        return f"{summary} и ещё {rest}" if rest > 0 else summary

    @staticmethod
    def get_order_history(db: Session, client_id: uuid.UUID) -> list[ClientOrderHistoryItem]:
        orders = (
            db.scalars(
                select(Order)
                .options(
                    selectinload(Order.items),
                    joinedload(Order.status),
                    joinedload(Order.direction),
                )
                .where(Order.client_id == client_id, Order.deleted_at.is_(None))
                .order_by(Order.created_at.desc())
            )
            .unique()
            .all()
        )

        return [
            ClientOrderHistoryItem(
                id=order.id,
                order_number=order.order_number,
                created_at=order.created_at,
                final_amount=order.final_amount,
                currency=order.currency,
                status_name=order.status.name if order.status else None,
                direction_name=order.direction.name if order.direction else None,
                items_summary=ClientService._items_summary(list(order.items)),
                items_count=len(order.items),
            )
            for order in orders
        ]

    @staticmethod
    def get_calculations(db: Session, client_id: uuid.UUID) -> list[ClientCalculationItem]:
        """Расчёты клиента: и ждущие ответа, и ставшие заказами.

        Заказчик: «сдала клиента, 2 заказа посчитала, но их здесь нет». Заявка —
        это посчитанное, но ещё не купленное: в выручку ей нельзя, а теряться из
        карточки нельзя тем более, иначе менеджер не помнит, кому что называл.

        Рядом с заявкой показываем заказ, если он из неё вырос: так видно, что
        расчёт закончился делом, а не остался висеть.
        """
        leads = db.scalars(
            select(Lead)
            .options(selectinload(Lead.orders.and_(Order.deleted_at.is_(None))))
            .where(Lead.client_id == client_id, Lead.deleted_at.is_(None))
            .order_by(Lead.created_at.desc())
        ).all()

        items: list[ClientCalculationItem] = []
        for lead in leads:
            summary = LeadService.build_summary(lead)
            order = lead.orders[0] if lead.orders else None
            items.append(
                ClientCalculationItem(
                    id=lead.id,
                    lead_number=lead.lead_number,
                    created_at=lead.created_at,
                    due_date=lead.due_date,
                    status=lead.status,
                    status_label=lead_status_label(lead.status),
                    quantity=summary.quantity,
                    facade_area_sqm=summary.facade_area_sqm,
                    estimated_amount=summary.estimated_amount,
                    order_id=order.id if order else None,
                    order_number=order.order_number if order else None,
                    currency=summary.currency,
                )
            )
        return items

    @staticmethod
    def get_purchase_totals(history: list[ClientOrderHistoryItem]) -> ClientPurchaseTotals:
        """Сводка по покупкам. Основа отчётов ТЗ «кто давно не покупал» и «сумма за период»."""
        if not history:
            return ClientPurchaseTotals()

        dates = [item.created_at for item in history]
        last_order_at = max(dates)
        reference = last_order_at
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)

        return ClientPurchaseTotals(
            orders_count=len(history),
            total_amount=sum((item.final_amount for item in history), Decimal("0")),
            currency=history[0].currency,
            first_order_at=min(dates),
            last_order_at=last_order_at,
            days_since_last_order=(datetime.now(UTC) - reference).days,
        )
