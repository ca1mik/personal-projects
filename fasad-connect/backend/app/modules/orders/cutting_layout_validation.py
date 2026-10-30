"""Server-side geometry checks for saved cutting layouts."""

from __future__ import annotations

import math

from app.core.exceptions import AppError
from app.modules.orders.schemas import OrderCuttingLayoutSaveRequest


def _number(value: object, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise AppError(f"{label}: требуется число", 422)
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AppError(f"{label}: требуется число", 422) from exc
    if not math.isfinite(number) or (positive and number <= 0) or (not positive and number < 0):
        raise AppError(f"{label}: недопустимое значение", 422)
    return number


def validate_cutting_layout(payload: OrderCuttingLayoutSaveRequest, *, no_rotation: bool = False) -> None:
    settings = payload.sheet_settings
    if len(payload.sheets) > 1000:
        raise AppError("Слишком много листов раскроя", 422)
    default_width = settings.get("sheetWidth")
    default_height = settings.get("sheetHeight")
    seen_units: set[str] = set()
    placed_count = 0
    for sheet_index, sheet in enumerate(payload.sheets, 1):
        placements = sheet.get("placements")
        if not isinstance(placements, list):
            raise AppError(f"Лист {sheet_index}: нет списка деталей", 422)
        if not placements:
            continue
        width = _number(sheet.get("width", default_width), f"Лист {sheet_index}: ширина", positive=True)
        height = _number(sheet.get("height", default_height), f"Лист {sheet_index}: высота", positive=True)
        left = _number(sheet.get("marginX", settings.get("marginX", 0)), "Левый отступ")
        top = _number(sheet.get("marginY", settings.get("marginY", 0)), "Верхний отступ")
        right_margin = _number(settings.get("marginRight", left), "Правый отступ")
        bottom_margin = _number(settings.get("marginBottom", top), "Нижний отступ")
        right, bottom = width - right_margin, height - bottom_margin
        if right <= left or bottom <= top:
            raise AppError(f"Лист {sheet_index}: рабочая область пуста", 422)
        boxes: list[tuple[float, float, float, float, float, float]] = []
        for part_index, part in enumerate(placements, 1):
            label = f"Лист {sheet_index}, деталь {part_index}"
            if not isinstance(part, dict):
                raise AppError(f"{label}: неверный формат", 422)
            x = _number(part.get("x"), f"{label}: X")
            y = _number(part.get("y"), f"{label}: Y")
            part_width = _number(part.get("width"), f"{label}: ширина", positive=True)
            part_height = _number(part.get("height"), f"{label}: высота", positive=True)
            gap_x = _number(part.get("gapX", settings.get("defaultGapX", 0)), f"{label}: зазор X")
            gap_y = _number(part.get("gapY", settings.get("defaultGapY", 0)), f"{label}: зазор Y")
            if x < left - 1e-6 or y < top - 1e-6 or x + part_width > right + 1e-6 or y + part_height > bottom + 1e-6:
                raise AppError(f"{label}: деталь выходит за рабочую область", 422)
            rotated = part.get("rotated", False)
            if not isinstance(rotated, bool):
                raise AppError(f"{label}: неверный признак поворота", 422)
            if no_rotation and rotated:
                raise AppError(f"{label}: поворот запрещён для этого заказа", 422)
            unit_id = part.get("unitId")
            if unit_id is not None:
                unit_id = str(unit_id)
                if unit_id in seen_units:
                    raise AppError(f"{label}: деталь размещена дважды", 422)
                seen_units.add(unit_id)
            for other_x, other_y, other_w, other_h, other_gap_x, other_gap_y in boxes:
                if (x < other_x + other_w + max(gap_x, other_gap_x) - 1e-6
                    and other_x < x + part_width + max(gap_x, other_gap_x) - 1e-6
                    and y < other_y + other_h + max(gap_y, other_gap_y) - 1e-6
                    and other_y < y + part_height + max(gap_y, other_gap_y) - 1e-6):
                    raise AppError(f"{label}: детали пересекаются или нарушен зазор", 422)
            boxes.append((x, y, part_width, part_height, gap_x, gap_y))
            placed_count += 1
    stats = payload.stats
    for key, actual in (("sheetCount", len(payload.sheets)), ("placedCount", placed_count)):
        if key in stats and _number(stats[key], key) != actual:
            raise AppError(f"Статистика раскроя: {key} не совпадает с размещением", 422)
    if "requestedCount" in stats and "unplacedCount" in stats:
        requested = _number(stats["requestedCount"], "requestedCount")
        unplaced = _number(stats["unplacedCount"], "unplacedCount")
        if requested != placed_count + unplaced:
            raise AppError("Статистика раскроя: количество деталей не совпадает", 422)
    if payload.parts and placed_count == 0 and _number(stats.get("unplacedCount", 0), "unplacedCount") == 0:
        raise AppError("В раскрое есть детали, но ни одна не размещена", 422)
