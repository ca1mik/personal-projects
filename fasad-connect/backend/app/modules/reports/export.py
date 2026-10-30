"""Отчёты файлом: то же, что на экране, только в Excel.

Экран нужен, чтобы посмотреть, файл — чтобы отдать: бухгалтерии, директору, в
папку за месяц. Поэтому цифры берутся из тех же сервисов, что рисуют экран, —
две ветки расчёта разошлись бы на первом же округлении.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.xlsx import (
    Column,
    ColumnKind,
    new_workbook,
    to_bytes,
    write_pairs,
    write_table,
    write_title,
)
from app.modules.reports.schemas import (
    ClientActivityReport,
    OrderVolumeReport,
    ProductionTimeReport,
    VolumeReport,
    WorkKindReport,
)

VOLUME_COLUMNS = [
    Column("Направление", "label", width=22),
    Column("Заказов", "orders_count", "number", width=10),
    Column("Сумма", "amount", "money", width=16),
    Column("Площадь фасадов, м²", "facade_area_sqm", "area", width=20),
    Column("Площадь материала, м²", "material_area_sqm", "area", width=21),
    Column("Позиций", "items_count", "number", width=10),
]

WORK_KIND_COLUMNS = [
    Column("Тип работы", "kind_label", width=20),
    Column("Заказов", "orders_count", "number", width=10),
    Column("Строк", "positions_count", "number", width=10),
    Column("Количество", "quantity", "number", width=12),
    Column("Площадь, м²", "area_sqm", "area", width=15),
    Column("Сумма", "amount", "money", width=16),
]

WORK_KIND_ARTICLE_COLUMNS = [
    Column("Артикул", "article", width=14),
    Column("Наименование", "name", width=28),
    Column("Тип работы", "kind_label", width=18),
    Column("Заказов", "orders_count", "number", width=10),
    Column("Площадь, м²", "area_sqm", "area", width=15),
    Column("Сумма", "amount", "money", width=16),
]

CLIENT_COLUMNS = [
    # 30, не 26: «Тутаева Ольга Александровна» (27 символов) на 26 переносилась
    # на вторую строку и визуально «уезжала» от чисел той же строки.
    Column("Клиент", "full_name", width=30),
    Column("Организация", "organization", width=22),
    Column("Телефон", "phone", width=16),
    Column("Тип", "category_label", width=14),
    Column("Заказов", "orders_count", "number", width=10),
    Column("Сумма", "amount", "money", width=16),
    Column("Площадь фасадов, м²", "facade_area_sqm", "area", width=20),
    Column("Последний заказ", "last_order_at", "date", width=15),
    Column("Дней без заказов", "days_since_last_order", "number", width=16),
    Column("Материал (посл. заказ)", "last_order_material_status_label", width=20),
]

STAGE_COLUMNS = [
    Column("Этап", "stage_name", width=24),
    Column("Участок", "work_center_name", width=20),
    Column("Завершено", "completed_count", "number", width=11),
    Column("В работе", "in_progress_count", "number", width=10),
    Column("Заблокировано", "blocked_count", "number", width=14),
    Column("Среднее, ч", "average_hours", "number", width=12),
    Column("Медиана, ч", "median_hours", "number", width=12),
    Column("Дольше всего, ч", "longest_hours", "number", width=15),
]

ORDER_CYCLE_COLUMNS = [
    Column("Заказ", "order_number", width=14),
    Column("Клиент", "client_name", width=24),
    Column("Направление", "direction_name", width=18),
    Column("Этапов", "stages_total", "number", width=9),
    Column("Готово", "stages_done", "number", width=9),
    Column("Текущий этап", "current_stage_name", width=22),
    Column("В производстве, ч", "production_hours", "number", width=17),
]

#: Строка = заказ. Заказчик сводит объёмы по заказам руками, поэтому нужен файл
#: без свёрнутых итогов: номер, дата, клиент, сумма, площадь.
ORDER_VOLUME_COLUMNS = [
    Column("Заказ", "order_number", width=14),
    Column("Принят", "created_at", "date", width=12),
    Column("Отгружен", "shipped_at", "date", width=12),
    Column("Клиент", "client_name", width=26),
    Column("Организация", "organization", width=22),
    Column("Направление", "direction_name", width=18),
    Column("Статус", "status_name", width=18),
    Column("Позиций", "items_count", "number", width=9),
    Column("Площадь фасадов, м²", "facade_area_sqm", "area", width=20),
    Column("Площадь материала, м²", "material_area_sqm", "area", width=21),
    Column("Сумма", "amount", "money", width=16),
]


def _period_pairs(report) -> list[tuple[str, object, ColumnKind]]:
    """Шапка файла: период и, если он задан, отобранное направление.

    Направление печатаем обязательно. Заказчик: «цифры в файле молча расходятся
    с экраном» — без подписи по распечатке не понять, что отчёт не по всему
    производству, а только по шпону.
    """
    period = report.period
    pairs: list[tuple[str, object, ColumnKind]] = [("Период", period.label, "text")]
    if period.date_from:
        # Только дата: границы периода — это начало и конец суток, и «00:00» в
        # шапке лишь сбивает с толку.
        pairs.append(("С", period.date_from.date(), "date"))
    if period.date_to:
        pairs.append(("По", period.date_to.date(), "date"))
    label = getattr(report, "direction_label", None)
    pairs.append(("Направление", label or "Все направления", "text"))
    return pairs


def build_volume_xlsx(report: VolumeReport) -> bytes:
    book, sheet = new_workbook("Объёмы")
    row = write_title(sheet, 1, f"Объёмы: {report.metric_label}")
    row = write_pairs(
        sheet,
        row + 1,
        [
            *_period_pairs(report),
            ("Заказов", report.total.orders_count, "number"),
            ("Сумма", float(report.total.amount), "money"),
            ("Площадь фасадов, м²", float(report.total.facade_area_sqm), "area"),
            ("Площадь материала, м²", float(report.total.material_area_sqm), "area"),
        ],
    )

    row = write_title(sheet, row + 1, "По направлениям", size=11)
    rows = [item.model_dump() for item in report.by_direction]
    total = report.total.model_dump()
    total["label"] = "Итого"
    row = write_table(sheet, row, VOLUME_COLUMNS, rows, total_row=total if rows else None)

    months = book.create_sheet("По месяцам")
    month_row = write_title(months, 1, "Помесячно")
    write_table(
        months,
        month_row + 1,
        VOLUME_COLUMNS,
        [item.model_dump() for item in report.by_month],
    )
    return to_bytes(book)


def build_work_kind_xlsx(report: WorkKindReport) -> bytes:
    book, sheet = new_workbook("Обработка")
    row = write_title(sheet, 1, f"Обработка: {report.metric_label}")
    row = write_pairs(
        sheet,
        row + 1,
        [
            *_period_pairs(report),
            ("Заказов", report.total.orders_count, "number"),
            ("Строк", report.total.positions_count, "number"),
            ("Площадь, м²", float(report.total.area_sqm), "area"),
            ("Сумма", float(report.total.amount), "money"),
        ],
    )

    row = write_title(sheet, row + 1, "По типам работ", size=11)
    rows = [item.model_dump() for item in report.by_kind]
    total = report.total.model_dump()
    total["kind_label"] = "Итого"
    row = write_table(sheet, row, WORK_KIND_COLUMNS, rows, total_row=total if rows else None)

    articles = book.create_sheet("По артикулам")
    article_row = write_title(articles, 1, "Разбивка до артикула")
    write_table(
        articles,
        article_row + 1,
        WORK_KIND_ARTICLE_COLUMNS,
        [
            {**item.model_dump(), "article": item.article or "нестандарт"}
            for item in report.by_article
        ],
    )
    return to_bytes(book)


def build_clients_xlsx(
    report: ClientActivityReport,
    orders: OrderVolumeReport | None = None,
) -> bytes:
    """Клиенты: сводка и, вторым листом, их заказы построчно.

    Два листа обещаны в docs/statements-and-exports.md, но их не было: файл
    отдавал одну свёрнутую таблицу, и «а из чего эта сумма» приходилось
    выяснять в системе. ``orders`` — те же клиенты и тот же период.
    """
    book, sheet = new_workbook("Клиенты")
    row = write_title(sheet, 1, "Клиенты за период")

    pairs: list[tuple[str, object, ColumnKind]] = [
        *_period_pairs(report),
        ("Клиентов", len(report.rows), "number"),
        ("Заказов", report.total.orders_count, "number"),
        ("Сумма", float(report.total.amount), "money"),
    ]
    if report.inactive_days is not None:
        pairs.append(("Не заказывал дольше, дней", report.inactive_days, "number"))
    if report.selected_clients is not None:
        pairs.append(("Отмечено галочками", report.selected_clients, "number"))
    row = write_pairs(sheet, row + 1, pairs)

    rows = [item.model_dump() for item in report.rows]
    total = {
        "full_name": "Итого",
        "orders_count": report.total.orders_count,
        "amount": report.total.amount,
        "facade_area_sqm": report.total.facade_area_sqm,
    }
    write_table(sheet, row + 1, CLIENT_COLUMNS, rows, total_row=total if rows else None)

    detail = book.create_sheet("Заказы")
    detail_row = write_title(detail, 1, "Заказы этих клиентов")
    order_rows = [item.model_dump() for item in orders.rows] if orders else []
    order_total = (
        {
            "order_number": "Итого",
            "items_count": orders.total.items_count,
            "facade_area_sqm": orders.total.facade_area_sqm,
            "material_area_sqm": orders.total.material_area_sqm,
            "amount": orders.total.amount,
        }
        if orders and order_rows
        else None
    )
    write_table(
        detail,
        detail_row + 1,
        ORDER_VOLUME_COLUMNS,
        order_rows,
        total_row=order_total,
    )
    return to_bytes(book)


def build_orders_xlsx(report: OrderVolumeReport) -> bytes:
    """Заказы построчно: строка = заказ с суммой и площадью."""
    book, sheet = new_workbook("Заказы")
    row = write_title(sheet, 1, f"Заказы: {report.metric_label}")
    row = write_pairs(
        sheet,
        row + 1,
        [
            *_period_pairs(report),
            ("Заказов", report.total.orders_count, "number"),
            ("Сумма", float(report.total.amount), "money"),
            ("Площадь фасадов, м²", float(report.total.facade_area_sqm), "area"),
            ("Площадь материала, м²", float(report.total.material_area_sqm), "area"),
        ],
    )

    rows = [item.model_dump() for item in report.rows]
    total = {
        "order_number": "Итого",
        "items_count": report.total.items_count,
        "facade_area_sqm": report.total.facade_area_sqm,
        "material_area_sqm": report.total.material_area_sqm,
        "amount": report.total.amount,
    }
    write_table(sheet, row + 1, ORDER_VOLUME_COLUMNS, rows, total_row=total if rows else None)
    return to_bytes(book)


def build_production_time_xlsx(report: ProductionTimeReport) -> bytes:
    book, sheet = new_workbook("Этапы")
    row = write_title(sheet, 1, "Время изготовления")
    row = write_pairs(sheet, row + 1, _period_pairs(report))

    row = write_title(sheet, row + 1, "По этапам", size=11)
    row = write_table(sheet, row, STAGE_COLUMNS, [item.model_dump() for item in report.by_stage])

    orders = book.create_sheet("Заказы")
    order_row = write_title(orders, 1, "Заказы в производстве")
    write_table(
        orders,
        order_row + 1,
        ORDER_CYCLE_COLUMNS,
        [item.model_dump() for item in report.orders],
    )
    return to_bytes(book)


def money_total(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0"))
