"""Client money held on account until allocated to an order."""

from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.audit.service import AuditService
from app.modules.clients.models import ClientDepositMovement
from app.modules.clients.schemas import (
    ClientDepositCorrection,
    ClientDepositCreate,
    ClientDepositMovementRead,
    ClientDepositRead,
    ClientDepositWithdrawalCreate,
)
from app.modules.orders.payments import PAYMENT_METHODS


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ClientDepositService:
    @staticmethod
    def read(db: Session, client_id: uuid.UUID) -> ClientDepositRead:
        movements = list(db.scalars(
            select(ClientDepositMovement)
            .where(ClientDepositMovement.client_id == client_id)
            .order_by(ClientDepositMovement.created_at.desc(), ClientDepositMovement.id.desc())
        ))
        balance = sum((m.amount if m.kind in ("topup", "return") else -m.amount for m in movements), Decimal("0"))
        return ClientDepositRead(
            balance=_money(balance),
            movements=[ClientDepositMovementRead.model_validate(m) for m in movements],
        )

    @staticmethod
    def topup(db: Session, client_id: uuid.UUID, payload: ClientDepositCreate, user_id: uuid.UUID) -> ClientDepositRead:
        if payload.method not in PAYMENT_METHODS or payload.method == "deposit":
            raise AppError("Неизвестный способ внесения депозита", 422)
        movement = ClientDepositMovement(
            client_id=client_id, amount=_money(payload.amount), kind="topup",
            method=payload.method, comment=payload.comment, created_by=user_id,
        )
        db.add(movement)
        AuditService.log_event(
            db, entity_type="client", entity_id=str(client_id), action="deposit_topup",
            user_id=str(user_id), new_value={"amount": movement.amount, "method": movement.method},
        )
        db.commit()
        return ClientDepositService.read(db, client_id)

    @staticmethod
    def correct_topup(
        db: Session,
        client_id: uuid.UUID,
        movement_id: uuid.UUID,
        payload: ClientDepositCorrection,
        user_id: uuid.UUID,
    ) -> ClientDepositRead:
        movement = db.scalar(
            select(ClientDepositMovement).where(
                ClientDepositMovement.id == movement_id,
                ClientDepositMovement.client_id == client_id,
                ClientDepositMovement.kind == "topup",
            )
        )
        if movement is None:
            raise AppError("Пополнение депозита не найдено", 404)

        reason = payload.reason.strip()
        if not reason:
            raise AppError("Укажите причину исправления суммы", 422)

        corrected_amount = _money(payload.amount)
        original_amount = movement.amount
        balance_after = ClientDepositService.read(db, client_id).balance + corrected_amount - original_amount
        if balance_after < 0:
            raise AppError("Нельзя уменьшить пополнение ниже уже потраченной суммы", 422)
        if corrected_amount == original_amount:
            raise AppError("Новая сумма совпадает с текущей", 422)

        movement.amount = corrected_amount
        AuditService.log_event(
            db,
            entity_type="client",
            entity_id=str(client_id),
            action="deposit_topup_corrected",
            user_id=str(user_id),
            old_value={"movement_id": str(movement_id), "amount": original_amount},
            new_value={"movement_id": str(movement_id), "amount": corrected_amount, "reason": reason},
        )
        db.commit()
        return ClientDepositService.read(db, client_id)

    @staticmethod
    def withdraw(db: Session, client_id: uuid.UUID, payload: ClientDepositWithdrawalCreate, user_id: uuid.UUID) -> ClientDepositRead:
        if payload.method not in PAYMENT_METHODS or payload.method == "deposit":
            raise AppError("Неизвестный способ возврата депозита", 422)
        if not payload.comment.strip():
            raise AppError("Укажите причину корректировки депозита", 422)
        if _money(payload.amount) > ClientDepositService.read(db, client_id).balance:
            raise AppError("Недостаточно денег на депозите клиента", 422)
        movement = ClientDepositMovement(
            client_id=client_id, amount=_money(payload.amount), kind="withdrawal",
            method=payload.method, comment=payload.comment.strip(), created_by=user_id,
        )
        db.add(movement)
        AuditService.log_event(
            db, entity_type="client", entity_id=str(client_id), action="deposit_withdrawal",
            user_id=str(user_id), new_value={"amount": movement.amount, "method": movement.method, "comment": movement.comment},
        )
        db.commit()
        return ClientDepositService.read(db, client_id)

    @staticmethod
    def spend(db: Session, client_id: uuid.UUID, order_id: uuid.UUID, payment_id: uuid.UUID, amount: Decimal, user_id: uuid.UUID | None) -> None:
        available = ClientDepositService.read(db, client_id).balance
        if _money(amount) > available:
            raise AppError("Недостаточно денег на депозите клиента", 422)
        db.add(ClientDepositMovement(
            client_id=client_id, amount=_money(amount), kind="spend", method="deposit",
            order_id=order_id, payment_id=payment_id, created_by=user_id,
        ))

    @staticmethod
    def return_payment(db: Session, payment_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
        original = db.scalar(select(ClientDepositMovement).where(
            ClientDepositMovement.payment_id == payment_id,
            ClientDepositMovement.kind == "spend",
        ))
        if original is None:
            return
        original.payment_id = None
        db.add(ClientDepositMovement(
            client_id=original.client_id, amount=original.amount, kind="return",
            method="deposit", order_id=original.order_id,
            comment="Возврат после удаления оплаты заказа", created_by=user_id,
        ))
