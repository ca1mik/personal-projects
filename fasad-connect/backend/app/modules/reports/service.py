"""Отчётность по пунктам 4, 5, 6 ТЗ и по времени изготовления.

Площадь считается из позиций заказа (``OrderItem`` — старый флоу /catalog, и
``OrderPosition`` — смета, актуальный флоу приёма с «Рабочего места»), а не из
сгенерированных деталей (``Part``): менеджер вводит позиции сразу, а детали
появляются позже — иначе свежий заказ давал бы ноль квадратных метров.

Реальный заказ обычно заполнен только одним из двух — ``OrderItem`` или
``OrderPosition``, — но раньше площадь считалась только по ``OrderItem``.
Практика сместилась на смету ещё в этой сессии (лид → заказ → позиции), и
отчёты молча показывали 0,00000 м² на заказах с деньгами и составом: сумма
заказа была настоящей, а площадь — от заказов, которых никто давно не создаёт.
Считаем оба источника — тогда отчёт верен независимо от того, как заказ собран.

Различаем две площади:
  * площадь фасада — то, что заказал клиент;
  * площадь материала — с учётом коэффициента направления (ПВХ клеится на две
    стороны, значит плёнки нужно вдвое больше).
"""

from __future__ import annotations

import statistics
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.clients.models import Client
from app.modules.directions.models import ProductionDirection
from app.modules.orders.models import Order, OrderItem
from app.modules.price_book.kinds import kind_label
from app.modules.production.models import OrderStageInstance
from app.modules.reports.periods import Period, month_bucket, month_label, resolve_period
from app.modules.reports.schemas import (
    ClientActivityReport,
    ClientActivityRow,
    OrderCycleRow,
    OrderVolumeReport,
    OrderVolumeRow,
    PeriodRead,
    ProductionTimeReport,
    StageDurationRow,
    VolumeReport,
    VolumeRow,
    VolumeTotals,
    WorkKindArticleRow,
    WorkKindReport,
    WorkKindRow,
)

SQ_MM_IN_SQ_M = Decimal("1000000")
NO_DIRECTION_KEY = "none"
NO_DIRECTION_LABEL = "Без направления"

METRIC_LABELS = {"accepted": "Принято", "shipped": "Отгружено"}

# Порог «постоянного» клиента и «спящего». Значения уточняются с заказчиком —
# сейчас взята типовая практика: три заказа делают клиента постоянным,
# три месяца тишины переводят в спящие.
REGULAR_ORDERS_THRESHOLD = 3
SLEEPING_AFTER_DAYS = 90
LOST_AFTER_DAYS = 180

CATEGORY_LABELS = {
    "regular": "Постоянный",
    "active": "Активный",
    "new": "Новый",
    "sleeping": "Спящий",
    "lost": "Потерянный",
    "no_orders": "Без заказов",
}


def _as_utc(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _round_totals(totals: VolumeTotals) -> VolumeTotals:
    """Округляет площади один раз — перед выдачей наружу.

    Внутри отчёт складывает точные значения, иначе погрешность каждого заказа
    попадала бы в итог.
    """
    totals.facade_area_sqm = _quantize_area(totals.facade_area_sqm)
    totals.material_area_sqm = _quantize_area(totals.material_area_sqm)
    return totals


def _quantize_area(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"))


def _quantize_hours(value: float) -> Decimal:
    return Decimal(str(round(value, 1)))


def _material_status(order: Order | None) -> tuple[str | None, str | None]:
    """Статус материала последнего заказа клиента — та же логика, что и бейдж
    в списке заказов (`orders/page.tsx`): «отгружен» перебивает «заказан»,
    иначе бейдж молча врёт, что материал ещё едет, хотя он уже на месте.
    Заказов у клиента ещё не было — статуса тоже нет (не «не заказан»)."""
    if order is None:
        return None, None
    if order.shipped_at:
        return "shipped", "материал отгружен"
    if order.material_ordered:
        return "ordered", "материал заказан"
    return "not_ordered", "материал не заказан"


def _order_direction_key(order: Order) -> str:
    """Ключ направления заказа. Заказы без направления — своя группа."""
    return order.direction.code if order.direction is not None else NO_DIRECTION_KEY


def _normalize_direction(code: str | None) -> str | None:
    """Пустая строка в query — это «все направления», а не «направление ''»."""
    wanted = (code or "").strip()
    return wanted or None


def _direction_label(db: Session, code: str | None) -> str | None:
    """Название направления для шапки выгрузки.

    Заказчик: «цифры в файле молча расходятся с экраном». Название пишем в файл,
    чтобы по распечатке было видно, что отчёт не по всему производству.
    Неизвестный код не подменяем на «все»: пусть в шапке стоит то, что спросили.
    """
    if code is None:
        return None
    if code == NO_DIRECTION_KEY:
        return NO_DIRECTION_LABEL
    found = db.scalar(select(ProductionDirection).where(ProductionDirection.code == code))
    return found.name if found is not None else code


class ReportService:
    # --- площадь ----------------------------------------------------------

    @staticmethod
    def item_facade_area(item: OrderItem) -> Decimal:
        """Площадь позиции в м². Габариты хранятся в миллиметрах."""
        return (Decimal(item.width) * Decimal(item.height) * Decimal(item.quantity)) / SQ_MM_IN_SQ_M

    @staticmethod
    def order_areas(order: Order) -> tuple[Decimal, Decimal, int]:
        """Площадь фасадов, площадь материала и число позиций заказа.

        Складывает и каталожные ``OrderItem`` (площадь на штуку), и строки
        сметы ``OrderPosition`` (площадь уже посчитана и лежит в
        ``area_sqm`` — тем же способом, что и здесь: длина × ширина ×
        количество). У обычного заказа заполнено только одно из двух, но
        отчёт не обязан это знать — он просто складывает то, что есть.

        Возвращает **точные** значения, без округления. Округлять здесь нельзя:
        итог считается суммой по заказам, и погрешность каждого заказа копилась
        бы в общей цифре. На двенадцати заказах это давало 9.639 вместо 9.640 и
        ломало равенство «материал ПВХ = площадь фасадов x 2». Округление —
        только один раз, при выводе.
        """
        items_area = sum(
            (ReportService.item_facade_area(item) for item in order.items), Decimal("0")
        )
        positions_area = sum(
            (Decimal(position.area_sqm) for position in order.positions), Decimal("0")
        )
        facade = items_area + positions_area
        factor = (
            Decimal(order.direction.material_area_factor)
            if order.direction is not None
            else Decimal("1")
        )
        return facade, facade * factor, len(order.items) + len(order.positions)

    # --- выборка заказов --------------------------------------------------

    @staticmethod
    def _orders_in_period(db: Session, period: Period, metric: str) -> list[Order]:
        """Заказы периода. ``accepted`` — по дате создания, ``shipped`` — по дате отгрузки."""
        stmt = select(Order).where(Order.deleted_at.is_(None)).options(
            selectinload(Order.items),
            selectinload(Order.positions),
            joinedload(Order.direction),
            joinedload(Order.client),
            joinedload(Order.status),
        )

        moment_column = Order.shipped_at if metric == "shipped" else Order.created_at
        if metric == "shipped":
            stmt = stmt.where(Order.shipped_at.is_not(None))
        if period.date_from is not None:
            stmt = stmt.where(moment_column >= period.date_from)
        if period.date_to is not None:
            stmt = stmt.where(moment_column <= period.date_to)

        return list(db.scalars(stmt.order_by(moment_column.desc())).unique().all())

    @staticmethod
    def _accumulate(target: VolumeTotals, order: Order) -> None:
        facade, material, items = ReportService.order_areas(order)
        target.orders_count += 1
        target.amount += Decimal(order.final_amount)
        # складываем точные значения, округление — на выводе
        target.facade_area_sqm += facade
        target.material_area_sqm += material
        target.items_count += items

    # --- отчёт по обработке ------------------------------------------------

    @staticmethod
    def work_kind_report(
        db: Session,
        *,
        metric: str = "accepted",
        period_code: str = "month",
        date_from: date | None = None,
        date_to: date | None = None,
        direction_code: str | None = None,
    ) -> WorkKindReport:
        """Сколько прошло фрезеровки, шпона, мыла — в м², штуках и рублях.

        Источник — строки сметы заказа: только они знают тип работы. Заказы без
        сметы в отчёт не попадают, и это правильно: за них ещё ничего не
        посчитано.

        Отбор направления фильтрует заказы, а не строки сметы: в заказе на шпон
        может быть и фрезеровка, и её надо посчитать — заказчик смотрит «что я
        сделала по шпону», а не «какие строки называются шпоном».
        """
        metric = metric if metric in METRIC_LABELS else "accepted"
        period = resolve_period(period_code, date_from, date_to)
        wanted = _normalize_direction(direction_code)

        stmt = select(Order).where(Order.deleted_at.is_(None)).options(
            selectinload(Order.positions),
            joinedload(Order.direction),
        )
        moment_column = Order.shipped_at if metric == "shipped" else Order.created_at
        if metric == "shipped":
            stmt = stmt.where(Order.shipped_at.is_not(None))
        if period.date_from is not None:
            stmt = stmt.where(moment_column >= period.date_from)
        if period.date_to is not None:
            stmt = stmt.where(moment_column <= period.date_to)
        orders = list(db.scalars(stmt).unique().all())
        if wanted:
            orders = [order for order in orders if _order_direction_key(order) == wanted]

        total = WorkKindRow(kind="total", kind_label="Всего")
        by_kind: dict[str, WorkKindRow] = {}
        by_article: dict[tuple[str, str], WorkKindArticleRow] = {}
        # Заказ считается один раз на тип: две строки фрезеровки в одном заказе
        # не должны превратиться в два заказа в колонке «Заказов».
        seen_orders: dict[str, set[uuid.UUID]] = defaultdict(set)
        total_orders: set[uuid.UUID] = set()

        def add(row: WorkKindRow, position) -> None:
            row.positions_count += 1
            row.quantity += Decimal(position.quantity)
            row.area_sqm += Decimal(position.area_sqm)
            row.amount += Decimal(position.amount)

        for order in orders:
            for position in order.positions:
                add(total, position)
                total_orders.add(order.id)

                kind_row = by_kind.setdefault(
                    position.kind,
                    WorkKindRow(kind=position.kind, kind_label=kind_label(position.kind)),
                )
                add(kind_row, position)
                seen_orders[position.kind].add(order.id)

                # Нестандарт группируется по названию: артикула у него нет, но
                # менеджеру всё равно надо видеть, что продавали.
                article_key = (position.kind, position.article or position.name)
                article_row = by_article.setdefault(
                    article_key,
                    WorkKindArticleRow(
                        kind=position.kind,
                        kind_label=kind_label(position.kind),
                        article=position.article,
                        name=position.name,
                    ),
                )
                add(article_row, position)
                seen_orders[f"article:{article_key}"].add(order.id)

        total.orders_count = len(total_orders)
        for kind, row in by_kind.items():
            row.orders_count = len(seen_orders[kind])
            row.area_sqm = _quantize_area(row.area_sqm)
        for key, row in by_article.items():
            row.orders_count = len(seen_orders[f"article:{key}"])
            row.area_sqm = _quantize_area(row.area_sqm)
        total.area_sqm = _quantize_area(total.area_sqm)

        return WorkKindReport(
            metric=metric,
            metric_label=METRIC_LABELS[metric],
            direction_code=wanted,
            direction_label=_direction_label(db, wanted),
            period=PeriodRead(
                code=period.code,
                label=period.label,
                date_from=period.date_from,
                date_to=period.date_to,
            ),
            total=total,
            by_kind=sorted(by_kind.values(), key=lambda item: -item.amount),
            by_article=sorted(by_article.values(), key=lambda item: -item.amount),
        )

    # --- отчёт по объёмам (пп. 5, 6 ТЗ) -----------------------------------

    @staticmethod
    def volume_report(
        db: Session,
        *,
        metric: str = "accepted",
        period_code: str = "month",
        date_from: date | None = None,
        date_to: date | None = None,
        direction_code: str | None = None,
    ) -> VolumeReport:
        """Объёмы за период. С направлением — только по нему.

        Заказчик: «а где можно выбрать, по какому направлению я делаю этот
        отчёт?». Разбивка по направлениям в отчёте была, а отбора не было: чтобы
        посмотреть один шпон, приходилось читать строку в таблице и держать в
        уме, что все остальные цифры — не про него.
        """
        metric = metric if metric in METRIC_LABELS else "accepted"
        period = resolve_period(period_code, date_from, date_to)
        orders = ReportService._orders_in_period(db, period, metric)

        wanted = _normalize_direction(direction_code)
        if wanted:
            orders = [order for order in orders if _order_direction_key(order) == wanted]

        total = VolumeTotals()
        by_direction: dict[str, VolumeRow] = {}
        by_month: dict[str, VolumeRow] = {}

        for order in orders:
            ReportService._accumulate(total, order)

            key = _order_direction_key(order)
            label = order.direction.name if order.direction else NO_DIRECTION_LABEL
            row = by_direction.setdefault(key, VolumeRow(key=key, label=label))
            ReportService._accumulate(row, order)

            moment = _as_utc(order.shipped_at if metric == "shipped" else order.created_at)
            if moment is not None:
                bucket = month_bucket(moment)
                month_row = by_month.setdefault(
                    bucket, VolumeRow(key=bucket, label=month_label(bucket))
                )
                ReportService._accumulate(month_row, order)

        return VolumeReport(
            metric=metric,
            metric_label=METRIC_LABELS[metric],
            direction_code=wanted,
            direction_label=_direction_label(db, wanted),
            period=PeriodRead(
                code=period.code,
                label=period.label,
                date_from=period.date_from,
                date_to=period.date_to,
            ),
            total=_round_totals(total),
            by_direction=sorted(
                (_round_totals(row) for row in by_direction.values()),
                key=lambda item: -item.amount,
            ),
            by_month=sorted(
                (_round_totals(row) for row in by_month.values()),
                key=lambda item: item.key,
            ),
        )

    # --- отчёт по клиентам (п. 4 ТЗ) --------------------------------------

    @staticmethod
    def _classify(orders_count: int, days_since: int | None) -> str:
        if orders_count == 0 or days_since is None:
            return "no_orders"
        if days_since > LOST_AFTER_DAYS:
            return "lost"
        if days_since > SLEEPING_AFTER_DAYS:
            return "sleeping"
        if orders_count >= REGULAR_ORDERS_THRESHOLD:
            return "regular"
        if orders_count == 1:
            return "new"
        return "active"

    @staticmethod
    def client_activity_report(
        db: Session,
        *,
        period_code: str = "all",
        date_from: date | None = None,
        date_to: date | None = None,
        inactive_days: int | None = None,
        direction_code: str | None = None,
        client_ids: list[uuid.UUID] | None = None,
    ) -> ClientActivityReport:
        """Кто сколько купил, чем и когда последний раз.

        Закрывает оба отчёта ТЗ: «сумма покупок за период» и «кто давно не
        покупал» (через ``inactive_days``).

        Заказчик: «я всех клиентов галочкой выбираю и вижу, когда последняя
        покупка была» — отмеченные галочками клиенты приходят в ``client_ids``.
        Пустой список — это «не отмечен никто», а не «все»: иначе снятая
        последняя галочка молча возвращала бы полный список.
        """
        period = resolve_period(period_code, date_from, date_to)
        wanted_direction = _normalize_direction(direction_code)
        now = datetime.now(UTC)

        clients = list(db.scalars(select(Client).order_by(Client.full_name.asc())).all())
        if client_ids is not None:
            chosen = set(client_ids)
            clients = [item for item in clients if item.id in chosen]
        orders = list(
            db.scalars(
                select(Order).where(Order.deleted_at.is_(None)).options(
                    selectinload(Order.items),
                    selectinload(Order.positions),
                    joinedload(Order.direction),
                )
            )
            .unique()
            .all()
        )

        grouped: dict[uuid.UUID, list[Order]] = defaultdict(list)
        for order in orders:
            if wanted_direction and _order_direction_key(order) != wanted_direction:
                continue
            grouped[order.client_id].append(order)

        rows: list[ClientActivityRow] = []

        for client in clients:
            client_orders = grouped.get(client.id, [])
            # Давность считается по всей истории, а не по периоду: клиент «давно
            # не покупал» независимо от того, какой период выбран в фильтре.
            all_dates = [_as_utc(order.created_at) for order in client_orders]
            last_order_at = max(all_dates) if all_dates else None
            days_since = (now - last_order_at).days if last_order_at else None
            last_order = (
                max(client_orders, key=lambda order: _as_utc(order.created_at))
                if client_orders
                else None
            )
            material_status, material_status_label = _material_status(last_order)

            in_period = [order for order in client_orders if period.contains(order.created_at)]

            row = ClientActivityRow(
                client_id=client.id,
                full_name=client.full_name,
                organization=client.organization,
                phone=client.phone,
                email=client.email,
                category="no_orders",
                category_label=CATEGORY_LABELS["no_orders"],
                first_order_at=min(all_dates) if all_dates else None,
                last_order_at=last_order_at,
                days_since_last_order=days_since,
                last_order_material_status=material_status,
                last_order_material_status_label=material_status_label,
            )

            directions: set[str] = set()
            for order in in_period:
                ReportService._accumulate(row, order)
                if order.direction is not None:
                    directions.add(order.direction.name)
            row.directions = sorted(directions)

            category = ReportService._classify(len(client_orders), days_since)
            row.category = category
            row.category_label = CATEGORY_LABELS[category]

            if len(all_dates) >= 2:
                # Округляем, а не отбрасываем дробь: при усечении интервал
                # 29,99 дня превращался бы в 29.
                span_seconds = (max(all_dates) - min(all_dates)).total_seconds()
                average = span_seconds / 86400 / (len(all_dates) - 1)
                row.average_days_between_orders = max(1, round(average))

            if inactive_days is not None:
                if days_since is None or days_since < inactive_days:
                    continue
            rows.append(row)

        # Итог считаем ПОСЛЕ отбора, а не по всем клиентам подряд. Регрессия:
        # при ``inactive_days`` шапка выгрузки показывала сумму по всей базе, а
        # таблица под ней — по отфильтрованным, и цифры в одном файле не
        # сходились между собой.
        total = VolumeTotals()
        for row in rows:
            total.orders_count += row.orders_count
            total.amount += row.amount
            total.facade_area_sqm += row.facade_area_sqm
            total.material_area_sqm += row.material_area_sqm
            total.items_count += row.items_count

        for row in rows:
            _round_totals(row)
        rows.sort(key=lambda item: (-item.amount, item.full_name))

        return ClientActivityReport(
            direction_code=wanted_direction,
            direction_label=_direction_label(db, wanted_direction),
            inactive_days=inactive_days,
            selected_clients=len(client_ids) if client_ids is not None else None,
            period=PeriodRead(
                code=period.code,
                label=period.label,
                date_from=period.date_from,
                date_to=period.date_to,
            ),
            total=_round_totals(total),
            rows=rows,
        )

    # --- время изготовления -----------------------------------------------

    @staticmethod
    def production_time_report(
        db: Session,
        *,
        period_code: str = "month",
        date_from: date | None = None,
        date_to: date | None = None,
        direction_code: str | None = None,
    ) -> ProductionTimeReport:
        """Сколько времени занимает каждый этап и сколько идёт заказ целиком."""
        period = resolve_period(period_code, date_from, date_to)
        wanted = _normalize_direction(direction_code)

        stages = list(
            db.scalars(
                select(OrderStageInstance).options(
                    joinedload(OrderStageInstance.workflow_stage),
                    joinedload(OrderStageInstance.order).joinedload(Order.direction),
                    joinedload(OrderStageInstance.order).joinedload(Order.client),
                )
            )
            .unique()
            .all()
        )
        if wanted:
            # Этап принадлежит заказу, поэтому отбор направления фильтрует
            # этапы через заказ: «сколько у меня идёт шпон» — вопрос про заказы
            # шпона, а не про участок.
            stages = [
                stage
                for stage in stages
                if stage.order is not None and _order_direction_key(stage.order) == wanted
            ]

        durations: dict[str, list[float]] = defaultdict(list)
        meta: dict[str, StageDurationRow] = {}

        for stage in stages:
            definition = stage.workflow_stage
            if definition is None:
                continue
            row = meta.setdefault(
                definition.code,
                StageDurationRow(
                    stage_code=definition.code,
                    stage_name=definition.name,
                    work_center_name=(
                        definition.work_center.name if definition.work_center else None
                    ),
                ),
            )

            if stage.status == "in_progress":
                row.in_progress_count += 1
            elif stage.status == "blocked":
                row.blocked_count += 1

            started = _as_utc(stage.started_at)
            completed = _as_utc(stage.completed_at)
            if stage.status != "done" or started is None or completed is None:
                continue
            if not period.contains(stage.completed_at):
                continue

            row.completed_count += 1
            durations[definition.code].append((completed - started).total_seconds() / 3600)

        for code, values in durations.items():
            if not values:
                continue
            row = meta[code]
            row.average_hours = _quantize_hours(sum(values) / len(values))
            row.median_hours = _quantize_hours(statistics.median(values))
            row.longest_hours = _quantize_hours(max(values))

        by_order: dict[uuid.UUID, list[OrderStageInstance]] = defaultdict(list)
        for stage in stages:
            by_order[stage.order_id].append(stage)

        orders: list[OrderCycleRow] = []
        for order_id, items in by_order.items():
            order = items[0].order
            if order is None:
                continue

            done = [item for item in items if item.status == "done"]
            finished = len(done) == len(items)
            reference = max(
                (_as_utc(item.completed_at) for item in done if item.completed_at), default=None
            )
            if not period.contains(reference or order.created_at):
                continue

            started_all = [_as_utc(item.started_at) for item in items if item.started_at]
            production_hours: Decimal | None = None
            if started_all and reference is not None:
                production_hours = _quantize_hours(
                    (reference - min(started_all)).total_seconds() / 3600
                )

            current = next(
                (
                    item.workflow_stage.name
                    for item in sorted(items, key=lambda x: x.workflow_stage.sort_order)
                    if item.status != "done" and item.workflow_stage is not None
                ),
                None,
            )

            orders.append(
                OrderCycleRow(
                    order_id=order_id,
                    order_number=order.order_number,
                    direction_name=order.direction.name if order.direction else None,
                    client_name=order.client.full_name if order.client else None,
                    stages_total=len(items),
                    stages_done=len(done),
                    current_stage_name=current,
                    production_hours=production_hours,
                    is_finished=finished,
                )
            )

        orders.sort(key=lambda item: (item.is_finished, item.order_number))

        return ProductionTimeReport(
            direction_code=wanted,
            direction_label=_direction_label(db, wanted),
            period=PeriodRead(
                code=period.code,
                label=period.label,
                date_from=period.date_from,
                date_to=period.date_to,
            ),
            by_stage=sorted(meta.values(), key=lambda item: item.stage_name),
            orders=orders,
        )

    # --- заказы построчно ---------------------------------------------------

    @staticmethod
    def order_volume_report(
        db: Session,
        *,
        metric: str = "accepted",
        period_code: str = "month",
        date_from: date | None = None,
        date_to: date | None = None,
        direction_code: str | None = None,
        client_ids: list[uuid.UUID] | None = None,
    ) -> OrderVolumeReport:
        """Заказы построчно: сумма и площадь каждой сделки.

        Свёрнутые итоги по направлениям бухгалтерии не годятся — нужен файл, где
        строка это заказ. Считаем теми же ``order_areas``, что и сводка, иначе
        сумма строк не сойдётся с итогом на экране.
        """
        metric = metric if metric in METRIC_LABELS else "accepted"
        period = resolve_period(period_code, date_from, date_to)
        wanted = _normalize_direction(direction_code)

        orders = ReportService._orders_in_period(db, period, metric)
        if wanted:
            orders = [order for order in orders if _order_direction_key(order) == wanted]
        if client_ids is not None:
            chosen = set(client_ids)
            orders = [order for order in orders if order.client_id in chosen]

        total = VolumeTotals()
        rows: list[OrderVolumeRow] = []
        for order in orders:
            ReportService._accumulate(total, order)
            facade, material, items = ReportService.order_areas(order)
            rows.append(
                OrderVolumeRow(
                    order_id=order.id,
                    order_number=order.order_number,
                    created_at=_as_utc(order.created_at),
                    shipped_at=_as_utc(order.shipped_at),
                    client_name=order.client.full_name if order.client else None,
                    organization=order.client.organization if order.client else None,
                    direction_name=(
                        order.direction.name if order.direction else NO_DIRECTION_LABEL
                    ),
                    status_name=order.status.name if order.status else None,
                    items_count=items,
                    facade_area_sqm=_quantize_area(facade),
                    material_area_sqm=_quantize_area(material),
                    amount=Decimal(order.final_amount),
                )
            )

        return OrderVolumeReport(
            metric=metric,
            metric_label=METRIC_LABELS[metric],
            direction_code=wanted,
            direction_label=_direction_label(db, wanted),
            period=PeriodRead(
                code=period.code,
                label=period.label,
                date_from=period.date_from,
                date_to=period.date_to,
            ),
            total=_round_totals(total),
            rows=rows,
        )
