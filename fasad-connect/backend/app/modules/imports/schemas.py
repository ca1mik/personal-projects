from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:  # pragma: no cover - только для подсказок типов
    from app.modules.imports.parser import ParsedPart


class ImportedPartRead(BaseModel):
    width: int
    height: int
    quantity: int
    thickness: str | None = None
    milling: str | None = None
    color: str | None = None
    # что было написано в бланке до чистки — менеджер сверяет с бумагой
    color_source: str | None = None
    milling_source: str | None = None

    @classmethod
    def from_parsed(cls, part: ParsedPart) -> ImportedPartRead:
        """Собирает ответ из разобранной строки бланка.

        Отдельный конструктор, чтобы новые поля разбора не приходилось
        дописывать в каждом месте, где строится ответ.
        """
        return cls(
            width=part.width,
            height=part.height,
            quantity=part.quantity,
            thickness=part.thickness,
            milling=part.milling,
            color=part.color,
            color_source=part.color_source,
            milling_source=part.milling_source,
        )


class PartsImportRead(BaseModel):
    """Разобранный список деталей из выгрузки заказчика."""

    file_name: str
    sheet_name: str | None = None
    customer: str | None = None
    order_number: str | None = None
    parts: list[ImportedPartRead] = []
    total_quantity: int = 0
    total_area_sqm: Decimal = Decimal("0")
    # строки в том же виде, что принимает поле «Размеры списком»
    size_lines: str = ""
