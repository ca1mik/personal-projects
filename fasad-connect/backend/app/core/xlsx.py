"""Сборка XLSX-выгрузок: одна вёрстка на все отчёты и выписки.

Файл открывают в Excel и отдают бухгалтерии, поэтому важны мелочи: числа
должны быть числами (а не текстом), деньги — с разделителем разрядов, шапка —
закреплена, ширина колонок — по содержимому. Держим это в одном месте, чтобы
восемь выгрузок не разъехались по оформлению.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

#: Деньги и площадь выводятся с двумя знаками после запятой.
MONEY_FORMAT = "# ##0.00"
AREA_FORMAT = "0.00"
DATE_FORMAT = "DD.MM.YYYY"
DATETIME_FORMAT = "DD.MM.YYYY HH:MM"

ColumnKind = Literal["text", "money", "area", "number", "date", "datetime"]

HEADER_FILL = PatternFill("solid", fgColor="F1F5F9")
TOTAL_FILL = PatternFill("solid", fgColor="FEF3C7")
THIN = Side(style="thin", color="CBD5E1")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


@dataclass(frozen=True)
class Column:
    """Колонка выгрузки: заголовок, ключ в строке и как показывать значение."""

    title: str
    key: str
    kind: ColumnKind = "text"
    width: int = 16


def _apply(cell, kind: ColumnKind) -> None:
    # Вертикальное выравнивание — одинаковое для всех типов колонок. Текстовые
    # колонки переносятся (`wrap_text`), и если у длинного имени клиента строка
    # растягивается на две строки, а числа рядом остаются по умолчанию прижаты
    # к низу ячейки — вся строка визуально «съезжает». Заказчик увидел это
    # именно на «Тутаева Ольга Александровна»: имя сверху, а «4 / 14 379,59» в
    # той же строке — заметно ниже. `center` держит строку вместе при любой
    # высоте, перенесётся текст или нет.
    if kind == "money":
        cell.number_format = MONEY_FORMAT
        cell.alignment = Alignment(horizontal="right", vertical="center")
    elif kind == "area":
        cell.number_format = AREA_FORMAT
        cell.alignment = Alignment(horizontal="right", vertical="center")
    elif kind == "number":
        cell.alignment = Alignment(horizontal="right", vertical="center")
    elif kind == "date":
        cell.number_format = DATE_FORMAT
        cell.alignment = Alignment(vertical="center")
    elif kind == "datetime":
        cell.number_format = DATETIME_FORMAT
        cell.alignment = Alignment(vertical="center")
    else:
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def _value(raw: object, kind: ColumnKind) -> object:
    """Приводит значение к типу, который Excel сумеет сложить.

    Decimal из API приходит строкой; если положить её как есть, столбец в Excel
    не суммируется, и бухгалтер получит текст вместо чисел.
    """
    if raw is None:
        return None
    if kind in {"money", "area", "number"}:
        if kind == "number" and isinstance(raw, int) and not isinstance(raw, bool):
            # Счётчик остаётся целым: «3 заказа», а не «3,0».
            return raw
        try:
            return float(Decimal(str(raw)))
        except (ArithmeticError, TypeError, ValueError):
            return raw
    if kind in {"date", "datetime"}:
        if isinstance(raw, datetime):
            # Excel не умеет хранить зону — отдаём наивное local-время
            return raw.replace(tzinfo=None)
        if isinstance(raw, date):
            return raw
        return str(raw)
    return raw


def write_title(sheet: Worksheet, row: int, text: str, *, size: int = 13) -> int:
    sheet.cell(row=row, column=1, value=text).font = Font(bold=True, size=size)
    return row + 1


def _guess_kind(value: object) -> ColumnKind:
    """Как показать значение в шапке, если тип не указан явно.

    Целое — это счётчик («Заказов: 3»), и денежный формат превращал его в
    «3,00»: заказчик читала это как сумму. Дробное в шапке — почти всегда
    деньги, поэтому для него денежный формат остаётся значением по умолчанию;
    площади в отчётах передают тип явно.
    """
    if isinstance(value, bool):
        return "text"
    if isinstance(value, int):
        return "number"
    if isinstance(value, (float, Decimal)):
        return "money"
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    return "text"


def write_pairs(
    sheet: Worksheet,
    row: int,
    pairs: list[tuple[str, object]] | list[tuple[str, object, ColumnKind]],
) -> int:
    """Шапка выгрузки: «Клиент: …», «Период: …», «Баланс: …».

    Пара может быть трёхэлементной — тогда третий элемент задаёт формат ячейки
    явно. Это нужно площадям и счётчикам: по типу значения их от денег не
    отличить, а «3,00 м²» в шапке читается как рубли.
    """
    for pair in pairs:
        label, value = pair[0], pair[1]
        kind: ColumnKind = pair[2] if len(pair) > 2 else _guess_kind(value)  # type: ignore[misc]
        sheet.cell(row=row, column=1, value=label).font = Font(bold=True)
        cell = sheet.cell(row=row, column=2, value=_value(value, kind))
        if kind != "text":
            _apply(cell, kind)
        row += 1
    return row


def write_table(
    sheet: Worksheet,
    row: int,
    columns: list[Column],
    rows: list[dict],
    *,
    total_row: dict | None = None,
    freeze: bool = True,
) -> int:
    """Таблица с шапкой, рамкой и, если нужно, строкой итога."""
    header_row = row
    for index, column in enumerate(columns, start=1):
        cell = sheet.cell(row=header_row, column=index, value=column.title)
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        sheet.column_dimensions[get_column_letter(index)].width = column.width
    row += 1

    for item in rows:
        for index, column in enumerate(columns, start=1):
            cell = sheet.cell(
                row=row, column=index, value=_value(item.get(column.key), column.kind)
            )
            cell.border = BORDER
            _apply(cell, column.kind)
        row += 1

    if total_row is not None:
        for index, column in enumerate(columns, start=1):
            cell = sheet.cell(
                row=row, column=index, value=_value(total_row.get(column.key), column.kind)
            )
            cell.font = Font(bold=True)
            cell.fill = TOTAL_FILL
            cell.border = BORDER
            _apply(cell, column.kind)
        row += 1

    if freeze:
        # Шапка закреплена: в выгрузке на 300 строк без этого не разобрать,
        # какая колонка перед тобой.
        sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
    return row


def new_workbook(sheet_title: str) -> tuple[Workbook, Worksheet]:
    book = Workbook()
    sheet = book.active
    sheet.title = sheet_title[:31]
    return book, sheet


def to_bytes(book: Workbook) -> bytes:
    stream = io.BytesIO()
    book.save(stream)
    return stream.getvalue()
