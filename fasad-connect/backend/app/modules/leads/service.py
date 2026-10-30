from __future__ import annotations

import base64
import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.exceptions import AppError, ConflictError
from app.core.pagination import PageParams, pagination_meta
from app.modules.audit.service import AuditService
from app.modules.clients.models import Client
from app.modules.clients.repository import ClientRepository
from app.modules.directions.service import DirectionService
from app.modules.leads.models import Lead, LeadAttachment
from app.modules.leads.repository import LeadRepository
from app.modules.leads.schemas import (
    LeadNormalizedPayload,
    LeadOrderRef,
    LeadSummaryRead,
    LeadUpdate,
)
from app.modules.messaging.schemas import UnifiedAttachmentIn, UnifiedLeadIn
from app.modules.price_book.kinds import direction_price_kind, kind_label, kind_lead_time_days
from app.modules.price_book.schemas import PriceItemCreate
from app.modules.price_book.service import PriceBookService
from app.modules.users.models import User
from app.modules.shared.numbering import allocate, peek, reserve
from app.storage.factory import get_storage_backend

PHONE_RE = re.compile(r"(\+?\d[\d\-\s\(\)]{8,}\d)")
EMAIL_RE = re.compile(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)
SIZE_RE = re.compile(r"(\d{2,4})\s*[xхХX]\s*(\d{2,4})(?:\s*[xхХX]\s*(\d{2,4}))?")
NAME_RE = re.compile(r"(?:name|client|имя)\s*[:\-]\s*([A-Za-zА-Яа-я\s]{3,})", re.IGNORECASE)
# Количество рядом с размером: «560х123 — 3 шт.», «610x120, 5 штук».
# Только со словом «шт»: без него в количество уехало бы любое число строки —
# цена, номер дома, год.
PART_QUANTITY_RE = re.compile(r"(\d{1,4})\s*(?:шт|штук|pcs)", re.IGNORECASE)


LEAD_NUMBER_PREFIX = "З-"
SQ_MM_IN_SQ_M = Decimal("1000000")
AREA_PRECISION = Decimal("0.001")
#: Потолок на разбор размеров из текста письма. Столько позиций в одной заявке
#: не бывает: всё, что выше, — это уже не список размеров, а чужая таблица в
#: подписи письма, и раздувать ею заявку незачем.
MAX_DERIVED_PARTS = 200


def _to_decimal(value: Any) -> Decimal | None:
    """Значения приходят из JSON строками и числами — приводим бережно."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _positive_int(value: Any) -> int:
    try:
        number = int(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return 1
    return number if number > 0 else 1


class LeadService:
    @staticmethod
    def normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _generate_lead_number(db: Session) -> str:
        """Номер заявки вида «З-0001».

        Нумерация своя, а не общая с заказами: иначе «0012» и «0012» означали бы
        разные сущности. Занятые номера пропускаются — так же, как у заказов.
        """
        sequence = allocate(db, "leads")
        candidate = f"{LEAD_NUMBER_PREFIX}{sequence:04d}"
        while db.scalar(select(Lead.id).where(Lead.lead_number == candidate)) is not None:
            sequence = allocate(db, "leads")
            candidate = f"{LEAD_NUMBER_PREFIX}{sequence:04d}"
        return candidate

    @staticmethod
    def preview_next_number(db: Session) -> str:
        """Номер, который получит заявка, если оставить поле пустым.

        Заказчик: «чтобы дважды не заносили предыдущие номера» — менеджер
        подглядывал последний номер в списке и прибавлял единицу руками, что
        и приводило к неверным/задвоенным номерам. Только предпросмотр: ничего
        не резервирует и не пишет, настоящий номер выдаётся при сохранении той
        же функцией — если за это время добавилась ещё заявка, число может
        сдвинуться на единицу.
        """
        return f"{LEAD_NUMBER_PREFIX}{peek(db, 'leads'):04d}"

    @staticmethod
    def _resolve_lead_number(db: Session, requested: str | None) -> str:
        """Номер заявки: свой, если менеджер его назвал, иначе автоматический.

        Заказчик: «нажала создать заявку, автоматом встаёт номер, редактировать
        я его не могу». Студия ведёт свои номера, и подменять их системными
        нельзя — по ним она разговаривает с клиентом.

        Занятый номер отклоняем: две заявки с одним номером означают, что по
        звонку клиента невозможно понять, о какой из них речь.
        """
        manual = (requested or "").strip()
        if not manual:
            return LeadService._generate_lead_number(db)
        taken = db.scalar(select(Lead.id).where(Lead.lead_number == manual)) is not None
        if taken:
            raise ConflictError(f"Заявка с номером «{manual}» уже есть")
        if re.fullmatch(r"З-\d+", manual):
            reserve(db, "leads", int(manual[2:]))
        return manual

    @staticmethod
    def extract_payload(payload: UnifiedLeadIn) -> LeadNormalizedPayload:
        text = payload.text or json.dumps(payload.raw_payload, ensure_ascii=False)
        phone_match = PHONE_RE.search(text)
        email_match = EMAIL_RE.search(text)
        name_match = NAME_RE.search(text)
        size_match = SIZE_RE.search(text)

        dimensions: dict[str, Any] = {}
        if size_match:
            dimensions = {
                "width": int(size_match.group(1)),
                "height": int(size_match.group(2)),
            }
            if size_match.group(3):
                dimensions["depth"] = int(size_match.group(3))

        return LeadNormalizedPayload(
            client_name=(payload.sender.full_name if payload.sender else None)
            or (name_match.group(1).strip() if name_match else None),
            client_id=payload.sender.client_id if payload.sender else None,
            phone=(payload.sender.phone if payload.sender else None)
            or (phone_match.group(1).strip() if phone_match else None),
            email=(payload.sender.email if payload.sender else None)
            or (email_match.group(1).strip().lower() if email_match else None),
            address=(payload.sender.address if payload.sender else None),
            organization=(payload.sender.organization if payload.sender else None),
            text=text,
            dimensions=dimensions,
        )

    @staticmethod
    def extract_parts(text: str, declared_quantity: Any = None) -> list[dict[str, Any]]:
        """Позиции заявки, разобранные из текста письма или сообщения.

        Клиент присылает размеры списком («560х123 — 3 шт., 610х120 — 5 шт.»), а
        в заявку с канала попадал только первый размер: в карточке оставался
        один сплошной текст, площадь считалась по одной строке, а раскрой по
        такой заявке открывался пустым — менеджер перебивал размеры руками.

        Формат позиций один на всю систему (``raw_payload.parts``), поэтому
        разобранные строки дальше читают и бланк, и печать, и раскрой.
        """
        source = text or ""
        parts: list[dict[str, Any]] = []
        matches = list(SIZE_RE.finditer(source))
        for index, match in enumerate(matches):
            next_start = matches[index + 1].start() if index + 1 < len(matches) else len(source)
            # Количество ищем только после этого размера и только до конца его
            # строки: «5 шт» из следующей позиции к этой не относится.
            tail = source[match.end() : next_start].split("\n", 1)[0]
            found = PART_QUANTITY_RE.search(tail)
            parts.append(
                {
                    "width": int(match.group(1)),
                    "height": int(match.group(2)),
                    "quantity": _positive_int(found.group(1)) if found else 1,
                }
            )
            if len(parts) >= MAX_DERIVED_PARTS:
                break

        # Один размер и отдельно названное количество — это одна позиция в
        # нужном числе штук. Так заявку присылает бот и справочник: «Size:
        # 1200x600x520», «Quantity: 3» — раньше это и считалось умножением
        # размера на количество, и разбор не должен эту цифру потерять.
        if len(parts) == 1 and parts[0]["quantity"] == 1 and declared_quantity is not None:
            parts[0]["quantity"] = _positive_int(declared_quantity)
        return parts

    @staticmethod
    def build_summary(lead: Lead) -> LeadSummaryRead:
        """Сводка заявки: количество, площади, оценка и деньги по заказам.

        Порядок источников важен. Сначала готовый расчёт, если он был (заявка из
        справочника или из бота) — там площадь посчитана по правилам изделия.
        Затем список позиций: у заявки почти всегда несколько разных размеров, и
        умножать первый размер на общее количество нельзя — площадь выйдет
        неверной. И только если ничего этого нет — один разобранный размер.
        """
        payload = lead.parsed_payload_json or {}
        raw = payload.get("raw_payload") or {}
        estimate = raw.get("estimate") or {}

        parts = [item for item in (raw.get("parts") or []) if isinstance(item, dict)]

        # Деталь — только строка с размерами.
        #
        # В списке позиций живут и строки расчёта без размеров: «доставка»,
        # «гнутьё», просто запомненный артикул. Раньше такие строки до сервера
        # не доезжали вовсе, и набранный номер пропадал; теперь доезжают, но
        # деталями не считаются — иначе карточка писала бы «Деталей: 5» там,
        # где физических фасадов четыре, и цех недосчитался бы одного.
        sized = [
            part
            for part in parts
            if (_to_decimal(part.get("width")) or Decimal("0")) > 0
            and (_to_decimal(part.get("height")) or Decimal("0")) > 0
        ]

        quantity = _positive_int(raw.get("quantity") or estimate.get("quantity") or 1)
        if sized:
            quantity = sum(_positive_int(part.get("quantity") or 1) for part in sized)
        elif parts:
            # Позиции есть, но ни одной с размерами — считать нечего.
            quantity = 0

        facade_area = _to_decimal(estimate.get("area_sqm"))
        material_area = _to_decimal(estimate.get("material_area_sqm"))

        if facade_area is None and parts:
            facade_area = Decimal("0")
            for part in sized:
                width = _to_decimal(part.get("width")) or Decimal("0")
                height = _to_decimal(part.get("height")) or Decimal("0")
                count = _positive_int(part.get("quantity") or 1)
                facade_area += (width * height * count) / SQ_MM_IN_SQ_M

        if facade_area is None:
            dimensions = payload.get("dimensions") or raw.get("dimensions") or {}
            width = _to_decimal(dimensions.get("width")) or Decimal("0")
            height = _to_decimal(dimensions.get("height")) or Decimal("0")
            facade_area = (width * height * quantity) / SQ_MM_IN_SQ_M

        if material_area is None:
            factor = Decimal("1")
            if lead.direction is not None and lead.direction.material_area_factor:
                factor = Decimal(str(lead.direction.material_area_factor))
            material_area = facade_area * factor

        orders = [order for order in lead.orders if order.deleted_at is None]
        orders_amount = sum(
            (Decimal(str(order.final_amount or 0)) for order in orders), Decimal("0")
        )
        currency = next((order.currency for order in orders if order.currency), None)

        return LeadSummaryRead(
            quantity=quantity,
            facade_area_sqm=facade_area.quantize(AREA_PRECISION),
            material_area_sqm=material_area.quantize(AREA_PRECISION),
            estimated_amount=_to_decimal(estimate.get("final_amount")),
            orders_count=len(orders),
            orders_amount=orders_amount,
            currency=currency or estimate.get("currency") or "RUB",
            orders=[
                LeadOrderRef(
                    id=order.id,
                    order_number=order.order_number,
                    final_amount=Decimal(str(order.final_amount or 0)),
                    currency=order.currency or "RUB",
                    comment=order.comment,
                )
                for order in orders
            ],
        )

    @staticmethod
    def _placeholder_client_name(source_channel: str) -> str:
        """Имя для клиента, который не назвал себя: канал по-русски."""
        titles = {
            "website_form": "Клиент с сайта",
            "manual_manager_input": "Клиент без имени",
            "manager_film_cutting": "Клиент из раскроя",
            "telegram": "Клиент из Telegram",
            "telegram_bot": "Клиент из Telegram",
            "whatsapp": "Клиент из WhatsApp",
            "email": "Клиент с почты",
            "email_inbox": "Клиент с почты",
            "webhook": "Клиент из внешнего источника",
            "catalog_demo": "Клиент из расчёта",
        }
        return titles.get(source_channel, "Клиент без имени")

    @staticmethod
    def _resolve_client(
        db: Session, normalized: LeadNormalizedPayload, source_channel: str
    ) -> Client:
        # Менеджер сам ткнул в клиента из базы — это точнее любого поиска по
        # контактам. Если id мусорный (карточку успели удалить), не падаем,
        # а идём обычным путём.
        if normalized.client_id:
            picked = ClientRepository.get_by_id(db, normalized.client_id)
            if picked:
                LeadService._fill_missing_address(picked, normalized.address)
                LeadService._fill_missing_organization(picked, normalized.organization)
                return picked
        client = ClientRepository.find_by_contact(db, normalized.email, normalized.phone)
        if client:
            LeadService._fill_missing_address(client, normalized.address)
            LeadService._fill_missing_organization(client, normalized.organization)
            return client
        # Имя уходит прямо в интерфейс и в разговор с клиентом, поэтому
        # заглушка тоже на русском: «Client from manual_manager_input» менеджер
        # не может ни прочитать, ни назвать по телефону.
        client = Client(
            full_name=normalized.client_name
            or LeadService._placeholder_client_name(source_channel),
            phone=normalized.phone,
            email=normalized.email,
            address=(normalized.address or None),
            organization=(normalized.organization or None),
            comment="Клиент создан автоматически при приёме заявки",
        )
        db.add(client)
        db.flush()
        AuditService.log_event(
            db,
            entity_type="client",
            entity_id=str(client.id),
            action="create_client",
            new_value={"full_name": client.full_name, "email": client.email, "phone": client.phone},
        )
        return client

    @staticmethod
    def _resolve_due_date(payload: UnifiedLeadIn) -> date | None:
        """Срок сдачи заявки: названный менеджером или типовой по типу работ.

        Заказчик: «мыло типовое 14 дней, так же с возможностью редактирования
        при создании заявки». Поэтому названная дата главнее: типовой срок —
        только подстановка, а обещание клиенту даёт менеджер.

        Без типа работ срок не выдумываем: у письма с почты его нет, и поставить
        дату «через две недели» от имени студии нельзя — по ней потом отвечать.
        """
        if payload.due_date:
            return payload.due_date
        kind = (payload.work_kind or "").strip()
        if not kind:
            return None
        return date.today() + timedelta(days=kind_lead_time_days(kind))

    @staticmethod
    def _fill_missing_address(client: Client, address: str | None) -> None:
        """Дописывает адрес в карточку, если его там не было.

        Заполненный адрес не перетираем: заявка — не место, где меняют карточку
        клиента. Если менеджер привёз новый адрес объекта, он правит карточку
        сам, осознанно, а не побочным эффектом приёма заявки.

        Адрес из формы при этом не пропадает: он остаётся в самой заявке
        (``parsed_payload_json["address"]``) как адрес доставки этой поставки —
        см. ``_store_lead_address``. Раньше его просто не показывали, и
        выглядело это так, будто введённый адрес система молча выбросила.
        """
        value = (address or "").strip()
        if value and not (client.address or "").strip():
            client.address = value

    @staticmethod
    def _fill_missing_organization(client: Client, organization: str | None) -> None:
        """Дописывает организацию в карточку, если там пусто — как с адресом.

        Раньше поле «Организация» на «Рабочем месте» вообще не долетало до
        карточки клиента: заполненную организацию из формы молча теряло, даже
        если менеджер выбрал существующего клиента без организации в базе.
        Заполненную карточку по той же причине не трогаем — organization в ней
        мог поправить кто-то другой осознанно.
        """
        value = (organization or "").strip()
        if value and not (client.organization or "").strip():
            client.organization = value

    @staticmethod
    def _store_lead_address(lead: Lead, address: str | None) -> None:
        """Пишет адрес доставки в саму заявку.

        Почему при заявке, а не в карточке клиента: доставка бывает разовой —
        на объект, на склад монтажников, «в этот раз везём на дачу». У одного
        заказчика таких адресов столько же, сколько заявок, и юридический адрес
        карточки от них меняться не должен. Поэтому у каждой заявки свой адрес,
        а карточка правится только руками, из карточки.

        Отдельной колонки в БД адрес не получил: разобранные поля заявки и так
        живут одним JSON-документом (имя, телефон, почта, размеры), и адрес —
        такое же разобранное поле, а не новая сущность.
        """
        payload = dict(lead.parsed_payload_json or {})
        value = (address or "").strip()
        payload["address"] = value or None
        # JSON-колонка не отслеживает правку по месту: присваиваем новый
        # словарь, иначе SQLAlchemy не увидит изменения и адрес не сохранится.
        lead.parsed_payload_json = payload

    @staticmethod
    def _save_attachment(lead_id: uuid.UUID, attachment: UnifiedAttachmentIn) -> str:
        storage = get_storage_backend()
        relative_path = f"leads/{lead_id}/{attachment.file_name}"
        if attachment.content_base64:
            content = base64.b64decode(attachment.content_base64)
            return storage.save_bytes(relative_path, content)
        placeholder = attachment.external_url or "Attachment placeholder"
        return storage.save_text(relative_path, placeholder)

    @staticmethod
    def _remember_manual_prices(db: Session, payload: UnifiedLeadIn, raw_payload: dict[str, Any]) -> None:
        """Add new article/price pairs as soon as a manager saves a manual lead.

        Repeat entries keep the existing catalog price: a one-off price quoted
        to a customer belongs to the lead and must not reprice future orders.
        Automatically imported messages do not create catalog entries.
        """
        if payload.source_channel != "manual_manager_input":
            return
        parts = raw_payload.get("parts")
        if not isinstance(parts, list):
            return

        for part in parts:
            if not isinstance(part, dict):
                continue
            article = PriceBookService._normalize_article(str(part.get("article") or ""))
            price = _to_decimal(part.get("unit_price"))
            if not article or len(article) > 50 or price is None or not price.is_finite() or price <= 0:
                continue
            kind = str(part.get("kind") or direction_price_kind(payload.direction_code or "") or payload.work_kind or "other")
            unit = str(part.get("unit") or "sqm")
            if len(kind) > 50 or len(unit) > 20 or PriceBookService.get_by_article(db, article, kind):
                continue
            PriceBookService.create_item(
                db,
                PriceItemCreate(
                    article=article,
                    name=f"{kind_label(kind)}, арт. {article}",
                    kind=kind,
                    unit=unit,
                    price=price,
                    comment="Заведено из заявки",
                ),
                commit=False,
            )

    @staticmethod
    def intake_lead(db: Session, payload: UnifiedLeadIn, acting_user_id: str | None = None) -> Lead:
        if payload.external_message_id:
            existing = LeadRepository.get_by_external_message(
                db,
                payload.source_channel,
                payload.external_message_id,
            )
            if existing:
                return existing

        normalized = LeadService.extract_payload(payload)
        client = LeadService._resolve_client(db, normalized, payload.source_channel)
        assigned_manager_id = None
        if payload.assigned_manager_id:
            try:
                assigned_manager_id = uuid.UUID(payload.assigned_manager_id)
            except ValueError:
                assigned_manager_id = None

        direction = DirectionService.resolve(db, direction_code=payload.direction_code)

        raw_text = payload.text or json.dumps(payload.raw_payload, ensure_ascii=False)
        # Заявка с канала приходит сплошным текстом: позиций в ней нет, их надо
        # разобрать. Форма приёма и бот присылают позиции сами — их разбор не
        # трогает, менеджер набрал строки точнее любого разбора.
        raw_payload = dict(payload.raw_payload or {})
        stored_parts = raw_payload.get("parts")
        if not isinstance(stored_parts, list) or not stored_parts:
            derived = LeadService.extract_parts(raw_text, raw_payload.get("quantity"))
            if derived:
                raw_payload["parts"] = derived

        lead = Lead(
            lead_number=LeadService._resolve_lead_number(db, payload.lead_number),
            source_channel=payload.source_channel,
            external_message_id=payload.external_message_id,
            direction_id=direction.id if direction else None,
            subject=payload.subject,
            raw_text=raw_text,
            normalized_text=LeadService.normalize_text(raw_text),
            parsed_payload_json=normalized.model_dump(mode="json")
            | {"raw_payload": raw_payload, "attachments_count": len(payload.attachments)},
            status="new",
            client_id=client.id,
            assigned_manager_id=assigned_manager_id,
            due_date=LeadService._resolve_due_date(payload),
        )
        db.add(lead)
        db.flush()

        for attachment in payload.attachments:
            stored_path = LeadService._save_attachment(lead.id, attachment)
            db.add(
                LeadAttachment(
                    lead_id=lead.id,
                    file_name=attachment.file_name,
                    file_path=stored_path,
                    mime_type=attachment.mime_type,
                    size_bytes=attachment.size_bytes,
                )
            )

        AuditService.log_event(
            db,
            entity_type="lead",
            entity_id=str(lead.id),
            action="create_lead",
            user_id=acting_user_id,
            new_value={
                "source_channel": lead.source_channel,
                "status": lead.status,
                "client_id": str(lead.client_id) if lead.client_id else None,
            },
        )
        LeadService._remember_manual_prices(db, payload, raw_payload)
        db.commit()
        return LeadService.get_lead(db, lead.id)

    @staticmethod
    def list_leads(
        db: Session,
        params: PageParams,
        *,
        status: str | None = None,
        source_channel: str | None = None,
        direction_code: str | None = None,
        search: str | None = None,
        deleted: bool = False,
    ) -> tuple[list[Lead], dict[str, Any]]:
        stmt = (
            select(Lead)
            .options(
                selectinload(Lead.attachments),
                joinedload(Lead.client),
                joinedload(Lead.direction),
                joinedload(Lead.assigned_manager).joinedload(User.role),
            )
            .order_by(Lead.created_at.desc())
        )
        count_stmt = select(func.count()).select_from(Lead)
        criteria = Lead.deleted_at.is_not(None) if deleted else Lead.deleted_at.is_(None)
        stmt = stmt.where(criteria)
        count_stmt = count_stmt.where(criteria)

        if status:
            stmt = stmt.where(Lead.status == status)
            count_stmt = count_stmt.where(Lead.status == status)
        if source_channel:
            stmt = stmt.where(Lead.source_channel == source_channel)
            count_stmt = count_stmt.where(Lead.source_channel == source_channel)
        if direction_code:
            direction = DirectionService.require_by_code(db, direction_code)
            stmt = stmt.where(Lead.direction_id == direction.id)
            count_stmt = count_stmt.where(Lead.direction_id == direction.id)
        if search:
            # Заказчик: «создала заказ, зашла в другую вкладку — как мне его
            # найти? Под этим номером ничего нет». Искали только по тексту
            # заявки, поэтому ни номер, ни имя клиента её не находили.
            pattern = f"%{search.lower()}%"
            criteria = or_(
                func.lower(func.coalesce(Lead.lead_number, "")).like(pattern),
                func.lower(func.coalesce(Lead.subject, "")).like(pattern),
                func.lower(Lead.raw_text).like(pattern),
                func.lower(func.coalesce(Lead.normalized_text, "")).like(pattern),
                Lead.client.has(
                    or_(
                        func.lower(func.coalesce(Client.full_name, "")).like(pattern),
                        func.lower(func.coalesce(Client.organization, "")).like(pattern),
                        func.lower(func.coalesce(Client.phone, "")).like(pattern),
                    )
                ),
            )
            stmt = stmt.where(criteria)
            count_stmt = count_stmt.where(criteria)

        total = db.scalar(count_stmt) or 0
        leads = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return leads, pagination_meta(total, params)

    @staticmethod
    def get_lead(db: Session, lead_id: uuid.UUID, *, include_deleted: bool = False) -> Lead:
        lead = LeadRepository.get_by_id(db, lead_id)
        if not lead or (lead.deleted_at and not include_deleted):
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Заявка не найдена")
        return lead

    @staticmethod
    def get_attachment(db: Session, attachment_id: uuid.UUID) -> LeadAttachment:
        """Вложение заявки по id — для скачивания.

        Раньше карточка заявки печатала только служебный `file_path` текстом:
        открыть файл из интерфейса было нельзя в принципе, эндпоинта скачивания
        не было вовсе (см. `documents/{id}/download` — у заказов он есть,
        у заявок — нет).
        """
        from app.core.exceptions import NotFoundError

        attachment = db.get(LeadAttachment, attachment_id)
        if not attachment:
            raise NotFoundError("Вложение не найдено")
        return attachment

    @staticmethod
    def read_attachment_content(attachment: LeadAttachment) -> bytes:
        from app.core.exceptions import NotFoundError

        storage = get_storage_backend()
        try:
            return storage.read_bytes(attachment.file_path)
        except (OSError, ValueError) as exc:
            raise NotFoundError("Файл не найден в хранилище") from exc

    @staticmethod
    def _resolve_updated_number(db: Session, lead: Lead, requested: str | None) -> str:
        """Новый номер заявки: не пустой и не занятый чужой заявкой.

        Пустой номер запрещаем: номер — это то, как заявку называют клиенту по
        телефону, и без него её потом не найти. Занятый — тоже: две заявки под
        одним номером означают, что по звонку непонятно, о какой речь.
        """
        manual = (requested or "").strip()
        if not manual:
            raise AppError("Номер заявки не может быть пустым")
        taken = db.scalar(select(Lead.id).where(Lead.lead_number == manual, Lead.id != lead.id))
        if taken is not None:
            raise ConflictError(f"Заявка с номером «{manual}» уже есть")
        return manual

    @staticmethod
    def update_lead(
        db: Session,
        lead_id: uuid.UUID,
        payload: LeadUpdate,
        acting_user_id: uuid.UUID | None = None,
    ) -> Lead:
        """Правка заявки менеджером. Направление приходит id или кодом.

        Меняем только то, что прислали: заявку правят по одному полю (поставили
        отказ, сдвинули срок), и незаполненное поле формы не должно затирать
        соседнее.
        """
        lead = LeadService.get_lead(db, lead_id)
        # Адрес и направление в модели лежат не так, как в форме, — их
        # раскладываем отдельно, остальное переносится один в один.
        data = payload.model_dump(exclude_unset=True, exclude={"direction_code", "address", "part_articles"})

        # Смотрим на «поле прислали», а не на «поле не пустое»: пустое
        # направление — это осознанное «убрать направление» из формы правки, и
        # отличить его от «поле не трогали» иначе нечем.
        fields = payload.model_fields_set
        if "direction_code" in fields or "direction_id" in fields:
            direction = DirectionService.resolve(
                db,
                direction_id=payload.direction_id,
                direction_code=payload.direction_code,
            )
            data["direction_id"] = direction.id if direction else None

        if "lead_number" in data:
            data["lead_number"] = LeadService._resolve_updated_number(db, lead, data["lead_number"])

        # Значения «до» снимаем заранее: в журнале старое и новое совпадали,
        # потому что читались уже после присвоения, и по записи нельзя было
        # понять, что именно поменяли.
        old_value = {
            "direction_id": str(lead.direction_id) if lead.direction_id else None,
            "status": lead.status,
            "lead_number": lead.lead_number,
        }
        for key, value in data.items():
            setattr(lead, key, value)

        if "address" in payload.model_fields_set:
            LeadService._store_lead_address(lead, payload.address)
            # То же правило, что и на приёме: пустой адрес в карточке клиента
            # дописываем, заполненный не трогаем. Без этого интерфейс обещал
            # «в карточке адреса не было — он записан туда же», а на правке
            # заявки этого не происходило, и обещание было ложным.
            if lead.client is not None:
                LeadService._fill_missing_address(lead.client, payload.address)

        if "part_articles" in payload.model_fields_set:
            from app.modules.orders.models import Order, OrderPosition
            from app.modules.price_book.service import PriceBookService

            parsed = dict(lead.parsed_payload_json or {})
            raw = dict(parsed.get("raw_payload") or {})
            parts = raw.get("parts") or []
            articles = payload.part_articles or []
            if not isinstance(parts, list) or len(parts) != len(articles) or any(
                not isinstance(part, dict) for part in parts
            ):
                raise AppError("Количество артикулов не совпадает с позициями заявки", 422)

            old_parts = parts
            new_parts = []
            for part, article in zip(old_parts, articles, strict=True):
                updated = dict(part)
                updated["article"] = article
                new_parts.append(updated)
            raw["parts"] = new_parts
            parsed["raw_payload"] = raw
            lead.parsed_payload_json = parsed

            # Keep the linked order's cutting card in sync when its position has
            # not been edited independently since conversion from this lead.
            order = db.scalar(select(Order).where(Order.source_lead_id == lead.id))
            if order is not None:
                positions = list(db.scalars(select(OrderPosition).where(
                    OrderPosition.order_id == order.id
                ).order_by(OrderPosition.line_no)))
                priced_parts = [
                    (old, new) for old, new in zip(old_parts, new_parts, strict=True)
                    if (_to_decimal(old.get("unit_price")) or 0) > 0
                ]
                if len(positions) == len(priced_parts):
                    for position, (old, new) in zip(positions, priced_parts, strict=True):
                        old_article = PriceBookService._normalize_article(str(old.get("article") or ""))
                        current_article = PriceBookService._normalize_article(position.article or "")
                        if not current_article or current_article == old_article:
                            new_article = PriceBookService._normalize_article(str(new.get("article") or "")) or None
                            if new_article != position.article:
                                position.article = new_article
                                position.price_item_id = None
                                position.is_custom = True

        AuditService.log_event(
            db,
            entity_type="lead",
            entity_id=str(lead.id),
            action="update_lead",
            user_id=str(acting_user_id) if acting_user_id else None,
            old_value=old_value,
            new_value={
                "direction_id": str(lead.direction_id) if lead.direction_id else None,
                "status": lead.status,
                "lead_number": lead.lead_number,
            },
        )
        db.commit()
        return LeadService.get_lead(db, lead.id)
