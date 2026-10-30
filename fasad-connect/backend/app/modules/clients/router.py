from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.http import content_disposition
from app.core.pagination import PageParams, get_page_params
from app.core.responses import envelope
from app.core.xlsx import XLSX_MEDIA_TYPE
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.clients.schemas import (
    ClientCreate,
    ClientDepositCorrection,
    ClientDepositCreate,
    ClientDepositRead,
    ClientDepositWithdrawalCreate,
    ClientDetailRead,
    ClientRead,
    ClientUpdate,
)
from app.modules.clients.service import ClientService
from app.modules.clients.deposit import ClientDepositService
from app.modules.clients.statement import ClientStatementService
from app.modules.clients.statement_export import build_statement_xlsx, statement_file_name
from app.modules.leads.statuses import CLOSED_LEAD_STATUSES
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter()

# Читать карточку клиента нужно не только тем, кто её ведёт: при оформлении
# заказа клиента выбирают из списка, поэтому orders.manage тоже пускаем.
CLIENTS_READ = ("clients.manage", "orders.manage")
# Заводить и править клиента, а также выгружать его взаиморасчёты — работа
# менеджера. Цех и технолог в контакты и долги клиента не лезут.
CLIENTS_WRITE = ("clients.manage",)
# Order managers can record customer money from the order card. Corrections and
# withdrawals remain limited to client managers.
CLIENTS_DEPOSIT_TOPUP = ("clients.manage", "orders.manage")


@router.get("", response_model=Envelope[list[ClientRead]])
def list_clients(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CLIENTS_READ))],
    params: Annotated[PageParams, Depends(get_page_params)],
    search: str | None = Query(default=None),
) -> dict[str, object]:
    clients, meta = ClientService.list_clients_with_summary(db, params, search)
    return envelope(clients, meta)


@router.post("", response_model=Envelope[ClientRead])
def create_client(
    payload: ClientCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CLIENTS_WRITE))],
) -> dict[str, object]:
    client = ClientService.create_client(db, payload)
    return envelope(ClientRead.model_validate(client))


@router.get("/{client_id}", response_model=Envelope[ClientDetailRead])
def get_client(
    client_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CLIENTS_READ))],
) -> dict[str, object]:
    client = ClientService.get_client(db, client_id)
    history = ClientService.get_order_history(db, client_id)
    detail = ClientDetailRead.model_validate(client)
    detail.order_history = history
    detail.totals = ClientService.get_purchase_totals(history)
    detail.statement = ClientStatementService.build(db, client)
    detail.deposit = ClientDepositService.read(db, client_id)
    # Расчёты клиента — рядом с заказами: посчитанное и не купленное иначе
    # исчезало из карточки, и менеджер не помнил, кому какую цену называл.
    detail.calculations = ClientService.get_calculations(db, client_id)
    # «Ждут ответа» — только живые расчёты. Отказ и спам ждать нечего: без
    # этой проверки счётчик считал их вечно, и закрыть расчёт было нечем —
    # заказ по нему не появится никогда, а статус игнорировался.
    pending = [
        item
        for item in detail.calculations
        if item.order_id is None and item.status not in CLOSED_LEAD_STATUSES
    ]
    detail.pending_calculations_count = len(pending)
    detail.pending_calculations_amount = sum(
        (item.estimated_amount or Decimal("0") for item in pending), Decimal("0")
    )
    return envelope(detail)


@router.post("/{client_id}/deposit", response_model=Envelope[ClientDepositRead])
def add_client_deposit(
    client_id: uuid.UUID,
    payload: ClientDepositCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*CLIENTS_DEPOSIT_TOPUP))],
) -> dict[str, object]:
    ClientService.get_client(db, client_id)
    return envelope(ClientDepositService.topup(db, client_id, payload, current_user.id))


@router.patch("/{client_id}/deposit/{movement_id}", response_model=Envelope[ClientDepositRead])
def correct_client_deposit_topup(
    client_id: uuid.UUID,
    movement_id: uuid.UUID,
    payload: ClientDepositCorrection,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*CLIENTS_WRITE))],
) -> dict[str, object]:
    ClientService.get_client(db, client_id)
    return envelope(
        ClientDepositService.correct_topup(db, client_id, movement_id, payload, current_user.id)
    )


@router.post("/{client_id}/deposit/withdraw", response_model=Envelope[ClientDepositRead])
def withdraw_client_deposit(
    client_id: uuid.UUID,
    payload: ClientDepositWithdrawalCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*CLIENTS_WRITE))],
) -> dict[str, object]:
    ClientService.get_client(db, client_id)
    return envelope(ClientDepositService.withdraw(db, client_id, payload, current_user.id))


@router.patch("/{client_id}", response_model=Envelope[ClientRead])
def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CLIENTS_WRITE))],
) -> dict[str, object]:
    client = ClientService.update_client(db, client_id, payload)
    return envelope(ClientRead.model_validate(client))


@router.get("/{client_id}/statement.xlsx")
def download_client_statement(
    client_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CLIENTS_WRITE))],
) -> Response:
    """Выписка по клиенту файлом: баланс, заказы и лента поступлений.

    Excel, а не PDF: этот файл идёт бухгалтерии, его дополняют и сверяют
    формулами — заказчик и сейчас ведёт взаиморасчёты в таблице.
    """
    client = ClientService.get_client(db, client_id)
    statement = ClientStatementService.build(db, client)
    return Response(
        content=build_statement_xlsx(client, statement),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": content_disposition(statement_file_name(client))},
    )
