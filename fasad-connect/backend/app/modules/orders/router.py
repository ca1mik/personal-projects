from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.http import content_disposition
from app.core.pagination import PageParams, get_page_params
from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.cutting_export.schemas import ExportRead
from app.modules.cutting_export.service import CuttingExportService
from app.modules.order_statuses.models import OrderStatus
from app.modules.order_statuses.schemas import OrderStatusRead
from app.modules.orders.payments import PAYMENT_METHODS
from app.modules.orders.positions_service import OrderPaymentService, OrderPositionService
from app.modules.orders.schemas import (
    AdditionalOrderRequest,
    ChangeOrderStatusRequest,
    OrderCalculationResult,
    OrderCreate,
    OrderCuttingLayoutSaveRequest,
    OrderItemCreate,
    OrderItemRead,
    OrderMaterialOrderedRequest,
    OrderPaymentCreate,
    OrderPaymentRead,
    OrderPositionRead,
    OrderPositionsReplace,
    OrderRead,
    OrderShippedRequest,
    OrderUpdate,
)
from app.modules.orders.service import OrderService
from app.modules.parts_generator.schemas import PartRead
from app.modules.shared.schemas import ConfirmPermanentDeletion, Envelope, MessageEnvelope
from app.modules.users.models import User

router = APIRouter()

# Кто имеет право открыть ОДИН заказ. Цеху карточка нужна: мастер смотрит, что
# именно делает и в какой срок, — но правит заказ только тот, кто за него
# отвечает перед клиентом.
ORDERS_READ = ("orders.manage", "production.read", "production.manage")
# Список заказов — только тем, кто ведёт деньги.
#
# В списке стоят суммы по каждому заказу, то есть по нему читается вся выручка
# студии разом. Цеху список не нужен: свои заказы работник открывает из этапа,
# ссылкой на конкретную карточку. Описание роли обещает, что денег он не видит.
ORDERS_LIST = ("orders.manage",)
# Деньги, состав сметы, статусы и отгрузка. Заказчик отдельно просил, чтобы
# оплату не мог удалить человек «мимо проходил».
ORDERS_WRITE = ("orders.manage",)
# Подготовка производства: детали, раскрой, запуск в цех. Это работа технолога,
# менеджер тоже запускает заказ, поэтому обе роли.
ORDERS_PRODUCTION = ("orders.manage", "production.manage")
# Резерв и списание материала — совместная зона заказа и склада.
ORDERS_STOCK = ("orders.manage", "stock.manage")


@router.get("/statuses", response_model=Envelope[list[OrderStatusRead]])
def list_order_statuses(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*ORDERS_READ))],
) -> dict[str, object]:
    """Справочник статусов заказа — для фильтров и выпадающих списков."""
    statuses = db.scalars(select(OrderStatus).order_by(OrderStatus.sort_order.asc())).all()
    return envelope([OrderStatusRead.model_validate(item) for item in statuses])


# Объявлен до «/{order_id}»: иначе FastAPI примет «payment-methods» за
# идентификатор заказа и ответит 422 вместо справочника.
@router.get("/payment-methods", response_model=Envelope[list[dict[str, str]]])
def list_payment_methods(
    _: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    """Способы оплаты для чекбоксов в карточке заказа."""
    return envelope([{"code": code, "label": label} for code, label in PAYMENT_METHODS.items()])


@router.get("", response_model=Envelope[list[OrderRead]])
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*ORDERS_LIST))],
    params: Annotated[PageParams, Depends(get_page_params)],
    status_code: str | None = Query(default=None),
    exclude_status_code: str | None = Query(
        default=None, description="Все, кроме этого статуса — «обычные» без отменённых"
    ),
    client_id: uuid.UUID | None = Query(default=None),
    direction_code: str | None = Query(
        default=None, description="Код направления или «none» — без направления"
    ),
    number_shape: str | None = Query(
        default=None, description="plain — просто номер, letter — номер и буква, double — две буквы"
    ),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None, description="Номер, комментарий, клиент, организация"),
    material_ordered: bool | None = Query(
        default=None, description="true — материал заказан, false — ещё нет"
    ),
    lifecycle: str | None = Query(default=None, pattern="^(estimate|waiting|in_work|completed|cancelled)$"),
    deleted: bool = Query(default=False, description="true — корзина"),
    sort_by: str | None = Query(
        default=None, description="Пока только «due_date» — клик по «Сроку»"
    ),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> dict[str, object]:
    orders, meta = OrderService.list_orders(
        db,
        params,
        status_code=status_code,
        exclude_status_code=exclude_status_code,
        client_id=client_id,
        direction_code=direction_code,
        number_shape=number_shape,
        date_from=date_from,
        date_to=date_to,
        search=search,
        material_ordered=material_ordered,
        lifecycle=lifecycle,
        deleted=deleted,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return envelope([OrderService.to_read(item) for item in orders], meta)


@router.post("", response_model=Envelope[OrderRead])
def create_order(
    payload: OrderCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    order = OrderService.create_order(db, payload, current_user.id)
    return envelope(OrderService.to_read(order))


@router.delete("/trash", response_model=Envelope[dict[str, str | int]])
def empty_order_trash(
    payload: ConfirmPermanentDeletion,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    from app.modules.orders.trash_service import purge_orders
    count = purge_orders(db, None, user.id)
    return envelope({"message": f"Корзина очищена. Удалено заказов: {count}.", "deleted_count": count})


@router.delete("/{order_id}/permanent", response_model=Envelope[dict[str, str | int]])
def permanently_delete_order(
    order_id: uuid.UUID,
    payload: ConfirmPermanentDeletion,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    from app.modules.orders.trash_service import purge_orders
    count = purge_orders(db, order_id, user.id)
    return envelope({"message": "Заказ удалён навсегда", "deleted_count": count})


@router.get("/{order_id}", response_model=Envelope[OrderRead])
def get_order(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*ORDERS_READ))],
) -> dict[str, object]:
    order = OrderService.get_order(db, order_id, include_deleted=True)
    return envelope(OrderService.to_read(order))


@router.delete("/{order_id}", response_model=MessageEnvelope)
def delete_order(order_id: uuid.UUID, db: Annotated[Session, Depends(get_db)],
                 user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))]):
    from app.modules.shared.trash import set_deleted
    set_deleted(db, "order", order_id, True, user.id)
    return envelope({"message": "Заказ перемещён в корзину"})


@router.post("/{order_id}/restore", response_model=MessageEnvelope)
def restore_order(order_id: uuid.UUID, db: Annotated[Session, Depends(get_db)],
                  user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))]):
    from app.modules.shared.trash import set_deleted
    set_deleted(db, "order", order_id, False, user.id)
    return envelope({"message": "Заказ восстановлен"})


@router.patch("/{order_id}", response_model=Envelope[OrderRead])
def update_order(
    order_id: uuid.UUID,
    payload: OrderUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    """Правка карточки заказа: текстура, запрет поворота, направление, срок."""
    order = OrderService.update_order(db, order_id, payload, current_user.id)
    return envelope(OrderService.to_read(order))


@router.post("/{order_id}/items", response_model=Envelope[OrderItemRead])
def add_order_item(
    order_id: uuid.UUID,
    payload: OrderItemCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    item = OrderService.add_item(db, order_id, payload)
    return envelope(OrderItemRead.model_validate(item))


@router.post("/{order_id}/generate-parts", response_model=Envelope[list[PartRead]])
def generate_parts(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_PRODUCTION))],
) -> dict[str, object]:
    parts = OrderService.generate_parts(db, order_id, current_user.id)
    return envelope([PartRead.model_validate(item) for item in parts])


@router.post("/{order_id}/calculate", response_model=Envelope[OrderCalculationResult])
def calculate_order(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    result = OrderService.calculate(db, order_id, current_user.id)
    return envelope(result)


@router.post("/{order_id}/change-status", response_model=Envelope[OrderRead])
def change_status(
    order_id: uuid.UUID,
    payload: ChangeOrderStatusRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_PRODUCTION))],
) -> dict[str, object]:
    order = OrderService.change_status(db, order_id, payload, current_user.id)
    return envelope(OrderService.to_read(order))


@router.post("/{order_id}/reserve-stock", response_model=MessageEnvelope)
def reserve_stock(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_STOCK))],
) -> dict[str, object]:
    OrderService.reserve_stock(db, order_id, current_user.id)
    return {"data": {"message": "Stock reserved"}}


@router.post("/{order_id}/writeoff-stock", response_model=MessageEnvelope)
def writeoff_stock(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_STOCK))],
) -> dict[str, object]:
    OrderService.writeoff_stock(db, order_id, current_user.id)
    return {"data": {"message": "Stock written off"}}


@router.put("/{order_id}/positions", response_model=Envelope[list[OrderPositionRead]])
def replace_order_positions(
    order_id: uuid.UUID,
    payload: OrderPositionsReplace,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    """Таблица позиций заказа целиком: пересчитывает сумму заказа."""
    positions = OrderPositionService.replace_positions(db, order_id, payload, current_user.id)
    return envelope([OrderPositionService.to_read(item) for item in positions])


@router.post("/{order_id}/payments", response_model=Envelope[OrderPaymentRead])
def add_order_payment(
    order_id: uuid.UUID,
    payload: OrderPaymentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    payment = OrderPaymentService.add_payment(db, order_id, payload, current_user.id)
    return envelope(OrderPaymentService.to_read(payment))


@router.delete("/{order_id}/payments/{payment_id}", response_model=MessageEnvelope)
def delete_order_payment(
    order_id: uuid.UUID,
    payment_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    OrderPaymentService.delete_payment(db, order_id, payment_id, current_user.id)
    return {"data": {"message": "Оплата удалена"}}


@router.post("/{order_id}/additional", response_model=Envelope[OrderRead])
def create_additional_order(
    order_id: uuid.UUID,
    payload: AdditionalOrderRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    """Доп. заказ к основному: клиент добавил фасады сверх заказанного."""
    order = OrderService.create_additional_order(
        db,
        order_id,
        payload.manager_id,
        current_user.id,
        order_number=payload.order_number,
        positions=payload.positions,
    )
    return envelope(OrderService.to_read(order))


@router.post("/{order_id}/material-ordered", response_model=Envelope[OrderRead])
def set_order_material_ordered(
    order_id: uuid.UUID,
    payload: OrderMaterialOrderedRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_PRODUCTION))],
) -> dict[str, object]:
    """Отметка «материал заказан»: раньше это была заливка ячейки в экселе."""
    order = OrderService.set_material_ordered(
        db, order_id, payload.material_ordered, current_user.id
    )
    return envelope(OrderService.to_read(order))


@router.post("/{order_id}/shipped", response_model=Envelope[OrderRead])
def set_order_shipped(
    order_id: uuid.UUID,
    payload: OrderShippedRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_WRITE))],
) -> dict[str, object]:
    order = OrderService.set_shipped(db, order_id, payload.shipped, current_user.id)
    return envelope(OrderService.to_read(order))


@router.post("/{order_id}/save-cutting-layout", response_model=Envelope[ExportRead])
def save_cutting_layout(
    order_id: uuid.UUID,
    payload: OrderCuttingLayoutSaveRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*ORDERS_PRODUCTION))],
) -> dict[str, object]:
    export = OrderService.save_cutting_layout(db, order_id, payload, current_user)
    return envelope(ExportRead.model_validate(export))


@router.get("/{order_id}/cutting-layout/latest", response_model=Envelope[dict | None])
def latest_cutting_layout(
    order_id: uuid.UUID,
    work_kind: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*ORDERS_READ))],
) -> dict[str, object]:
    if work_kind not in {"film", "cutting"}:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Unknown cutting work kind")
    return envelope(OrderService.latest_cutting_layout(db, order_id, work_kind))


@router.get("/{order_id}/exports", response_model=Envelope[list[ExportRead]])
def list_order_exports(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*ORDERS_READ))],
) -> dict[str, object]:
    exports = CuttingExportService.list_for_order(db, order_id)
    return envelope([ExportRead.model_validate(item) for item in exports])


@router.get("/{order_id}/exports/{export_id}/download")
def download_order_export(
    order_id: uuid.UUID,
    export_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*ORDERS_READ))],
) -> Response:
    """Раньше карточка «Экспорты» только печатала имя и путь файла на диске
    сервера — ссылки скачать не было вообще, ни для CSV раскроя, ни для
    сохранённой раскладки."""
    content, media_type, file_name = CuttingExportService.get_download(db, order_id, export_id)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": content_disposition(file_name)},
    )
