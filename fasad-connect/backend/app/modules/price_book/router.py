from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.price_book.kinds import (
    PRICE_ITEM_KINDS,
    PRICE_ITEM_UNITS,
    production_kind_options,
)
from app.modules.price_book.schemas import (
    PriceBookOptions,
    PriceItemCreate,
    PriceItemDetailRead,
    PriceItemRead,
    PriceItemUpdate,
)
from app.modules.price_book.service import PriceBookService
from app.modules.shared.schemas import ConfirmPermanentDeletion, Envelope, MessageEnvelope
from app.modules.users.models import User

router = APIRouter()

# Справочник цен — это прайс студии, то есть деньги.
#
# Читать его должны те, кто считает заказ и ведёт номенклатуру. Работнику цеха
# прайс не нужен и по описанию его роли не положен: «Денег и клиентов не видит».
# Раньше все три чтения стояли на голом «вошёл в систему».
PRICE_BOOK_READ = ("orders.manage", "templates.manage")
PRICE_BOOK_WRITE = ("orders.manage",)

#: Верхняя граница страницы справочника.
#:
#: Общий `get_page_params` разрешает не больше 100 записей, а справочник целиком
#: нужен выпадающему списку в смете заказа: менеджер выбирает артикул из него, и
#: обрезанный список — это молча пропавшие позиции. Прайс мебельной студии
#: столько строк не набирает, поэтому берём с запасом.
PRICE_BOOK_MAX_PAGE_SIZE = 500


def get_price_book_page_params(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=PRICE_BOOK_MAX_PAGE_SIZE),
) -> PageParams:
    return PageParams(page=page, size=size)


@router.get("/price-book/options", response_model=Envelope[PriceBookOptions])
def price_book_options(
    _: Annotated[User, Depends(require_permissions(*PRICE_BOOK_READ))],
) -> dict[str, object]:
    """Типы работ и единицы для выпадающих списков."""
    return envelope(
        PriceBookOptions(
            kinds=[{"code": code, "label": label} for code, label in PRICE_ITEM_KINDS.items()],
            units=[{"code": code, "label": label} for code, label in PRICE_ITEM_UNITS.items()],
            production_kinds=production_kind_options(),
        )
    )


@router.get("/price-book", response_model=Envelope[list[PriceItemRead]])
def list_price_items(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*PRICE_BOOK_READ))],
    params: Annotated[PageParams, Depends(get_price_book_page_params)],
    search: str | None = Query(default=None, description="Артикул или название"),
    kind: str | None = Query(default=None, description="Тип работы"),
    only_active: bool = Query(default=False),
) -> dict[str, object]:
    items, meta = PriceBookService.list_items(
        db,
        params,
        search=search,
        kind=kind,
        only_active=only_active,
    )
    return envelope([PriceBookService.to_read(item) for item in items], meta)


@router.post("/price-book", response_model=Envelope[PriceItemDetailRead])
def create_price_item(
    payload: PriceItemCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*PRICE_BOOK_WRITE))],
) -> dict[str, object]:
    item = PriceBookService.create_item(db, payload, current_user.id)
    return envelope(PriceBookService.to_detail(item))


@router.get("/price-book/{item_id}", response_model=Envelope[PriceItemDetailRead])
def get_price_item(
    item_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*PRICE_BOOK_READ))],
) -> dict[str, object]:
    item = PriceBookService.get_item(db, item_id)
    return envelope(PriceBookService.to_detail(item))


@router.patch("/price-book/{item_id}", response_model=Envelope[PriceItemDetailRead])
def update_price_item(
    item_id: uuid.UUID,
    payload: PriceItemUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*PRICE_BOOK_WRITE))],
) -> dict[str, object]:
    item = PriceBookService.update_item(db, item_id, payload, current_user.id)
    return envelope(PriceBookService.to_detail(item))


@router.delete("/price-book/{item_id}", response_model=MessageEnvelope)
def delete_price_item(
    item_id: uuid.UUID,
    payload: ConfirmPermanentDeletion,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*PRICE_BOOK_WRITE))],
) -> dict[str, object]:
    PriceBookService.delete_item(db, item_id, current_user.id)
    return envelope({"message": "Запись удалена из справочника. Данные и цены старых заказов сохранены."})
