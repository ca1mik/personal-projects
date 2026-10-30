from __future__ import annotations

import csv
import io
import json
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError, NotFoundError
from app.modules.audit.service import AuditService
from app.modules.cutting_export.models import Export
from app.modules.orders.models import Order
from app.modules.parts_generator.models import Part
from app.storage.factory import get_storage_backend

# Соответствие Export.format реальному media type при скачивании. XLSX сюда
# не входит: бланк заказа отдаётся отдельным эндпоинтом (leads/blank_export.py),
# этот список — только про то, что реально сохраняет CuttingExportService.
_DOWNLOAD_MEDIA_TYPES = {
    "csv": "text/csv",
    "json": "application/json",
    "svg": "image/svg+xml",
}


def _positions_csv_lines(order: Order) -> list[str]:
    """Раскрой из позиций сметы — реального пути, которым живёт почти каждый
    заказ (см. `_generated_parts_csv_lines`, зачем это отдельная ветка).

    Формат человекочитаемый, тот же, что у остальных выгрузок раскроя в
    системе (`docs/imports.md`, бланк заказа) — цвет и материал текстом, не
    непрозрачный `material_id`, который вне базы ничего не значит.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["№", "Название", "Длина", "Ширина", "Количество", "Толщина", "Материал", "Фрезеровка"]
    )
    row_no = 0
    for position in sorted(order.positions, key=lambda p: p.line_no):
        if position.width is None or position.height is None:
            # Позиции без размеров (услуги, фурнитура) не режутся — им в
            # раскрое делать нечего.
            continue
        row_no += 1
        writer.writerow(
            [
                row_no,
                position.name,
                position.width,
                position.height,
                position.quantity,
                position.thickness if position.thickness is not None else "",
                position.color or "",
                position.milling or "",
            ]
        )
    return [] if row_no == 0 else buffer.getvalue().splitlines()


def _generated_parts_csv_lines(order: Order) -> list[str]:
    """Раскрой из детально сгенерированных `Part` — путь для заказов с
    позициями каталога (`OrderItem` → `PartsGeneratorService`). На практике
    почти не используется: заказы из заявок (то есть почти все) несут смету в
    `OrderPosition`, а не в `OrderItem` — но раз этот путь уже покрыт тестом
    (`test_export_cutting`) и кем-то мог использоваться, оставляем как есть,
    просто не даём ему быть единственным."""
    lines = ["part_code,name,length,width,thickness,quantity,material_id,grain_direction"]
    for part in order.parts:
        lines.append(
            f"{part.part_code},{part.name},{part.length},{part.width},{part.thickness},{part.quantity},{part.material_id},{part.grain_direction or ''}"
        )
    return lines


class CuttingExportService:
    @staticmethod
    def export_order(db: Session, order: Order, acting_user_id: str | None = None) -> Export:
        order = (
            db.scalar(
                select(Order)
                .options(
                    selectinload(Order.parts).selectinload(Part.edges),
                    selectinload(Order.positions),
                )
                .where(Order.id == order.id)
            )
            or order
        )
        # Раньше здесь была ЕДИНСТВЕННАЯ ветка через `Part` — модель, которую
        # реально наполняет только каталог товаров (`OrderItem`), а его ни разу
        # не создаёт ни один экран фронтенда. Заказ, пришедший из заявки (то
        # есть практически любой реальный заказ), у `order.parts` всегда
        # пустой — кнопка «Выгрузить раскрой (CSV)» падала 500 без единого
        # шанса на успех. Смета живёт в `OrderPosition`, и раскрой теперь
        # строится из неё, если сгенерированных `Part` нет.
        lines = _generated_parts_csv_lines(order) if order.parts else _positions_csv_lines(order)
        if not lines:
            raise AppError(
                "В заказе нет позиций с размерами — раскрой строить не из чего", status_code=400
            )

        storage = get_storage_backend()
        version = (
            db.scalar(select(func.count()).select_from(Export).where(Export.order_id == order.id))
            or 0
        ) + 1
        file_name = f"cutting-{order.order_number}-v{version}.csv"
        file_path = storage.save_text(f"exports/{order.id}/{file_name}", "\n".join(lines))
        export = Export(
            order_id=order.id,
            export_type="cutting",
            format="csv",
            file_name=file_name,
            file_path=file_path,
            version=version,
            created_by=acting_user_id,
        )
        db.add(export)
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="export_cutting",
            user_id=acting_user_id,
            new_value={"file_name": file_name, "version": version},
        )
        db.commit()
        db.refresh(export)
        return export

    @staticmethod
    def list_for_order(db: Session, order_id: uuid.UUID) -> list[Export]:
        return db.scalars(
            select(Export).where(Export.order_id == order_id).order_by(Export.created_at.desc())
        ).all()

    @staticmethod
    def get_download(
        db: Session, order_id: uuid.UUID, export_id: uuid.UUID
    ) -> tuple[bytes, str, str]:
        """(содержимое, media_type, имя файла) для скачивания.

        Раньше список «Экспорты» на карточке заказа печатал файлы просто
        текстом (`file_name`/`file_path`) без единой ссылки — ни CSV раскроя,
        ни сохранённую раскладку нельзя было реально забрать, только увидеть
        путь на диске сервера, бесполезный без доступа к нему.

        Для сохранённой раскладки (`cutting_layout`, JSON-снимок для
        повторного редактирования на экране) отдаём не сам JSON, а
        сохранённую вместе с ним SVG-карту раскроя (`preview_svg_path`) —
        именно её открывают и печатают, а JSON человеку смотреть незачем.
        """
        export = db.scalar(
            select(Export).where(Export.id == export_id, Export.order_id == order_id)
        )
        if not export:
            raise NotFoundError("Export not found")

        storage = get_storage_backend()
        if export.export_type == "cutting_layout" and export.format == "json":
            try:
                snapshot = json.loads(storage.read_bytes(export.file_path))
            except (OSError, ValueError):
                snapshot = {}
            svg_path = snapshot.get("preview_svg_path") if isinstance(snapshot, dict) else None
            if svg_path:
                return storage.read_bytes(svg_path), "image/svg+xml", Path(svg_path).name

        media_type = _DOWNLOAD_MEDIA_TYPES.get(export.format, "application/octet-stream")
        return storage.read_bytes(export.file_path), media_type, export.file_name
