"""Automatic film cutting snapshot for PVC orders' dimensional positions."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.orders.models import OrderPosition
from app.modules.orders.schemas import OrderCuttingLayoutSaveRequest
from app.modules.users.models import User


SHEET_WIDTH = 3100
SHEET_HEIGHT = 1300
LEFT = 150
RIGHT = 200
TOP = BOTTOM = GAP = 65
WORK_WIDTH = SHEET_WIDTH - LEFT - RIGHT
WORK_HEIGHT = SHEET_HEIGHT - TOP - BOTTOM


def _number(value: Decimal | None) -> float:
    return float(value or 0)


def build_film_layout(positions: list[OrderPosition]) -> OrderCuttingLayoutSaveRequest | None:
    """Lay out each color separately using deterministic shelves and 65 mm gaps."""
    groups = defaultdict(list)
    parts = []
    for position in positions:
        width, height = _number(position.width), _number(position.height)
        qty = int(_number(position.quantity))
        if width <= 0 or height <= 0 or qty <= 0:
            continue
        color = (position.color or "Без цвета").strip() or "Без цвета"
        for number in range(qty):
            unit = {
                "id": f"{position.id}-{number + 1}",
                "sourceId": str(position.id),
                "sourceNumber": position.line_no,
                "sourceName": position.name,
                "pattern": color,
                "width": width,
                "height": height,
                "milling": position.milling,
                "thickness": _number(position.thickness) or None,
            }
            parts.append(unit)
            groups[color].append(unit)
    if not parts:
        return None

    sheets = []
    unplaced = []
    ordered_mm = 0
    for color, units in groups.items():
        local = []
        for unit in sorted(units, key=lambda item: (-item["width"], -item["height"], item["id"])):
            w, h = unit["width"], unit["height"]
            if w > WORK_WIDTH or h > WORK_HEIGHT:
                unplaced.append(unit)
                continue
            target = None
            for sheet in local:
                x, y, row_h = sheet["_x"], sheet["_y"], sheet["_row_h"]
                if x + w <= LEFT + WORK_WIDTH and y + h <= TOP + WORK_HEIGHT:
                    target = sheet
                    break
                if TOP + WORK_HEIGHT >= y + row_h + GAP + h:
                    target = sheet
                    sheet["_x"] = LEFT
                    sheet["_y"] = y + row_h + GAP
                    sheet["_row_h"] = 0
                    break
            if target is None:
                target = {
                    "index": len(sheets) + 1,
                    "globalIndex": len(sheets) + 1,
                    "localIndex": len(local) + 1,
                    "pattern": color,
                    "materialCode": color,
                    "width": SHEET_WIDTH,
                    "height": SHEET_HEIGHT,
                    "marginX": LEFT,
                    "marginY": TOP,
                    "workWidth": WORK_WIDTH,
                    "workHeight": WORK_HEIGHT,
                    "placements": [],
                    "_x": LEFT,
                    "_y": TOP,
                    "_row_h": 0,
                }
                sheets.append(target)
                local.append(target)
            x, y = target["_x"], target["_y"]
            target["placements"].append({
                "unitId": unit["id"],
                "sourceId": unit["sourceId"],
                "sourceNumber": unit["sourceNumber"],
                "sourceName": unit["sourceName"],
                "pattern": color,
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "footprintWidth": w,
                "footprintHeight": h,
                "gapX": GAP,
                "gapY": GAP,
                "rotated": False,
            })
            target["_x"] = x + w + GAP
            target["_row_h"] = max(target["_row_h"], h)
    for sheet in sheets:
        used = max(item["x"] + item["width"] - LEFT for item in sheet["placements"])
        sheet["usedLength"] = used
        sheet["orderedLength"] = 3100 if used >= 2500 else ceil((used + 350) / 100) * 100
        ordered_mm += sheet["orderedLength"]
        del sheet["_x"], sheet["_y"], sheet["_row_h"]
    settings = {
        "sheetWidth": SHEET_WIDTH, "sheetHeight": SHEET_HEIGHT,
        "marginX": LEFT, "marginRight": RIGHT,
        "marginY": TOP, "marginBottom": BOTTOM,
        "defaultGapX": GAP, "defaultGapY": GAP,
        "workKind": "film", "algorithm": "leftEdge",
    }
    return OrderCuttingLayoutSaveRequest(
        sheet_settings=settings,
        stats={
            "source": "automatic_film", "sheetCount": len(sheets),
            "detailCount": len(parts), "unplacedCount": len(unplaced),
            "unplaced": unplaced,
            "orderedLengthM": ordered_mm / 1000,
            "rollAreaSqm": ordered_mm * SHEET_HEIGHT / 1_000_000,
        },
        parts=parts, sheets=sheets,
        note="Автоматический раскрой плёнки для ПВХ при изменении заказа",
    )


def save_for_order(db: Session, order_id, acting_user_id) -> None:
    from app.modules.orders.service import OrderService

    order = OrderService.get_order(db, order_id)
    if not order.direction or order.direction.code != "pvc":
        return
    user = db.get(User, acting_user_id) if acting_user_id else None
    if user is None:
        return
    positions = list(db.scalars(select(OrderPosition).where(OrderPosition.order_id == order_id).order_by(OrderPosition.line_no)).all())
    payload = build_film_layout(positions)
    if payload:
        OrderService.save_cutting_layout(db, order_id, payload, user)


# Compatibility for older callers; eligibility is decided from the order direction.
build_pvc_layout = build_film_layout
