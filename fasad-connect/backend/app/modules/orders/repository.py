from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.pagination import PageParams, pagination_meta
from app.modules.clients.models import Client
from app.modules.directions.models import ProductionDirection
from app.modules.order_statuses.models import OrderStatus, OrderStatusHistory
from app.modules.orders.models import Order, OrderItem
from app.modules.users.models import User

#: Значение фильтра «направление не указано».
NO_DIRECTION_CODE = "none"

#: Форма номера заказа. Заказчик различает типы именно так: «просто номер»,
#: «номер и буква», «номер и две буквы».
NUMBER_SHAPES = {
    "plain": lambda length: length == 0,
    "letter": lambda length: length == 1,
    "double": lambda length: length >= 2,
}

NUMBER_SHAPE_LABELS = {
    "plain": "Просто номер",
    "letter": "Номер и буква",
    "double": "Номер и две буквы",
}


class OrderRepository:
    @staticmethod
    def get_by_id(db: Session, order_id: uuid.UUID) -> Order | None:
        stmt = (
            select(Order)
            .options(
                joinedload(Order.client),
                joinedload(Order.source_lead),
                joinedload(Order.direction),
                joinedload(Order.manager).joinedload(User.role),
                joinedload(Order.status),
                selectinload(Order.items).joinedload(OrderItem.template),
                selectinload(Order.positions),
                selectinload(Order.payments),
                selectinload(Order.status_history).joinedload(OrderStatusHistory.old_status),
                selectinload(Order.status_history).joinedload(OrderStatusHistory.new_status),
                # Допы и родитель нужны карточке всегда: их читает `to_read`.
                # Без загрузки здесь каждое обращение к ним — отдельный запрос.
                selectinload(Order.additional_orders).joinedload(Order.status),
                joinedload(Order.parent_order),
            )
            .where(Order.id == order_id)
        )
        return db.scalar(stmt)

    @staticmethod
    def get_by_source_lead(db: Session, lead_id: uuid.UUID) -> Order | None:
        return db.scalar(select(Order).where(Order.source_lead_id == lead_id))

    @staticmethod
    def list_orders(
        db: Session,
        params: PageParams,
        *,
        status_code: str | None = None,
        #: «Обычные» = все, кроме этого статуса. Отдельно от status_code, а не
        #: значением вроде "not_cancelled": один параметр отвечал бы за две
        #: разные вещи (точное совпадение и исключение), и это путало бы как
        #: код, так и адрес страницы при копировании ссылки.
        exclude_status_code: str | None = None,
        client_id: uuid.UUID | None = None,
        direction_code: str | None = None,
        number_shape: str | None = None,
        material_ordered: bool | None = None,
        lifecycle: str | None = None,
        deleted: bool = False,
        date_from: date | None = None,
        date_to: date | None = None,
        search: str | None = None,
        # Клик по заголовку «Срок» в списке заказов: по возрастанию — что горит
        # раньше, наверх; по убыванию — наоборот. Без сортировки, как раньше,
        # список идёт по дате создания.
        sort_by: str | None = None,
        sort_dir: str = "asc",
    ) -> tuple[list[Order], dict]:
        stmt = select(Order).options(
            selectinload(Order.source_lead),
            joinedload(Order.client),
            joinedload(Order.direction),
            joinedload(Order.status),
            joinedload(Order.manager),
            # Список заказов показывает долг и аванс, поэтому смета и
            # оплаты грузятся сразу — иначе на каждой строке будет свой
            # запрос в базу.
            selectinload(Order.positions),
            selectinload(Order.payments),
            # То же и с допами: `to_read` читает их на каждой строке, а
            # ленивая связь превращала список из ста заказов в двести
            # лишних запросов.
            selectinload(Order.additional_orders).joinedload(Order.status),
            joinedload(Order.parent_order),
        )
        if sort_by == "due_date":
            # Пустой срок — всегда в конец списка, что бы ни сортировали: заказ
            # без названной даты не «самый ранний», просто её ещё не назвали.
            column = Order.due_date.desc() if sort_dir == "desc" else Order.due_date.asc()
            stmt = stmt.order_by(Order.due_date.is_(None), column, Order.created_at.desc())
        else:
            stmt = stmt.order_by(Order.created_at.desc())
        count_stmt = select(func.count()).select_from(Order)

        def apply(criteria) -> None:
            nonlocal stmt, count_stmt
            stmt = stmt.where(criteria)
            count_stmt = count_stmt.where(criteria)

        apply(Order.deleted_at.is_not(None) if deleted else Order.deleted_at.is_(None))
        if lifecycle:
            from app.modules.orders.lifecycle import lifecycle_criteria
            apply(lifecycle_criteria(lifecycle))

        if status_code or exclude_status_code:
            stmt = stmt.join(OrderStatus, Order.status_id == OrderStatus.id)
            count_stmt = count_stmt.join(OrderStatus, Order.status_id == OrderStatus.id)
            if status_code:
                apply(OrderStatus.code == status_code)
            if exclude_status_code:
                apply(OrderStatus.code != exclude_status_code)
        if client_id:
            apply(Order.client_id == client_id)

        if direction_code == NO_DIRECTION_CODE:
            apply(Order.direction_id.is_(None))
        elif direction_code:
            apply(
                Order.direction_id.in_(
                    select(ProductionDirection.id).where(ProductionDirection.code == direction_code)
                )
            )

        # Фильтр по форме номера: «0001» без буквы, «0001-П» с одной,
        # «0001-ОШ» с двумя. Длину берём у направления, а не разбором строки
        # номера — так фильтр не сломается от переноса данных или ручной правки.
        if number_shape in NUMBER_SHAPES:
            matching = select(ProductionDirection.id).where(
                NUMBER_SHAPES[number_shape](func.length(ProductionDirection.number_suffix))
            )
            if number_shape == "plain":
                # Без буквы — это и направления с пустым суффиксом, и заказы,
                # у которых направление не указано вовсе.
                apply(or_(Order.direction_id.is_(None), Order.direction_id.in_(matching)))
            else:
                apply(Order.direction_id.in_(matching))

        # «На что материал ещё не заказан» — вопрос каждого утра перед звонком
        # поставщику. Раньше отметка была только в карточке, а отобрать по ней
        # список было нечем: индекс под неё есть с миграции 0019 и не работал.
        if material_ordered is not None:
            apply(Order.material_ordered.is_(material_ordered))

        if date_from:
            apply(
                Order.created_at
                >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC)
            )
        if date_to:
            apply(
                Order.created_at
                <= datetime(
                    date_to.year, date_to.month, date_to.day, 23, 59, 59, 999999, tzinfo=UTC
                )
            )

        if search:
            pattern = f"%{search.lower()}%"
            apply(
                or_(
                    func.lower(Order.order_number).like(pattern),
                    func.lower(func.coalesce(Order.comment, "")).like(pattern),
                    func.lower(Client.full_name).like(pattern),
                    func.lower(func.coalesce(Client.organization, "")).like(pattern),
                )
            )
            stmt = stmt.join(Client, Order.client_id == Client.id)
            count_stmt = count_stmt.join(Client, Order.client_id == Client.id)

        total = db.scalar(count_stmt) or 0
        items = db.scalars(stmt.offset(params.offset).limit(params.size)).unique().all()
        return items, pagination_meta(total, params)
