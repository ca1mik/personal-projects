from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Config

CRM_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
CRM_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
DEFAULT_CRM_TITLE = "PPDSTR CRM"
CRM_DASHBOARD_TITLE = "CRM Dashboard"
CRM_LEADS_TITLE = "CRM Leads"
CRM_STATUSES_TITLE = "CRM Statuses"
CRM_PAYMENTS_TITLE = "CRM Payments"
DEFAULT_STATUSES = (
    ("new", "Новая", "Новая заявка, еще не взята в работу"),
    ("contacted", "Связались", "Уже ответили и уточняем детали"),
    ("consultation", "Консультация", "Идет обсуждение идеи, размера и места"),
    ("waiting_reply", "Ждем ответ", "Написали клиенту и ждем ответа"),
    ("confirmed", "Подтверждена", "Дата и формат уже согласованы"),
    ("deposit", "Предоплата", "Ждем или получили предоплату"),
    ("done", "Сделано", "Сеанс завершен"),
    ("archive", "Архив", "Неактуальная или закрытая заявка"),
)


@dataclass(frozen=True)
class GoogleCrmSettings:
    project_dir: Path
    db_path: Path
    service_account_file: str
    service_account_json: str
    spreadsheet_id: str
    title: str
    owner_email: str

    @property
    def credentials_ready(self) -> bool:
        return bool(self.service_account_file or self.service_account_json)

    @property
    def spreadsheet_ready(self) -> bool:
        return bool(self.spreadsheet_id and self.credentials_ready)


def discover_service_account_file(project_dir: Path) -> str:
    candidates = sorted(
        project_dir.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("type") == "service_account" and payload.get("client_email") and payload.get("private_key"):
            return str(path)
    return ""


def _load_service_account_payload(settings: GoogleCrmSettings) -> dict[str, Any]:
    if settings.service_account_json:
        return json.loads(settings.service_account_json)
    if settings.service_account_file:
        return json.loads(Path(settings.service_account_file).read_text(encoding="utf-8"))
    raise RuntimeError("Google CRM service-account credentials are not configured.")


def _service_account_email(settings: GoogleCrmSettings) -> str:
    try:
        payload = _load_service_account_payload(settings)
        return str(payload.get("client_email", "")).strip()
    except (OSError, json.JSONDecodeError):
        return ""
    return ""


def resolve_crm_settings(cfg: Config) -> GoogleCrmSettings:
    service_account_file = cfg.google_sheets_service_account_file or discover_service_account_file(cfg.data_dir.parent.parent)
    return GoogleCrmSettings(
        project_dir=cfg.data_dir.parent.parent,
        db_path=cfg.db_path,
        service_account_file=service_account_file,
        service_account_json=cfg.google_sheets_service_account_json,
        spreadsheet_id=cfg.google_crm_spreadsheet_id,
        title=cfg.google_crm_title or DEFAULT_CRM_TITLE,
        owner_email=cfg.google_crm_owner_email,
    )


def _build_credentials(settings: GoogleCrmSettings, *, scopes: list[str]) -> Any:
    try:
        from google.oauth2.service_account import Credentials
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("google-auth is not installed. Run 'pip install -r bot/requirements.txt'.") from error

    service_info = _load_service_account_payload(settings)
    credentials = Credentials.from_service_account_info(service_info, scopes=scopes)
    return credentials


def _get_access_token(credentials: Any) -> str:
    try:
        from google.auth.transport.requests import Request
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("google-auth is not installed. Run 'pip install -r bot/requirements.txt'.") from error

    try:
        credentials.refresh(Request())
        token = str(getattr(credentials, "token", "") or "").strip()
        if token:
            return token
    except Exception as refresh_error:  # pragma: no cover - runtime fallback
        assertion = credentials._make_authorization_grant_assertion()  # noqa: SLF001
        if isinstance(assertion, bytes):
            assertion = assertion.decode("utf-8")
        token_uri = str(getattr(credentials, "_token_uri", "https://oauth2.googleapis.com/token"))  # noqa: SLF001
        payload = urllib.parse.urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": str(assertion),
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            token_uri,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                token_payload = json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Google token request failed: {error.code} {details}") from refresh_error
        access_token = str(token_payload.get("access_token", "")).strip()
        if access_token:
            return access_token
        raise RuntimeError("Google token request succeeded without access_token.") from refresh_error

    raise RuntimeError("Google credentials did not provide an access token after refresh.")


def _authorized_request(
    method: str,
    url: str,
    settings: GoogleCrmSettings,
    *,
    payload: Mapping[str, Any] | None = None,
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    credentials = _build_credentials(settings, scopes=scopes or [CRM_SHEETS_SCOPE, CRM_DRIVE_SCOPE])
    access_token = _get_access_token(credentials)
    data = None
    headers = {"Authorization": f"Bearer {access_token}"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:  # pragma: no cover - runtime handling
        details = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Google API {method.upper()} {url} failed: {error.code} {details}") from error


def _sheet_map(payload: Mapping[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for sheet in payload.get("sheets", []):
        if not isinstance(sheet, Mapping):
            continue
        properties = sheet.get("properties", {})
        if not isinstance(properties, Mapping):
            continue
        title = str(properties.get("title", "")).strip()
        sheet_id = properties.get("sheetId")
        if title and isinstance(sheet_id, int):
            result[title] = sheet_id
    return result


def _dashboard_values() -> list[list[str]]:
    return [
        ["PPDSTR CRM", "", ""],
        ["Обновлено", "=NOW()", ""],
        [],
        ["Статус", "Количество", "Что значит"],
        ["Новые", f'=COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"new")', "Новые заявки без ответа"],
        ["Связались", f'=COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"contacted")', "Уже написали и взяли в работу"],
        ["Консультация", f'=COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"consultation")', "Идет обсуждение идеи"],
        ["Ждем ответ", f'=COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"waiting_reply")', "Нужно напомнить о себе"],
        ["Подтверждены", f'=COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"confirmed")', "Дата и работа согласованы"],
        ["Предоплата", f'=COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"deposit")', "Контроль оплаты / брони"],
        ["Сделано", f'=COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"done")', "Завершенные сеансы"],
        ["Архив", f'=COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"archive")', "Неактуальные заявки"],
        [],
        ["Всего заявок", f'=COUNTA(\'{CRM_LEADS_TITLE}\'!A2:A)', ""],
        [],
        ["Конверсия", "", ""],
        ["В переговоры", f'=IFERROR(ROUND(COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"contacted")/COUNTA(\'{CRM_LEADS_TITLE}\'!A2:A)*100;1)&"%";"n/a")', ""],
        ["До предоплаты", f'=IFERROR(ROUND(COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"deposit")/COUNTA(\'{CRM_LEADS_TITLE}\'!A2:A)*100;1)&"%";"n/a")', ""],
        ["До сеанса", f'=IFERROR(ROUND(COUNTIF(\'{CRM_LEADS_TITLE}\'!B2:B;"done")/COUNTA(\'{CRM_LEADS_TITLE}\'!A2:A)*100;1)&"%";"n/a")', ""],
        [],
        ["Платежи (Payments)", "", ""],
        ["Оплачено всего", f'=IFERROR(SUMIF(\'{CRM_PAYMENTS_TITLE}\'!F2:F;"paid";\'{CRM_PAYMENTS_TITLE}\'!D2:D);0)&" ₽"', ""],
        ["Средний чек", f'=IFERROR(ROUND(SUMIF(\'{CRM_PAYMENTS_TITLE}\'!F2:F;"paid";\'{CRM_PAYMENTS_TITLE}\'!D2:D)/COUNTIF(\'{CRM_PAYMENTS_TITLE}\'!F2:F;"paid");0)&" ₽";"—")', ""],
    ]


def _statuses_values() -> list[list[str]]:
    rows = [["Код", "Название", "Описание"]]
    rows.extend([[code, title, description] for code, title, description in DEFAULT_STATUSES])
    return rows


def _lead_headers() -> list[str]:
    return [
        "ID",
        "Статус",
        "Создано",
        "Имя",
        "Username",
        "Telegram ID",
        "Контакт",
        "Идея",
        "Размер",
        "Место",
        "Когда удобно",
        "Источник",
        "Заметки",
        "Следующий шаг",
    ]


def _crm_lead_headers() -> list[str]:
    return [
        "ID",
        "Статус",
        "Создано",
        "Имя",
        "Username",
        "Telegram ID",
        "Контакт",
        "Канал связи",
        "Идея / запрос",
        "Стиль / похожая работа",
        "Размер",
        "Место",
        "Цветность",
        "Сложность",
        "Эскиз",
        "Первая татуировка",
        "Когда удобно",
        "Диапазон цены",
        "Дата сеанса",
        "Предоплата",
        "Последнее касание",
        "Следующий шаг",
        "Заметки",
        "Источник",
        # Новые поля
        "Дата обновл. статуса",
        "Дней без движения",
        "Сумма сеанса (ручная)",
        "Комментарий мастера",
    ]


def _payments_headers() -> list[str]:
    return [
        "ID",
        "Дата",
        "Канал",
        "Сумма ₽",
        "Услуга",
        "Статус",
        "user_id",
        "Invoice ID",
    ]


def _parse_booking_details(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _guess_contact_channel(contact: str) -> str:
    text = (contact or "").strip().lower()
    if not text:
        return ""
    if "vk.com" in text or text.startswith("vk") or "вк" in text:
        return "VK"
    if text.startswith("@") or "t.me/" in text or "telegram" in text:
        return "Telegram"
    if "wa.me" in text or "whatsapp" in text or text.startswith("+7") or text.startswith("8") or any(ch.isdigit() for ch in text):
        return "Телефон / WhatsApp"
    return "Свободный контакт"


def _crm_booking_row(row: tuple[Any, ...]) -> list[str]:
    details = _parse_booking_details(row[12])
    style_label = str(details.get("style_label", "")).strip()
    selected_work = str(details.get("selected_work_title", "")).strip()
    style_or_work = " · ".join(part for part in (style_label, selected_work) if part)
    color_label = str(details.get("color_label", "")).strip()
    complexity_label = str(details.get("complexity_label", "")).strip()
    has_sketch_label = str(details.get("has_sketch_label", "")).strip()
    first_tattoo_label = str(details.get("first_tattoo_label", "")).strip()
    price_range = str(details.get("calc_price_range", "")).strip()
    contact_channel = str(details.get("contact_channel", "")).strip() or _guess_contact_channel(str(row[6]))
    notes_parts = [
        str(details.get("comment", "")).strip(),
        str(details.get("calc_materials_label", "")).strip(),
        str(details.get("followup_hint", "")).strip(),
    ]
    notes = "\n".join(part for part in notes_parts if part)
    # status_updated_at is row[13] if present
    status_updated_at = str(row[13]).strip() if len(row) > 13 and row[13] else ""
    return [
        str(row[0]),   # ID
        str(row[1]),   # Статус
        str(row[2]),   # Создано
        str(row[3]),   # Имя
        str(row[4]),   # Username
        str(row[5]),   # Telegram ID
        str(row[6]),   # Контакт
        contact_channel,
        str(row[7]),   # Идея
        style_or_work,
        str(row[8]),   # Размер
        str(row[9]),   # Место
        color_label,
        complexity_label,
        has_sketch_label,
        first_tattoo_label,
        str(row[10]),  # Когда удобно
        price_range,
        "",            # Дата сеанса
        "",            # Предоплата
        "",            # Последнее касание
        "",            # Следующий шаг
        notes,
        str(row[11]) or "telegram-bot",  # Источник
        # Новые поля
        status_updated_at,   # Дата обновл. статуса
        "",                  # Дней без движения (формула проставляется вручную в Sheets)
        "",                  # Сумма сеанса (ручная)
        "",                  # Комментарий мастера
    ]



def _load_booking_rows(db_path: Path) -> list[list[str]]:
    query = """
        SELECT
            id, status, created_at, COALESCE(full_name, ''), COALESCE(username, ''),
            user_id, contact, idea, size, placement, preferred_date,
            COALESCE(source, 'telegram-bot'), COALESCE(details_json, '{}'),
            status_updated_at
        FROM booking_requests
        ORDER BY id DESC
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(query).fetchall()

    lead_rows = [_crm_lead_headers()]
    for row in rows:
        lead_rows.append(_crm_booking_row(row))
    return lead_rows


def _load_payments_rows(db_path: Path) -> list[list[str]]:
    """\u0421\u0431\u043e\u0440\u043a\u0430 \u043f\u043b\u0430\u0442\u0435\u0436\u0435\u0439 \u0438\u0437 deposits + robokassa_invoices."""
    query_deposits = """
        SELECT
            id, created_at, 'Telegram Stars' AS channel,
            amount_rub, offer_title, status, user_id, id AS invoice_id
        FROM deposits
    """
    query_robokassa = """
        SELECT
            invoice_id, COALESCE(paid_at, created_at) AS date,
            'Robokassa' AS channel,
            amount_rub, offer_title, status, user_id, invoice_id
        FROM robokassa_invoices
    """
    with sqlite3.connect(db_path) as conn:
        deposits = conn.execute(query_deposits).fetchall()
        robokassa = conn.execute(query_robokassa).fetchall()

    all_rows = sorted(list(deposits) + list(robokassa), key=lambda r: str(r[1]), reverse=True)
    payment_rows = [_payments_headers()]
    for row in all_rows:
        payment_rows.append([str(c) for c in row])
    return payment_rows


def _batch_update_values(spreadsheet_id: str, settings: GoogleCrmSettings, data: list[dict[str, Any]]) -> None:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchUpdate"
    payload = {
        "valueInputOption": "USER_ENTERED",
        "data": data,
    }
    _authorized_request("POST", url, settings, payload=payload)


def _format_crm_sheets(spreadsheet_id: str, settings: GoogleCrmSettings, sheets: dict[str, int]) -> None:
    requests: list[dict[str, Any]] = []
    for title in (CRM_DASHBOARD_TITLE, CRM_LEADS_TITLE, CRM_STATUSES_TITLE):
        sheet_id = sheets.get(title)
        if sheet_id is None:
            continue
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            }
        )
        requests.append(
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.43, "green": 0.12, "blue": 0.12},
                            "textFormat": {
                                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                                "bold": True,
                            },
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            }
        )

    leads_id = sheets.get(CRM_LEADS_TITLE)
    if leads_id is not None:
        requests.extend(
            [
                {
                    "setBasicFilter": {
                        "filter": {
                            "range": {
                                "sheetId": leads_id,
                                "startRowIndex": 0,
                                "startColumnIndex": 0,
                                "endColumnIndex": len(_crm_lead_headers()),
                            }
                        }
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": leads_id,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": len(_crm_lead_headers()),
                        },
                        "properties": {"pixelSize": 160},
                        "fields": "pixelSize",
                    }
                },
            ]
        )

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate"
    _authorized_request("POST", url, settings, payload={"requests": requests})


def _fetch_spreadsheet(spreadsheet_id: str, settings: GoogleCrmSettings) -> dict[str, Any]:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}?fields=spreadsheetId,spreadsheetUrl,sheets(properties(sheetId,title))"
    return _authorized_request("GET", url, settings)


def _ensure_crm_sheets(spreadsheet_id: str, settings: GoogleCrmSettings) -> dict[str, str]:
    existing = _fetch_spreadsheet(spreadsheet_id, settings)
    sheets = _sheet_map(existing)
    missing_titles = [
        title
        for title in (CRM_DASHBOARD_TITLE, CRM_LEADS_TITLE, CRM_STATUSES_TITLE, CRM_PAYMENTS_TITLE)
        if title not in sheets
    ]
    if missing_titles:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate"
        requests = [{"addSheet": {"properties": {"title": title}}} for title in missing_titles]
        updated = _authorized_request("POST", url, settings, payload={"requests": requests})
        sheets = _sheet_map(updated) or _sheet_map(_fetch_spreadsheet(spreadsheet_id, settings))
    _format_crm_sheets(spreadsheet_id, settings, sheets)
    _batch_update_values(
        spreadsheet_id,
        settings,
        [
            {"range": f"{CRM_DASHBOARD_TITLE}!A1", "values": _dashboard_values()},
            {"range": f"{CRM_STATUSES_TITLE}!A1", "values": _statuses_values()},
            {"range": f"{CRM_LEADS_TITLE}!A1", "values": _load_booking_rows(settings.db_path)},
            {"range": f"{CRM_PAYMENTS_TITLE}!A1", "values": _load_payments_rows(settings.db_path)},
        ],
    )
    return {
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": str(existing.get("spreadsheetUrl") or f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"),
    }


def share_spreadsheet(spreadsheet_id: str, settings: GoogleCrmSettings) -> bool:
    if not settings.owner_email:
        return False
    url = (
        f"https://www.googleapis.com/drive/v3/files/{spreadsheet_id}/permissions"
        "?sendNotificationEmail=false"
    )
    payload = {
        "type": "user",
        "role": "writer",
        "emailAddress": settings.owner_email,
    }
    _authorized_request("POST", url, settings, payload=payload, scopes=[CRM_SHEETS_SCOPE, CRM_DRIVE_SCOPE])
    return True


def create_crm_spreadsheet(settings: GoogleCrmSettings) -> dict[str, str]:
    if not settings.credentials_ready:
        raise RuntimeError("CRM creation requires a configured Google service account.")

    payload = {
        "properties": {"title": settings.title or DEFAULT_CRM_TITLE},
        "sheets": [
            {"properties": {"title": CRM_DASHBOARD_TITLE}},
            {"properties": {"title": CRM_LEADS_TITLE}},
            {"properties": {"title": CRM_STATUSES_TITLE}},
        ],
    }
    created = _authorized_request("POST", "https://sheets.googleapis.com/v4/spreadsheets", settings, payload=payload)
    spreadsheet_id = str(created["spreadsheetId"])
    spreadsheet_url = str(created.get("spreadsheetUrl") or f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
    sheets = _sheet_map(created)
    _format_crm_sheets(spreadsheet_id, settings, sheets)
    _batch_update_values(
        spreadsheet_id,
        settings,
        [
            {"range": f"{CRM_DASHBOARD_TITLE}!A1", "values": _dashboard_values()},
            {"range": f"{CRM_STATUSES_TITLE}!A1", "values": _statuses_values()},
            {"range": f"{CRM_LEADS_TITLE}!A1", "values": _load_booking_rows(settings.db_path)},
            {"range": f"{CRM_PAYMENTS_TITLE}!A1", "values": _load_payments_rows(settings.db_path)},
        ],
    )
    shared = False
    try:
        shared = share_spreadsheet(spreadsheet_id, settings)
    except RuntimeError:
        shared = False
    return {
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": spreadsheet_url,
        "shared": "yes" if shared else "no",
    }


def sync_crm_spreadsheet(settings: GoogleCrmSettings) -> dict[str, str]:
    if not settings.spreadsheet_ready:
        raise RuntimeError("CRM sync requires GOOGLE_CRM_SPREADSHEET_ID and Google service-account credentials.")

    spreadsheet_id = settings.spreadsheet_id
    result = _ensure_crm_sheets(spreadsheet_id, settings)
    return {
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": result["spreadsheet_url"],
        "rows": str(max(0, len(_load_booking_rows(settings.db_path)) - 1)),
    }


def provision_crm_workspace(settings: GoogleCrmSettings, *, fallback_spreadsheet_id: str = "") -> dict[str, str]:
    try:
        return create_crm_spreadsheet(settings)
    except RuntimeError as error:
        if "PERMISSION_DENIED" not in str(error) and "403" not in str(error):
            raise
        if not fallback_spreadsheet_id:
            service_email = _service_account_email(settings)
            hint = (
                f" Share the target Google Sheet or a Drive folder with {service_email} as Editor."
                if service_email
                else ""
            )
            raise RuntimeError(f"{error}.{hint}") from error
        try:
            result = _ensure_crm_sheets(fallback_spreadsheet_id, settings)
        except RuntimeError as fallback_error:
            service_email = _service_account_email(settings)
            hint = (
                f" Share the spreadsheet {fallback_spreadsheet_id} with {service_email} as Editor."
                if service_email
                else f" Share the spreadsheet {fallback_spreadsheet_id} with the service account as Editor."
            )
            raise RuntimeError(f"{fallback_error}. {hint}") from fallback_error
        return {
            "spreadsheet_id": result["spreadsheet_id"],
            "spreadsheet_url": result["spreadsheet_url"],
            "shared": "existing-sheet",
        }
