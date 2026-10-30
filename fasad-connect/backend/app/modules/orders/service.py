from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.pagination import PageParams
from app.modules.audit.service import AuditService
from app.modules.cnc.models import CncJob
from app.modules.cnc.service import CncService
from app.modules.cutting_export.models import Export
from app.modules.cutting_export.service import CuttingExportService
from app.modules.directions.models import ProductionDirection
from app.modules.directions.service import DirectionService
from app.modules.leads.models import Lead
from app.modules.order_statuses.models import OrderStatus, OrderStatusHistory
from app.modules.order_statuses.service import OrderStatusService
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.positions_service import (
    LeadEstimateTransfer,
    OrderPaymentService,
    OrderPositionService,
)
from app.modules.orders.repository import OrderRepository
from app.modules.orders.schemas import (
    ChangeOrderStatusRequest,
    OrderCreate,
    OrderCuttingLayoutSaveRequest,
    OrderItemCreate,
    OrderPositionsReplace,
    OrderPositionWrite,
    OrderRead,
    OrderUpdate,
)
from app.modules.parts_generator.models import Part
from app.modules.parts_generator.service import PartsGeneratorService
from app.modules.pricing.service import PricingService
from app.modules.stock.service import StockService
from app.modules.users.models import User
from app.modules.shared.numbering import allocate, numeric_order_base, reserve
from app.storage.factory import get_storage_backend


def _jsonable(values: dict) -> dict:
    """Значения, пригодные для JSON-колонки журнала.

    `date`, `datetime`, `UUID` и `Decimal` в неё не сериализуются: попытка
    записать срок сдачи роняла не только запись в журнал, но и саму правку
    заказа — пользователь получал 500 на сохранении срока.
    """
    prepared = {}
    for key, value in values.items():
        if isinstance(value, (date, datetime, uuid.UUID, Decimal)):
            prepared[key] = str(value)
        else:
            prepared[key] = value
    return prepared


class OrderService:
    @staticmethod
    def _generate_order_number(
        db: Session,
        direction: ProductionDirection | None = None,
        kind: str | None = None,
    ) -> str:
        """Номер заказа по ТЗ: эмаль — «1024», ПВХ — «1024-П», шпон — «1024-Ш».

        Сквозная нумерация по всем направлениям: буква отличает направление,
        а не начинает отдельный счётчик. Коллизии исключены, потому что
        последовательность общая.

        Саму букву выбирает `DirectionService.format_order_number` — правило
        живёт там одно. Здесь оно когда-то было продублировано, и две копии
        успели разойтись: ровно из-за такой пары «одно правило в двух местах»
        буква и терялась.
        """
        sequence = allocate(db, "orders")

        def build(number: int) -> str:
            return DirectionService.format_order_number(number, direction, kind)

        candidate = build(sequence)
        while db.scalar(select(Order.id).where(Order.order_number == candidate)) is not None:
            sequence = allocate(db, "orders")
            candidate = build(sequence)
        return candidate

    @staticmethod
    def _resolve_order_number(
        db: Session,
        requested: str | None,
        direction: ProductionDirection | None,
        kind: str | None = None,
    ) -> str:
        """Ручные цифры сохраняются, буква берётся только из направления.

        Заказчик ведёт свою нумерацию («44 03 п») и спрашивал, останется ли она.
        Поэтому поле необязательное: пустое — номер ставит система сквозной
        нумерацией. У ручного номера оставляем цифровую часть без дополнения
        нулями; прежнюю букву заменяем выбранным направлением. Проверка на
        занятый номер обязательна: два заказа с одним номером
        в цеху означают, что по бумажке невозможно понять, какой из них резать.
        """
        manual = (requested or "").strip()
        if not manual:
            return OrderService._generate_order_number(db, direction, kind)
        supplemental = bool(re.search(r"(?:\s+|(?<=\d))доп\.?$", manual, re.IGNORECASE))
        if supplemental:
            manual = re.sub(r"(?:\s+|(?<=\d))доп\.?$", "", manual, flags=re.IGNORECASE).rstrip()
        if direction or kind:
            match = re.fullmatch(
                r"(?P<base>\d+(?:[ -]\d+)*)(?:[ -]?[A-Za-zА-Яа-яЁё]{1,3})?",
                manual,
            )
            if match:
                manual = DirectionService.format_order_number_base(
                    match.group("base"), direction, kind
                )
        if supplemental:
            manual += " Доп"
        taken = db.scalar(select(Order.id).where(Order.order_number == manual)) is not None
        if taken:
            raise ConflictError(f"Заказ с номером «{manual}» уже есть")
        reserve(db, "orders", numeric_order_base(manual))
        return manual

    @staticmethod
    def _additional_order_number(db: Session, parent: Order) -> str:
        """Номер допа — от родителя: «1024-Ф/1», «1024-Ф/2».

        Так в цеху и в бумагах сразу видно, к какому заказу относится пачка.
        Отдельная сквозная нумерация тут только мешала бы: доп без основного не
        существует, а по своему номеру его пришлось бы искать отдельно.
        """
        taken = {
            number
            for (number,) in db.execute(
                select(Order.order_number).where(Order.parent_order_id == parent.id)
            ).all()
        }
        index = len(taken) + 1
        candidate = f"{parent.order_number}/{index}"
        while (
            candidate in taken
            or db.scalar(select(Order.id).where(Order.order_number == candidate)) is not None
        ):
            index += 1
            candidate = f"{parent.order_number}/{index}"
        return candidate

    @staticmethod
    def create_additional_order(
        db: Session,
        parent_order_id: uuid.UUID,
        manager_id: uuid.UUID | None = None,
        acting_user_id=None,
        order_number: str | None = None,
        positions: list[OrderPositionWrite] | None = None,
    ) -> Order:
        """Доп. заказ к уже существующему.

        Смету изначально не копируем от родителя: доп — это то, что добавили
        сверх, а не повтор основного. Клиент, менеджер и направление
        наследуются, чтобы менеджеру не заполнять их заново.

        Свою смету на доп занести можно сразу — заказчик просил тот же контур,
        что на «Рабочем месте», одним действием, а не отдельным заходом на
        пустую карточку (`positions`, необязательно).
        """
        parent = OrderService.get_order(db, parent_order_id)
        # Доп к допу — это уже дерево, в котором в цеху не разобраться. Вешаем
        # на тот же основной заказ.
        root = parent.parent_order or parent

        order = OrderService.create_order(
            db,
            OrderCreate(
                client_id=root.client_id,
                manager_id=manager_id or root.manager_id,
                direction_id=root.direction_id,
                source_lead_id=root.source_lead_id,
                comment=f"Доп. заказ к {root.order_number}",
                order_number=order_number or OrderService._additional_order_number(db, root),
            ),
            acting_user_id,
        )
        order.parent_order_id = root.id
        db.commit()
        if positions:
            try:
                OrderPositionService.replace_positions(
                    db, order.id, OrderPositionsReplace(positions=positions), acting_user_id
                )
            except Exception:
                # Смета не прошла проверку (например, нестандарт без цены) —
                # заказ уже успел закоммититься строкой выше. Сначала откатываем
                # незавершённую попытку записать смету (иначе в сессии остаются
                # висеть недособранные строки), потом удаляем сам заказ — без
                # этого доп остался бы пустой записью в базе, хотя менеджер
                # получил ошибку и уверен, что ничего не создалось.
                db.rollback()
                db.delete(OrderService.get_order(db, order.id))
                db.commit()
                raise
        return OrderService.get_order(db, order.id)

    @staticmethod
    def _fallback_manager(db: Session) -> User:
        user = db.scalar(select(User).order_by(User.created_at.asc()))
        if not user:
            raise NotFoundError("No users available for order assignment")
        return user

    @staticmethod
    def list_orders(
        db: Session,
        params: PageParams,
        *,
        status_code: str | None = None,
        exclude_status_code: str | None = None,
        client_id: uuid.UUID | None = None,
        direction_code: str | None = None,
        number_shape: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str | None = None,
        material_ordered: bool | None = None,
        lifecycle: str | None = None,
        deleted: bool = False,
        sort_by: str | None = None,
        sort_dir: str = "asc",
    ) -> tuple[list[Order], dict]:
        return OrderRepository.list_orders(
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
            # Отбор «на что материал ещё не заказан» — вопрос каждого утра перед
            # звонком поставщику. Считаем его на сервере: фильтровать уже
            # загруженную страницу бесполезно, нужный заказ может быть не в ней.
            material_ordered=material_ordered,
            lifecycle=lifecycle,
            deleted=deleted,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

    @staticmethod
    def get_order(db: Session, order_id: uuid.UUID, *, include_deleted: bool = False) -> Order:
        order = OrderRepository.get_by_id(db, order_id)
        if not order or (order.deleted_at and not include_deleted):
            raise NotFoundError("Заказ не найден")
        return order

    @staticmethod
    def to_read(order: Order) -> OrderRead:
        """Карточка заказа для фронта: смета, оплаты и деньги одной строкой.

        Русские подписи типов и способов оплаты считаются здесь, а не на
        фронте: справочник живёт в бэкенде, и дублировать его в двух местах
        значит однажды разойтись.
        """
        data = OrderRead.model_validate(order)
        from app.modules.orders.money import round_order_amount
        data.final_amount = round_order_amount(order.final_amount or 0)
        from app.modules.orders.lifecycle import LABELS, order_lifecycle
        data.lifecycle = order_lifecycle(order)
        data.lifecycle_label = LABELS[data.lifecycle]
        # Сводка хранится в comment по прежнему формату. Пожелание менеджера
        # читаем отдельно, из поля «Что нужно клиенту» исходной заявки.
        if order.source_lead is not None:
            raw = (order.source_lead.parsed_payload_json or {}).get("raw_payload") or {}
            note = raw.get("manual_note") if isinstance(raw, dict) else None
            data.customer_comment = (note.strip() or None) if isinstance(note, str) else None
        data.positions = [OrderPositionService.to_read(item) for item in order.positions]
        from app.modules.orders.specification import current_information, current_parts
        data.specification_parts = current_parts(order)
        if data.specification_parts is not None:
            data.comment = current_information(order, data.specification_parts)
        data.payments = [OrderPaymentService.to_read(item) for item in order.payments]
        data.balance = OrderPaymentService.build_balance(order)
        # Допы: их число и сумма нужны прямо в списке — «заказ 1024 (2 доп.
        # заказа)». Иначе менеджер видит основной заказ и не знает, что к нему
        # уже довезли ещё две партии.
        additional = [item for item in order.additional_orders if item.deleted_at is None]
        data.additional_orders = [link for link in data.additional_orders if any(item.id == link.id for item in additional)]
        data.additional_orders_count = len(additional)
        data.additional_orders_total = sum(
            (Decimal(item.final_amount or 0) for item in additional), Decimal("0")
        )
        # `status` заполнился сам при model_validate (обычная связь), а вот
        # статус оплаты — расчётное поле, его подставляем отдельно тем же
        # способом, что и у самого заказа.
        for link, item in zip(data.additional_orders, additional, strict=True):
            link.payment_status = OrderPaymentService.build_balance(item).status
        data.parent_order_number = order.parent_order.order_number if order.parent_order else None
        return data

    @staticmethod
    def set_shipped(
        db: Session,
        order_id: uuid.UUID,
        shipped: bool,
        acting_user_id: uuid.UUID | None = None,
    ) -> Order:
        """Галочка «отгружено» в карточке заказа.

        Дата отгрузки — то, по чему считается отчёт «Отгружено», поэтому она
        проставляется здесь, а не руками. Снятая галочка дату стирает: заказ
        вернулся, и в отгруженных ему не место.
        """
        order = OrderService.get_order(db, order_id)
        old_value = order.shipped_at.isoformat() if order.shipped_at else None
        order.shipped_at = datetime.now(UTC) if shipped else None
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="set_order_shipped",
            user_id=str(acting_user_id) if acting_user_id else None,
            old_value={"shipped_at": old_value},
            new_value={"shipped_at": order.shipped_at.isoformat() if order.shipped_at else None},
        )
        db.commit()
        return OrderService.get_order(db, order_id)

    @staticmethod
    def set_material_ordered(
        db: Session,
        order_id: uuid.UUID,
        ordered: bool,
        acting_user_id: uuid.UUID | None = None,
    ) -> Order:
        """Галочка «материал заказан».

        Заказчик помечал это заливкой ячейки в экселе: «заказана плёнка — больше
        не трогаем». Заливку нельзя отфильтровать, а вопрос «на что материал ещё
        не заказан» задают каждый день перед звонком поставщику.

        Дата ставится сама: по ней видно, сколько заказ ждёт материал. Снятая
        галочка дату стирает — это отмена ошибочной отметки.
        """
        order = OrderService.get_order(db, order_id)
        old_value = order.material_ordered_at.isoformat() if order.material_ordered_at else None
        order.material_ordered = ordered
        order.material_ordered_at = datetime.now(UTC) if ordered else None
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="set_order_material_ordered",
            user_id=str(acting_user_id) if acting_user_id else None,
            old_value={"material_ordered_at": old_value},
            new_value={
                "material_ordered_at": (
                    order.material_ordered_at.isoformat() if order.material_ordered_at else None
                )
            },
        )
        db.commit()
        return OrderService.get_order(db, order_id)

    @staticmethod
    def create_order(db: Session, payload: OrderCreate, acting_user_id=None) -> Order:
        status = (
            db.get(OrderStatus, payload.status_id)
            if payload.status_id
            else OrderStatusService.get_start_status(db)
        )
        if not status:
            raise NotFoundError("Order status not found")
        direction = DirectionService.resolve(
            db,
            direction_id=payload.direction_id,
            direction_code=payload.direction_code,
        )
        order = Order(
            order_number=OrderService._resolve_order_number(
                db, payload.order_number, direction, payload.work_kind
            ),
            direction_id=direction.id if direction else None,
            client_id=payload.client_id,
            manager_id=payload.manager_id,
            status_id=status.id,
            comment=payload.comment,
            has_texture=payload.has_texture,
            no_rotation=payload.no_rotation,
            source_lead_id=payload.source_lead_id,
            due_date=payload.due_date,
        )
        db.add(order)
        db.flush()
        db.add(
            OrderStatusHistory(
                order_id=order.id,
                old_status_id=None,
                new_status_id=status.id,
                changed_by=acting_user_id,
                comment="Initial order status",
            )
        )
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="create_order",
            user_id=acting_user_id,
            new_value={"order_number": order.order_number, "status": status.code},
        )
        db.commit()
        return OrderService.get_order(db, order.id)

    @staticmethod
    def create_order_from_lead(
        db: Session,
        lead_id: uuid.UUID,
        manager_id: uuid.UUID | None = None,
        acting_user_id=None,
        order_number: str | None = None,
    ) -> Order:
        existing = OrderRepository.get_by_source_lead(db, lead_id)
        if existing:
            if existing.deleted_at:
                raise ConflictError("Заказ по заявке находится в корзине. Сначала восстановите его.")
            return OrderService.get_order(db, existing.id)

        lead = db.scalar(select(Lead).where(Lead.id == lead_id))
        if not lead or lead.deleted_at:
            raise NotFoundError("Заявка не найдена")
        if not lead.client_id:
            raise NotFoundError("Lead has no linked client")
        # Ручной номер заявки — та же цифровая часть заказа. Автоматический
        # «З-0001» в заказ не переносим: он лишь внутренний номер обращения.
        requested_number = (order_number or "").strip()
        if not requested_number and lead.lead_number and not re.fullmatch(
            r"З-\d+", lead.lead_number, re.IGNORECASE
        ):
            requested_number = lead.lead_number
        manager = manager_id or lead.assigned_manager_id or OrderService._fallback_manager(db).id
        order = OrderService.create_order(
            db,
            OrderCreate(
                client_id=lead.client_id,
                manager_id=manager,
                source_lead_id=lead.id,
                # Направление наследуется от заявки — менеджер выбрал его при приёме,
                # и номер заказа должен получить ту же букву.
                direction_id=lead.direction_id,
                # Раньше сюда писалась техническая строка "Заказ из заявки
                # {uuid}" — сама связь с заявкой и так есть в source_lead_id
                # (queryable), а вот реальный комментарий менеджера/клиента из
                # заявки при конвертации терялся безвозвратно. Переносим его.
                comment=lead.raw_text.strip() if lead.raw_text and lead.raw_text.strip() else None,
                order_number=requested_number or None,
                # Тип работ менеджер выбрал при приёме — из него берётся буква
                # номера, когда направление у заявки не задано.
                work_kind=LeadEstimateTransfer.main_work_kind(lead),
                # Срок едет из заявки: его уже назвали клиенту при расчёте.
                due_date=lead.due_date,
            ),
            acting_user_id,
        )
        # Заявку считают клиенту прямо в таблице приёма. Эти же строки должны
        # стать сметой заказа — иначе менеджер вводит их второй раз.
        LeadEstimateTransfer.copy_to_order(db, lead, order, acting_user_id)
        lead.status = "converted"
        db.commit()
        return OrderService.get_order(db, order.id)

    @staticmethod
    def add_item(db: Session, order_id: uuid.UUID, payload: OrderItemCreate) -> OrderItem:
        order = OrderService.get_order(db, order_id)
        item = OrderItem(order_id=order.id, **payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def update_order(
        db: Session,
        order_id: uuid.UUID,
        payload: OrderUpdate,
        acting_user_id=None,
    ) -> Order:
        """Частичное редактирование карточки заказа.

        Пустое поле означает «не трогать», иначе снятая галочка текстуры была бы
        неотличима от «поле не передали» и сбрасывалась бы при любом сохранении.
        """
        order = OrderService.get_order(db, order_id)
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            return order

        # Направление приходит кодом или идентификатором — в модели поле одно.
        # Без этой развязки `setattr(order, "direction_code", ...)` уронил бы
        # запрос: такого атрибута у заказа нет.
        direction_changed = "direction_code" in changes or "direction_id" in changes
        direction = order.direction
        if direction_changed:
            direction = DirectionService.resolve(
                db,
                direction_id=changes.pop("direction_id", None),
                direction_code=changes.pop("direction_code", None),
            )
            changes["direction_id"] = direction.id if direction else None
        if "order_number" in changes or direction_changed:
            requested = changes.get("order_number", order.order_number)
            new_number = (DirectionService.change_order_number_direction(requested, direction)
                          if direction is not None or direction_changed else requested)
            if len(new_number) > 50:
                raise AppError("Номер с буквой направления длиннее 50 символов", 422)
            if new_number != order.order_number:
                duplicate = db.scalar(select(Order.id).where(Order.order_number == new_number, Order.id != order.id))
                if duplicate is not None:
                    raise ConflictError(f"Номер «{new_number}» уже занят. Изменения не сохранены.")
                base = numeric_order_base(new_number)
                if base > 9_223_372_036_854_775_806:
                    raise AppError("Цифровая часть номера слишком большая", 422)
                reserve(db, "orders", base)
                changes["order_number"] = new_number
            else:
                changes.pop("order_number", None)
        if not changes:
            return order

        needs_film_layout = (
            "direction_id" in changes
            and direction is not None
            and direction.code == "pvc"
            and (
                changes["direction_id"] != order.direction_id
                or OrderService.latest_cutting_layout(db, order.id, "film") is None
            )
        )

        old_value = {field: getattr(order, field) for field in changes}
        for field, value in changes.items():
            setattr(order, field, value)
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="update_order",
            user_id=acting_user_id,
            # Журнал — JSON-колонка: `date` и `UUID` в неё не сериализуются и
            # роняли весь запрос вместе с правкой. Приводим к строкам.
            old_value=_jsonable(old_value),
            new_value=_jsonable(changes),
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if "order_number" in changes:
                raise ConflictError("Номер заказа уже занят. Изменения не сохранены.") from exc
            raise
        if needs_film_layout:
            from app.modules.orders.auto_film_layout import save_for_order

            save_for_order(db, order.id, acting_user_id)
        return OrderService.get_order(db, order.id)

    @staticmethod
    def generate_parts(db: Session, order_id: uuid.UUID, acting_user_id=None) -> list[Part]:
        order = OrderService.get_order(db, order_id)
        return PartsGeneratorService.generate_parts(db, order, acting_user_id)

    @staticmethod
    def calculate(db: Session, order_id: uuid.UUID, acting_user_id=None):
        order = OrderService.get_order(db, order_id)
        return PricingService.calculate_order(db, order, acting_user_id)

    @staticmethod
    def change_status(
        db: Session,
        order_id: uuid.UUID,
        payload: ChangeOrderStatusRequest,
        acting_user_id=None,
    ) -> Order:
        order = OrderService.get_order(db, order_id)
        # Свой поиск статуса вместо OrderStatusService.get_by_code: менеджер жмёт
        # кнопку статуса и при отказе должен увидеть русский текст, а не
        # служебное «Order status '...' not found».
        new_status = db.scalar(select(OrderStatus).where(OrderStatus.code == payload.status_code))
        if not new_status:
            raise NotFoundError(f"Статус «{payload.status_code}» не найден")
        old_status_id = order.status_id
        order.status_id = new_status.id
        now = datetime.now(UTC)
        if payload.status_code == "approved":
            order.approved_at = now
        if (
            payload.status_code in {"manufacturing", "cutting"}
            and order.production_start_at is None
        ):
            order.production_start_at = now
        if payload.status_code == "shipped":
            order.shipped_at = now
        db.add(
            OrderStatusHistory(
                order_id=order.id,
                old_status_id=old_status_id,
                new_status_id=new_status.id,
                changed_by=acting_user_id,
                comment=payload.comment,
            )
        )
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="change_status",
            user_id=acting_user_id,
            old_value={"status_id": str(old_status_id)},
            new_value={"status_id": str(new_status.id), "status_code": new_status.code},
        )
        db.commit()
        return OrderService.get_order(db, order.id)

    @staticmethod
    def reserve_stock(db: Session, order_id: uuid.UUID, acting_user_id=None) -> None:
        order = db.scalar(
            select(Order)
            .options(selectinload(Order.parts).selectinload(Part.edges))
            .where(Order.id == order_id)
        )
        if not order:
            raise NotFoundError("Заказ не найден")
        if not order.parts:
            PartsGeneratorService.generate_parts(db, order, acting_user_id)
            order = (
                db.scalar(
                    select(Order)
                    .options(selectinload(Order.parts).selectinload(Part.edges))
                    .where(Order.id == order_id)
                )
                or order
            )
        StockService.reserve_for_order(db, order, acting_user_id)

    @staticmethod
    def writeoff_stock(db: Session, order_id: uuid.UUID, acting_user_id=None) -> None:
        order = db.scalar(
            select(Order)
            .options(selectinload(Order.parts).selectinload(Part.edges))
            .where(Order.id == order_id)
        )
        if not order:
            raise NotFoundError("Заказ не найден")
        if not order.parts:
            PartsGeneratorService.generate_parts(db, order, acting_user_id)
            order = (
                db.scalar(
                    select(Order)
                    .options(selectinload(Order.parts).selectinload(Part.edges))
                    .where(Order.id == order_id)
                )
                or order
            )
        StockService.writeoff_for_order(db, order, acting_user_id)

    @staticmethod
    def export_cutting(db: Session, order_id: uuid.UUID, current_user: User) -> Export:
        order = OrderService.get_order(db, order_id)
        # generate_parts работает только с позициями каталога (OrderItem) —
        # у заказа из заявки (то есть почти любого реального заказа) их нет,
        # а сам generate_parts требует настроенный активный кромочный
        # материал в БД ещё до того, как поймёт, что генерировать нечего, и
        # падал ValueError'ом раньше любой проверки. Смета из OrderPosition
        # (реальный путь) обрабатывается уже внутри CuttingExportService.
        if not order.parts and order.items:
            PartsGeneratorService.generate_parts(db, order, current_user.id)
            order = OrderService.get_order(db, order_id)
        return CuttingExportService.export_order(db, order, current_user.id)

    @staticmethod
    def generate_cnc(db: Session, order_id: uuid.UUID, current_user: User,
                     machine_id: uuid.UUID | None = None) -> list[CncJob]:
        order = db.scalar(
            select(Order)
            .options(selectinload(Order.parts).selectinload(Part.operations))
            .where(Order.id == order_id)
        )
        if not order:
            raise NotFoundError("Заказ не найден")
        if not order.parts and not order.positions and order.items:
            try:
                PartsGeneratorService.generate_parts(db, order, current_user.id)
            except ValueError as exc:
                raise AppError(str(exc), 422) from exc
            order = (
                db.scalar(
                    select(Order)
                    .options(selectinload(Order.parts).selectinload(Part.operations))
                    .where(Order.id == order_id)
                )
                or order
            )
        return CncService.generate_jobs(db, order, current_user.id, machine_id=machine_id)

    @staticmethod
    def list_parts(db: Session, order_id: uuid.UUID) -> list[Part]:
        return PartsGeneratorService.list_parts(db, order_id)

    @staticmethod
    def list_exports(db: Session, order_id: uuid.UUID) -> list[Export]:
        return db.scalars(
            select(Export).where(Export.order_id == order_id).order_by(Export.created_at.desc())
        ).all()

    @staticmethod
    def latest_cutting_layout(
        db: Session, order_id: uuid.UUID, work_kind: str
    ) -> dict[str, object] | None:
        """Return the newest saved layout for printing, including every sheet."""
        order = OrderService.get_order(db, order_id)
        storage = get_storage_backend()
        exports = db.scalars(
            select(Export)
            .where(Export.order_id == order_id, Export.export_type == "cutting_layout")
            .order_by(Export.created_at.desc(), Export.version.desc())
        )
        for export in exports:
            try:
                snapshot = json.loads(storage.read_bytes(export.file_path))
            except (OSError, ValueError):
                continue
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get("sheets"), list):
                continue
            settings = snapshot.get("sheet_settings") or {}
            if not isinstance(settings, dict) or settings.get("workKind") != work_kind:
                continue
            from app.modules.orders.specification import snapshot_is_current
            if not snapshot_is_current(order, snapshot, export.created_at):
                continue
            return snapshot
        return None

    @staticmethod
    def list_cnc_jobs(db: Session, order_id: uuid.UUID) -> list[CncJob]:
        return db.scalars(
            select(CncJob).where(CncJob.order_id == order_id).order_by(CncJob.created_at.desc())
        ).all()

    @staticmethod
    def save_cutting_layout(
        db: Session,
        order_id: uuid.UUID,
        payload: OrderCuttingLayoutSaveRequest,
        current_user: User,
    ) -> Export:
        order = OrderService.get_order(db, order_id)
        from app.modules.orders.cutting_layout_validation import validate_cutting_layout

        if payload.sheet_settings.get("workKind") == "film" and (not order.direction or order.direction.code != "pvc"):
            raise AppError("Раскрой плёнки доступен только для направления ПВХ", 422)
        validate_cutting_layout(payload, no_rotation=bool(order.no_rotation or order.has_texture))
        storage = get_storage_backend()
        version = (
            db.scalar(
                select(func.count())
                .select_from(Export)
                .where(
                    Export.order_id == order.id,
                    Export.export_type == "cutting_layout",
                )
            )
            or 0
        ) + 1

        svg_path: str | None = None
        if payload.sheet_svg:
            svg_file_name = f"cutting-layout-{order.order_number}-v{version}.svg"
            svg_path = storage.save_text(
                f"exports/{order.id}/{svg_file_name}",
                payload.sheet_svg,
            )

        snapshot = {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "source_lead_id": str(order.source_lead_id) if order.source_lead_id else None,
            "saved_at": datetime.now(UTC).isoformat(),
            "sheet_settings": payload.sheet_settings,
            "stats": payload.stats,
            "parts": payload.parts,
            "sheets": payload.sheets,
            "pattern_filter": payload.pattern_filter,
            "active_sheet_index": payload.active_sheet_index,
            "note": payload.note,
            "preview_svg_path": svg_path,
        }
        from app.modules.orders.specification import geometry_signature
        snapshot["specification_signature"] = geometry_signature(order)
        file_name = f"cutting-layout-{order.order_number}-v{version}.json"
        file_path = storage.save_text(
            f"exports/{order.id}/{file_name}",
            json.dumps(snapshot, ensure_ascii=False, indent=2),
        )
        export = Export(
            order_id=order.id,
            export_type="cutting_layout",
            format="json",
            file_name=file_name,
            file_path=file_path,
            version=version,
            created_by=current_user.id,
        )
        db.add(export)
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="save_cutting_layout",
            user_id=current_user.id,
            new_value={
                "file_name": file_name,
                "version": version,
                "format": "json",
                "preview_svg_path": svg_path,
            },
        )
        db.commit()
        db.refresh(export)
        return export
