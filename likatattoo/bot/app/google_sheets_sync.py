from __future__ import annotations

import csv
import io
import json
import re
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"

DEFAULT_CALCULATOR_RULES = {
    "sizeMultipliers": {
        "xs": 0.9,
        "s": 1.0,
        "m": 1.12,
        "l": 1.24,
        "xl": 1.38,
    },
    "complexityMultipliers": {
        "basic": 0.95,
        "medium": 1.05,
        "high": 1.16,
        "max": 1.3,
    },
    "extraHourPrice": 220,
    "colorStepPrice": 95,
}

DEFAULT_STYLE_ESTIMATES = {
    "lettering": {"label": "Надпись", "baseMin": 3500, "baseMax": 6000},
    "minimal": {"label": "Минимализм", "baseMin": 3500, "baseMax": 5500},
    "graphics": {"label": "Графика", "baseMin": 5000, "baseMax": 8000},
    "color": {"label": "Цвет и акценты", "baseMin": 6000, "baseMax": 10000},
    "cover": {"label": "Обновление / перекрытие", "baseMin": 7000, "baseMax": 12000},
}

CONSUMABLE_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("наименование", "название", "расходник", "позиция", "item", "name"),
    "price": ("цена", "стоимость", "price", "rub", "руб"),
    "category": ("категория", "category", "группа"),
    "unit": ("ед", "единица", "unit", "едизм", "единицаизмерения"),
    "base_qty": ("колво", "количество", "qty", "quantity", "базаколво", "baseqty"),
    "notes": ("комментарий", "примечание", "note", "notes", "описание"),
}


@dataclass(frozen=True)
class GoogleSheetsSettings:
    spreadsheet_id: str
    consumables_range: str
    booking_range: str
    service_account_file: str
    service_account_json: str
    published_csv_url: str

    @property
    def api_ready(self) -> bool:
        return bool(
            self.spreadsheet_id
            and self.booking_range
            and (self.service_account_file or self.service_account_json)
        )

    @property
    def consumables_ready(self) -> bool:
        return bool(self.published_csv_url) or bool(
            self.spreadsheet_id
            and self.consumables_range
            and (self.service_account_file or self.service_account_json)
        )


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]+", "", (value or "").strip().lower())


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zа-я0-9]+", "-", (value or "").strip().lower())
    return text.strip("-") or "item"


def _parse_decimal(value: str, *, default: float) -> float:
    text = (value or "").strip().replace(" ", "").replace(",", ".")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _parse_money(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    normalized = text.replace(" ", "").replace("\xa0", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if match is None:
        return None
    return int(round(float(match.group(0))))


def _match_headers(headers: Sequence[str]) -> dict[str, int]:
    normalized = {_normalize_header(header): index for index, header in enumerate(headers)}
    result: dict[str, int] = {}
    for field_name, aliases in CONSUMABLE_HEADER_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                result[field_name] = normalized[alias]
                break
    return result


def _detect_calc_group(name: str) -> str:
    lower = name.lower()
    if "коворкин" in lower or "аренда" in lower:
        return "coworking"
    if "картридж" in lower or "игл" in lower:
        return "needle"
    if "трансфер" in lower:
        return "transfer"
    if "пленк" in lower:
        return "film"
    if "перчат" in lower:
        return "gloves"
    if "колпач" in lower:
        return "caps"
    if "краск" in lower or "пигмент" in lower:
        return "pigment"
    if "антисеп" in lower or "химия" in lower or "мыло" in lower:
        return "cleaning"
    if "вазелин" in lower or "обезбол" in lower or "баттер" in lower:
        return "care"
    return "sheet"


def _build_item_from_board_cell(text: str, *, row_index: int) -> dict[str, Any] | None:
    normalized = " ".join((text or "").split())
    if not normalized:
        return None

    lower = normalized.lower()
    matches = [
        int(round(float(match.group(1).replace(",", "."))))
        for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:р|руб|рублей)", lower)
    ]
    if not matches:
        return None

    name = normalized.split(",", 1)[0].split(" — ", 1)[0].split(" - ", 1)[0].strip()
    name = re.sub(r"\s*\d+(?:[.,]\d+)?\s*(?:р|руб|рублей).*$", "", name, flags=re.IGNORECASE)
    if "аренда коворкинга" in lower:
        name = "Аренда коворкинга"
    elif "краска" in lower:
        name = "Краска / пигмент"
    elif "тату машинка" in lower:
        name = "Тату машинка + барьерка"
    elif "перчатки" in lower:
        name = "Перчатки"
    elif "пленка заживляющая" in lower:
        name = "Пленка заживляющая"

    price = min(matches)
    return {
        "id": _slugify(name),
        "name": name,
        "category": "Коворкинг и расходники",
        "unit": "шт",
        "unit_price": price,
        "base_qty": 1.0,
        "kind": "fixed",
        "calc_group": _detect_calc_group(name),
        "notes": normalized,
        "row_index": row_index,
    }


def _parse_board_style_rows(rows: Sequence[Sequence[str]]) -> dict[str, Any]:
    seen: dict[tuple[str, int], dict[str, Any]] = {}
    for row_index, row in enumerate(rows, start=1):
        for cell in row:
            item = _build_item_from_board_cell(str(cell), row_index=row_index)
            if item is None:
                continue
            seen.setdefault((item["id"], item["unit_price"]), item)

    items = sorted(seen.values(), key=lambda item: (str(item["category"]), str(item["name"])))
    if not items:
        raise ValueError("Consumables board did not contain any priced items.")

    return {
        "version": "2026-06-05",
        "updated_at": _timestamp(),
        "source": "google-sheets-csv",
        "currency": "RUB",
        "minimum_charge": 1600,
        "rules": DEFAULT_CALCULATOR_RULES,
        "styleEstimates": DEFAULT_STYLE_ESTIMATES,
        "items": items,
    }


def default_booking_snapshot(*, reason: str = "unconfigured") -> dict[str, Any]:
    return {
        "version": "2026-06-05",
        "updated_at": _timestamp(),
        "source": reason,
        "slots": [],
        "summary": {
            "availableCount": 0,
            "bookedCount": 0,
        },
    }


def is_slot_booked_by_cell_note(cell: Mapping[str, Any] | None) -> bool:
    if not cell:
        return False
    note = cell.get("note")
    if note is None:
        return False
    return bool(str(note).strip())


def parse_consumables_rows(
    rows: Sequence[Sequence[str]],
    *,
    source: str,
    minimum_charge: int = 1600,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("Consumables sheet returned no rows.")

    headers = [str(value).strip() for value in rows[0]]
    header_map = _match_headers(headers)
    required = {"name", "price"}
    missing = required - set(header_map)
    if missing:
        return _parse_board_style_rows(rows)

    items: list[dict[str, Any]] = []
    for index, row in enumerate(rows[1:], start=1):
        name = str(row[header_map["name"]]).strip() if len(row) > header_map["name"] else ""
        if not name:
            continue
        price_text = str(row[header_map["price"]]).strip() if len(row) > header_map["price"] else ""
        price = _parse_money(price_text)
        if price is None:
            continue
        category = (
            str(row[header_map["category"]]).strip()
            if "category" in header_map and len(row) > header_map["category"]
            else "Расходники"
        )
        unit = (
            str(row[header_map["unit"]]).strip()
            if "unit" in header_map and len(row) > header_map["unit"]
            else "шт"
        )
        base_qty = (
            _parse_decimal(str(row[header_map["base_qty"]]), default=1.0)
            if "base_qty" in header_map and len(row) > header_map["base_qty"]
            else 1.0
        )
        notes = (
            str(row[header_map["notes"]]).strip()
            if "notes" in header_map and len(row) > header_map["notes"]
            else ""
        )

        items.append(
            {
                "id": _slugify(name),
                "name": name,
                "category": category or "Расходники",
                "unit": unit or "шт",
                "unit_price": price,
                "base_qty": base_qty,
                "kind": "fixed",
                "calc_group": "sheet",
                "notes": notes,
                "row_index": index + 1,
            }
        )

    if not items:
        raise ValueError("Consumables sheet did not produce any valid items.")

    return {
        "version": "2026-06-05",
        "updated_at": _timestamp(),
        "source": source,
        "currency": "RUB",
        "minimum_charge": minimum_charge,
        "rules": DEFAULT_CALCULATOR_RULES,
        "styleEstimates": DEFAULT_STYLE_ESTIMATES,
        "items": items,
    }


def build_booking_snapshot(grid_payload: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    sheets = grid_payload.get("sheets")
    if not isinstance(sheets, list) or not sheets:
        return default_booking_snapshot(reason="empty-grid")

    first_sheet = sheets[0]
    data_blocks = first_sheet.get("data")
    if not isinstance(data_blocks, list) or not data_blocks:
        return default_booking_snapshot(reason="empty-grid")

    row_data = data_blocks[0].get("rowData")
    if not isinstance(row_data, list) or not row_data:
        return default_booking_snapshot(reason="empty-grid")

    def _cell_text(cell: Any) -> str:
        if isinstance(cell, Mapping):
            return str(cell.get("formattedValue") or "").strip()
        return ""

    def _fill_forward(values: Sequence[str]) -> list[str]:
        result: list[str] = []
        current = ""
        for value in values:
            if value:
                current = value
            result.append(current)
        return result

    def _looks_like_day_headers(values: Sequence[str]) -> bool:
        known_prefixes = (
            "пн",
            "вт",
            "ср",
            "чт",
            "пт",
            "сб",
            "вс",
            "понедельник",
            "вторник",
            "среда",
            "четверг",
            "пятница",
            "суббота",
            "воскресенье",
        )
        non_empty = [value.strip().lower() for value in values if value.strip()]
        if not non_empty:
            return False
        matches = sum(1 for value in non_empty if value.startswith(known_prefixes))
        return matches >= min(2, len(non_empty))

    slots: list[dict[str, Any]] = []
    booked_count = 0
    available_count = 0

    day_headers: list[str] = []
    date_headers: list[str] = []
    resource_headers: list[str] = []

    for row in row_data:
        cells = row.get("values", []) if isinstance(row, Mapping) else []
        if not cells:
            continue

        row_label = _cell_text(cells[0])
        row_values = [_cell_text(cell) for cell in cells[1:]]
        if not row_label and not day_headers and _looks_like_day_headers(row_values):
            day_headers = _fill_forward(row_values)
            continue
        if row_label.startswith("День недели"):
            day_headers = _fill_forward(row_values)
            continue
        if row_label.startswith("Дата"):
            date_headers = _fill_forward(row_values)
            continue
        if row_label.startswith("Время"):
            resource_headers = row_values
            continue
        if not re.match(r"\d{1,2}[:.-]\d{2}", row_label):
            continue

        for column_index, cell in enumerate(cells[1:]):
            if not isinstance(cell, Mapping):
                continue
            day_label = day_headers[column_index] if column_index < len(day_headers) else ""
            date_label = date_headers[column_index] if column_index < len(date_headers) else ""
            resource_label = resource_headers[column_index] if column_index < len(resource_headers) else ""
            if not any((day_label, date_label, resource_label)):
                continue

            display_value = _cell_text(cell)
            note_text = str(cell.get("note") or "").strip()
            booked = is_slot_booked_by_cell_note(cell)
            if booked:
                booked_count += 1
            else:
                available_count += 1
            slots.append(
                {
                    "day": day_label,
                    "date": date_label,
                    "time": row_label,
                    "resource": resource_label,
                    "label": display_value,
                    "booked": booked,
                    "note": note_text if booked else "",
                }
            )

    return {
        "version": "2026-06-05",
        "updated_at": _timestamp(),
        "source": source,
        "slots": slots,
        "summary": {
            "availableCount": available_count,
            "bookedCount": booked_count,
        },
    }


def read_csv_rows(csv_url: str) -> list[list[str]]:
    with urllib.request.urlopen(csv_url, timeout=20) as response:
        content = response.read().decode("utf-8-sig")
    return list(csv.reader(io.StringIO(content)))


def _build_service_account_credentials(settings: GoogleSheetsSettings) -> Any:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.service_account import Credentials
    except ImportError as error:  # pragma: no cover - exercised in runtime docs
        raise RuntimeError(
            "google-auth is not installed. Run 'pip install -r bot/requirements.txt'."
        ) from error

    if settings.service_account_json:
        service_info = json.loads(settings.service_account_json)
        credentials = Credentials.from_service_account_info(service_info, scopes=[SHEETS_SCOPE])
    elif settings.service_account_file:
        credentials = Credentials.from_service_account_file(
            settings.service_account_file,
            scopes=[SHEETS_SCOPE],
        )
    else:
        raise RuntimeError("Google Sheets service-account credentials are not configured.")

    credentials.refresh(Request())
    return credentials


def _authorized_json_get(url: str, settings: GoogleSheetsSettings) -> dict[str, Any]:
    credentials = _build_service_account_credentials(settings)
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {credentials.token}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_consumables_rows(settings: GoogleSheetsSettings) -> list[list[str]]:
    if settings.published_csv_url:
        return read_csv_rows(settings.published_csv_url)

    if not settings.spreadsheet_id or not settings.consumables_range:
        raise RuntimeError("Consumables spreadsheet settings are incomplete.")

    encoded_range = urllib.parse.quote(settings.consumables_range, safe="")
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{settings.spreadsheet_id}/values/"
        f"{encoded_range}?majorDimension=ROWS"
    )
    payload = _authorized_json_get(url, settings)
    values = payload.get("values")
    if not isinstance(values, list):
        return []
    normalized_rows: list[list[str]] = []
    for row in values:
        if isinstance(row, list):
            normalized_rows.append([str(cell) for cell in row])
    return normalized_rows


def fetch_booking_grid(settings: GoogleSheetsSettings) -> dict[str, Any]:
    if not settings.api_ready:
        raise RuntimeError("Booking sheet note sync requires spreadsheet ID and service-account credentials.")

    fields = "sheets(properties(title),data(rowData(values(formattedValue,note))))"
    encoded_range = urllib.parse.quote(settings.booking_range, safe="")
    encoded_fields = urllib.parse.quote(fields, safe="(),")
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{settings.spreadsheet_id}"
        f"?includeGridData=true&ranges={encoded_range}&fields={encoded_fields}"
    )
    return _authorized_json_get(url, settings)


def write_json(path: Any, payload: Mapping[str, Any]) -> None:
    target = path if hasattr(path, "write_text") else None
    if target is None:
        raise TypeError("Path-like object expected.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
