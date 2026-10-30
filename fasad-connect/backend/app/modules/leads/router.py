from __future__ import annotations

import uuid
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.http import content_disposition
from app.core.exceptions import NotFoundError
from app.core.pagination import PageParams, get_page_params
from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.leads.blank_export import build_blank_xlsx
from app.modules.leads.models import Lead
from app.modules.leads.schemas import LeadCreateOrderRequest, LeadRead, LeadUpdate
from app.modules.leads.service import LeadService
from app.modules.messaging.schemas import UnifiedLeadIn
from app.modules.messaging.intake_auth import require_intake_access
from app.modules.messaging.service import MessagingService
from app.modules.orders.repository import OrderRepository
from app.modules.orders.schemas import OrderRead
from app.modules.orders.service import OrderService
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter()

# Заявка — это контакты клиента и посчитанная ему цена. Смотреть её должен и
# тот, кто ведёт заказы: заказ заводится из заявки, и по дороге в неё
# заглядывают. Цеху здесь делать нечего.
LEADS_READ = ("leads.manage", "orders.manage")
# Заводить и править заявку — работа приёма. Создание заказа из заявки —
# пограничное действие, поэтому пускаем и того, кто ведёт заказы.
LEADS_WRITE = ("leads.manage",)
LEADS_TO_ORDER = ("leads.manage", "orders.manage")


def _lead_with_summary(lead: Lead) -> LeadRead:
    """Одна точка сборки ответа по одной заявке.

    Сводка нужна сразу после создания — менеджер должен увидеть номер, площадь и
    сумму, не переходя никуда. В списке заявок сводка не считается: там она не
    нужна, а загрузка заказов на каждую строку дала бы запрос на запрос.
    """
    data = LeadRead.model_validate(lead)
    data.summary = LeadService.build_summary(lead)
    return data


@router.post("/intake", response_model=Envelope[LeadRead], dependencies=[Depends(require_intake_access)])
def intake_lead(
    payload: UnifiedLeadIn, db: Annotated[Session, Depends(get_db)]
) -> dict[str, object]:
    lead = MessagingService.intake_unified(db, payload)
    return envelope(_lead_with_summary(lead))


@router.get("", response_model=Envelope[list[LeadRead]])
def list_leads(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*LEADS_READ))],
    params: Annotated[PageParams, Depends(get_page_params)],
    status: str | None = Query(default=None),
    source_channel: str | None = Query(default=None),
    direction_code: str | None = Query(default=None),
    search: str | None = Query(default=None),
    deleted: bool = Query(default=False, description="true — корзина"),
) -> dict[str, object]:
    leads, meta = LeadService.list_leads(
        db,
        params,
        status=status,
        source_channel=source_channel,
        direction_code=direction_code,
        search=search,
        deleted=deleted,
    )
    return envelope([LeadRead.model_validate(item) for item in leads], meta)


@router.get("/next-number")
def preview_next_lead_number(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*LEADS_READ))],
) -> dict[str, object]:
    """Номер, который встанет, если оставить поле пустым при создании.

    Только подсказка на экране — ничего не резервирует. Объявлен раньше
    `/{lead_id}`: иначе FastAPI принял бы «next-number» за lead_id и уронил
    запрос валидацией UUID (как /statuses и /payment-methods у заказов).
    """
    return envelope({"next_number": LeadService.preview_next_number(db)})


@router.get("/{lead_id}", response_model=Envelope[LeadRead])
def get_lead(
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*LEADS_READ))],
) -> dict[str, object]:
    lead = LeadService.get_lead(db, lead_id, include_deleted=True)
    return envelope(_lead_with_summary(lead))


@router.delete("/{lead_id}")
def delete_lead(lead_id: uuid.UUID, db: Annotated[Session, Depends(get_db)],
                user: Annotated[User, Depends(require_permissions(*LEADS_WRITE))]):
    from app.modules.shared.trash import set_deleted
    set_deleted(db, "lead", lead_id, True, user.id)
    return envelope({"message": "Заявка перемещена в корзину. Связанные заказы сохранены."})


@router.post("/{lead_id}/restore")
def restore_lead(lead_id: uuid.UUID, db: Annotated[Session, Depends(get_db)],
                 user: Annotated[User, Depends(require_permissions(*LEADS_WRITE))]):
    from app.modules.shared.trash import set_deleted
    set_deleted(db, "lead", lead_id, False, user.id)
    return envelope({"message": "Заявка восстановлена"})


XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _blank_file_name(lead: Lead, order_number: str | None = None) -> str:
    number = str(order_number or lead.lead_number or lead.id)
    number = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', number).strip(' .') or 'заказ'
    return f"{number}.xlsx"


@router.get("/{lead_id}/blank.xlsx")
def download_lead_blank(
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*LEADS_READ))],
    order_id: Annotated[uuid.UUID | None, Query(alias="orderId")] = None,
) -> Response:
    """Бланк заказа файлом.

    Excel, а не PDF: заказчик и сейчас ведёт заказы в таблицах, файл можно
    переслать, доправить и распечатать откуда угодно. Смотреть тот же бланк на
    экране можно на странице `/leads/{id}/blank`.
    """
    lead = LeadService.get_lead(db, lead_id)
    # Заявка после приёма не меняется, а комментарий заказа менеджер может
    # поправить и позже — если заказ уже создан, бланк должен показывать
    # актуальный комментарий заказа, а не замороженный текст заявки.
    order = OrderService.get_order(db, order_id) if order_id else OrderRepository.get_by_source_lead(db, lead_id)
    if order and (order.source_lead_id != lead_id or order.deleted_at):
        raise NotFoundError("Заказ этой заявки не найден")
    comment = order.comment if order is not None else lead.raw_text
    number = order.order_number if order else None
    from app.modules.orders.specification import current_parts
    content = build_blank_xlsx(lead, comment, order_number=number,
                              parts_override=current_parts(order) if order else None,
                              final_amount=order.final_amount if order else None)
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": content_disposition(_blank_file_name(lead, number)), "Cache-Control": "no-store"},
    )


DEFAULT_ATTACHMENT_MEDIA_TYPE = "application/octet-stream"


@router.get("/attachments/{attachment_id}/download")
def download_lead_attachment(
    attachment_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*LEADS_READ))],
) -> Response:
    """Скачать вложение заявки — фото замера, скан, файл от клиента.

    Путь не вложен в `/leads/{lead_id}/...`: вложение уже несёт свой id, а
    вложенный путь заставил бы фронт помнить оба id ради одной ссылки.
    """
    attachment = LeadService.get_attachment(db, attachment_id)
    content = LeadService.read_attachment_content(attachment)
    return Response(
        content=content,
        media_type=attachment.mime_type or DEFAULT_ATTACHMENT_MEDIA_TYPE,
        headers={"Content-Disposition": content_disposition(attachment.file_name)},
    )


@router.patch("/{lead_id}", response_model=Envelope[LeadRead])
def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*LEADS_WRITE))],
) -> dict[str, object]:
    """Правка заявки из её карточки: статус (в том числе отказ), номер, срок,
    направление, адрес доставки.

    Ответ — вся карточка со сводкой: экран правки перерисовывается сразу,
    менеджеру не нужно обновлять страницу, чтобы поверить, что сохранилось.
    """
    lead = LeadService.update_lead(db, lead_id, payload, current_user.id)
    return envelope(_lead_with_summary(lead))


@router.post("/{lead_id}/create-order", response_model=Envelope[OrderRead])
def create_order_from_lead(
    lead_id: uuid.UUID,
    payload: LeadCreateOrderRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*LEADS_TO_ORDER))],
) -> dict[str, object]:
    """Заказ из заявки. Повторный вызов возвращает уже созданный заказ.

    Заказ по заявке один, и второй раз он не заводится — это правильно, иначе
    в цех уехало бы две одинаковые пачки. Но раньше повторное нажатие молча
    отдавало старый заказ, и менеджер думал, что создал новый: в `meta.created`
    честно говорим, был ли заказ создан сейчас, — по нему интерфейс и пишет
    «заказ уже был создан», вместо того чтобы делать вид, что всё получилось.
    """
    lead = LeadService.get_lead(db, lead_id)
    known_orders = {str(item.id) for item in lead.orders}
    order = OrderService.create_order_from_lead(
        db,
        lead_id,
        payload.manager_id,
        current_user.id,
        order_number=payload.order_number,
    )
    return envelope(
        OrderService.to_read(order),
        {"created": str(order.id) not in known_orders},
    )
