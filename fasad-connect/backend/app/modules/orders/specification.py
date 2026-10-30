"""Current order dimensions shared by its card, blank and cutting snapshots."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import object_session

from app.modules.audit.models import AuditLog
from app.modules.orders.models import Order


def last_positions_edit(order: Order) -> datetime | None:
    db = object_session(order)
    if db is None:
        return None
    return db.scalar(select(AuditLog.created_at).where(
        AuditLog.entity_type == "order", AuditLog.entity_id == str(order.id),
        AuditLog.action == "replace_order_positions",
    ).order_by(AuditLog.created_at.desc()).limit(1))


def current_parts(order: Order) -> list[dict] | None:
    # An explicitly cleared estimate must stay empty. Never resurrect lead rows,
    # including those belonging to the parent of an additional order.
    if not order.positions and not order.parent_order_id and last_positions_edit(order) is None:
        return None
    return [dict(
        width=float(row.width), height=float(row.height), quantity=int(row.quantity),
        material=row.color or "", thickness=str(row.thickness or ""),
        milling=row.milling or "", article=row.article or "",
    ) for row in order.positions
        if row.width and row.height and row.quantity > 0]


def current_information(order: Order, parts: list[dict]) -> str:
    client = order.client
    payload = order.source_lead.parsed_payload_json or {} if order.source_lead else {}
    raw = payload.get("raw_payload") or {}
    lines = [f"Клиент: {client.full_name}"] if client else []
    for label, value in (("Организация", client.organization if client else None),
                         ("Телефон", client.phone if client else None),
                         ("Email", client.email if client else None),
                         ("Адрес", payload.get("address") or (client.address if client else None))):
        if value:
            lines.append(f"{label}: {value}")
    def number(value):
        return format(Decimal(str(value)), "f").rstrip("0").rstrip(".") if "." in str(value) else str(value)
    lines.append("Размеры:")
    for part in parts:
        detail = f"{number(part['width'])}x{number(part['height'])} — {part['quantity']} шт."
        if part['thickness']:
            detail += f", {number(part['thickness'])} мм"
        if part['material']:
            detail += f", {part['material']}"
        lines.append(detail)
    lines.extend([f"Всего деталей: {sum(part['quantity'] for part in parts)}",
                  f"Расчёт: {order.final_amount} ₽"])
    if isinstance(raw, dict) and "manual_note" in raw:
        note = raw.get("manual_note")
    else:
        original = order.comment or ""
        # Preserve a legacy free comment or the text following its old summary.
        tail = re.split(r"^Расчёт:[^\n]*(?:\n|$)", original, maxsplit=1, flags=re.MULTILINE)
        note = tail[-1] if len(tail) > 1 else (original if not re.search(r"^(Клиент|Размеры):", original, re.MULTILINE) else "")
    if isinstance(note, str) and note.strip():
        lines.append(note.strip())
    return "\n".join(lines)


def geometry_signature(order: Order) -> str:
    parts = current_parts(order)
    if parts is None:
        from app.modules.leads.blank_export import read_parts
        parts = read_parts(order.source_lead) if order.source_lead else []
    rows = [json.dumps([
        str(Decimal(str(p.get('width') or 0)).normalize()),
        str(Decimal(str(p.get('height') or 0)).normalize()),
        str(Decimal(str(p.get('quantity') or 0)).normalize()),
        str(Decimal(str(p.get('thickness') or 0)).normalize()),
        p.get('material') or '', p.get('milling') or '', p.get('article') or '',
    ], ensure_ascii=False) for p in parts]
    return hashlib.sha256(json.dumps(sorted(rows), ensure_ascii=False).encode()).hexdigest()


def snapshot_is_current(order: Order, snapshot: dict, created_at: datetime) -> bool:
    signature = snapshot.get("specification_signature")
    if signature is not None:
        return signature == geometry_signature(order)
    edited = last_positions_edit(order)
    if edited is None:
        return True
    def utc(value):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return utc(created_at) >= utc(edited)
