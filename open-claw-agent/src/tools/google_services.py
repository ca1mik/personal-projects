"""
Google integrations (Calendar, Docs notes, Sheets memory).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


# Moscow UTC+3 fixed offset (avoid tzdata dependency on Windows).
DEFAULT_TZ = timezone(timedelta(hours=3))


def _dt_from_event_start(item: dict) -> datetime:
    start = item.get("start", {})
    if "dateTime" in start:
        raw = str(start["dateTime"]).replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=DEFAULT_TZ)
        return dt.astimezone(DEFAULT_TZ)
    # all-day events
    date_raw = start.get("date")
    if date_raw:
        return datetime.fromisoformat(f"{date_raw}T00:00:00").replace(tzinfo=DEFAULT_TZ)
    return datetime.now(tz=DEFAULT_TZ)


def _dt_from_event_end(item: dict, fallback_start: datetime) -> datetime:
    end = item.get("end", {})
    if "dateTime" in end:
        raw = str(end["dateTime"]).replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=DEFAULT_TZ)
        return dt.astimezone(DEFAULT_TZ)
    date_raw = end.get("date")
    if date_raw:
        return datetime.fromisoformat(f"{date_raw}T00:00:00").replace(tzinfo=DEFAULT_TZ)
    return fallback_start + timedelta(hours=1)


class GoogleCalendarService:
    def __init__(self, credentials_path: Path):
        self.credentials_path = credentials_path
        self.calendar_id = "primary"
        self.service = None
        if credentials_path.exists():
            self._init_service()

    def _init_service(self):
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/calendar"]
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )
            self.service = build("calendar", "v3", credentials=creds)
        except Exception:
            self.service = None

    def _parse_start(self, start_time: str | None) -> datetime:
        if not start_time:
            return datetime.now(tz=DEFAULT_TZ)
        if "T" not in start_time:
            naive = datetime.fromisoformat(f"{start_time}T14:00:00")
            return naive.replace(tzinfo=DEFAULT_TZ)
        cleaned = start_time.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=DEFAULT_TZ)
        return dt.astimezone(DEFAULT_TZ)

    def add_event(
        self,
        title: str,
        description: str = "",
        start_time: str | None = None,
        duration_hours: int = 1,
    ) -> tuple[bool, str]:
        if not self.service:
            return False, "Google Calendar is not initialized"
        try:
            start_dt = self._parse_start(start_time)
            end_dt = start_dt + timedelta(hours=duration_hours)
            event = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Moscow"},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Moscow"},
            }
            created = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
            link = created.get("htmlLink", "")
            return True, (
                f"Event created: {title}\n"
                f"Start: {start_dt.strftime('%Y-%m-%d %H:%M')}\n"
                f"Link: {link}"
            )
        except Exception as exc:
            return False, f"Google Calendar error: {exc}"

    def list_events_raw(
        self,
        days_ahead: int = 7,
        *,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
        max_results: int = 50,
    ) -> tuple[bool, list[dict] | str]:
        if not self.service:
            return False, "Google Calendar is not initialized"
        try:
            min_dt = time_min or datetime.now(tz=DEFAULT_TZ)
            max_dt = time_max or (min_dt + timedelta(days=days_ahead))
            payload = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=min_dt.isoformat(),
                timeMax=max_dt.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            events = payload.get("items", [])
            return True, events
        except Exception as exc:
            return False, f"Google Calendar list error: {exc}"

    def list_events(self, days_ahead: int = 7) -> tuple[bool, str]:
        ok, result = self.list_events_raw(days_ahead=days_ahead)
        if not ok:
            return False, str(result)
        events = result if isinstance(result, list) else []
        if not events:
            return True, f"No events for next {days_ahead} day(s)"
        lines = [f"Upcoming events ({days_ahead} days):"]
        for item in events:
            start_dt = _dt_from_event_start(item)
            lines.append(f"- {item.get('summary', 'Untitled')} ({start_dt.strftime('%Y-%m-%d %H:%M')})")
        return True, "\n".join(lines)

    def find_free_slots(
        self,
        date_str: str | None = None,
        *,
        duration_minutes: int = 60,
        work_start_hour: int = 9,
        work_end_hour: int = 22,
        max_slots: int = 6,
    ) -> tuple[bool, str, list[tuple[datetime, datetime]]]:
        if not self.service:
            return False, "Google Calendar is not initialized", []
        try:
            day = (
                datetime.fromisoformat(date_str).date()
                if date_str
                else datetime.now(tz=DEFAULT_TZ).date()
            )
            day_start = datetime(day.year, day.month, day.day, work_start_hour, 0, tzinfo=DEFAULT_TZ)
            day_end = datetime(day.year, day.month, day.day, work_end_hour, 0, tzinfo=DEFAULT_TZ)
            ok, result = self.list_events_raw(
                time_min=day_start,
                time_max=day_end,
                max_results=100,
            )
            if not ok:
                return False, str(result), []
            events = result if isinstance(result, list) else []

            busy: list[tuple[datetime, datetime]] = []
            for item in events:
                start_dt = _dt_from_event_start(item)
                end_dt = _dt_from_event_end(item, start_dt)
                if end_dt <= day_start or start_dt >= day_end:
                    continue
                busy.append((max(start_dt, day_start), min(end_dt, day_end)))
            busy.sort(key=lambda x: x[0])

            merged: list[tuple[datetime, datetime]] = []
            for interval in busy:
                if not merged:
                    merged.append(interval)
                    continue
                prev_start, prev_end = merged[-1]
                cur_start, cur_end = interval
                if cur_start <= prev_end:
                    merged[-1] = (prev_start, max(prev_end, cur_end))
                else:
                    merged.append(interval)

            slot_len = timedelta(minutes=max(15, duration_minutes))
            cursor = day_start
            slots: list[tuple[datetime, datetime]] = []
            for busy_start, busy_end in merged:
                while cursor + slot_len <= busy_start:
                    slots.append((cursor, cursor + slot_len))
                    if len(slots) >= max_slots:
                        break
                    cursor += slot_len
                if len(slots) >= max_slots:
                    break
                cursor = max(cursor, busy_end)
            while len(slots) < max_slots and cursor + slot_len <= day_end:
                slots.append((cursor, cursor + slot_len))
                cursor += slot_len

            if not slots:
                return True, "No free slots found in working window.", []

            lines = [f"Free slots on {day.isoformat()} ({duration_minutes} min):"]
            for start_dt, end_dt in slots:
                lines.append(f"- {start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}")
            return True, "\n".join(lines), slots
        except Exception as exc:
            return False, f"Google Calendar slot search error: {exc}", []


class GoogleNotesService:
    def __init__(self, credentials_path: Path, folder_id: str | None = None):
        self.credentials_path = credentials_path
        self.folder_id = folder_id
        self.service_docs = None
        self.service_drive = None
        if credentials_path.exists():
            self._init_service()

    def _init_service(self):
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            scopes = [
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )
            self.service_docs = build("docs", "v1", credentials=creds)
            self.service_drive = build("drive", "v3", credentials=creds)
        except Exception:
            self.service_docs = None
            self.service_drive = None

    def create_note(self, title: str, content: str) -> tuple[bool, str]:
        if not self.service_docs or not self.service_drive:
            return False, "Google Docs is not initialized"
        try:
            body = {"title": title, "mimeType": "application/vnd.google-apps.document"}
            if self.folder_id:
                body["parents"] = [self.folder_id]
            file_obj = self.service_drive.files().create(body=body, fields="id, webViewLink").execute()
            doc_id = file_obj.get("id")
            self.service_docs.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": [{"insertText": {"text": content, "location": {"index": 1}}}]},
            ).execute()
            return True, f"Note created: {file_obj.get('webViewLink', '')}"
        except Exception as exc:
            return False, f"Google note create error: {exc}"

    def get_or_create_notes_folder(self) -> Optional[str]:
        if not self.service_drive:
            return None
        try:
            results = self.service_drive.files().list(
                q="name='OpenClawNotes' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces="drive",
                fields="files(id, name)",
                pageSize=1,
            ).execute()
            files = results.get("files", [])
            if files:
                return files[0]["id"]
            folder = self.service_drive.files().create(
                body={"name": "OpenClawNotes", "mimeType": "application/vnd.google-apps.folder"},
                fields="id",
            ).execute()
            return folder.get("id")
        except Exception:
            return None


class GoogleSheetsService:
    def __init__(self, credentials_path: Path, spreadsheet_id: str):
        self.credentials_path = credentials_path
        self.spreadsheet_id = (spreadsheet_id or "").strip()
        self.service = None
        if self.credentials_path.exists() and self.spreadsheet_id:
            self._init_service()

    def _init_service(self):
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )
            self.service = build("sheets", "v4", credentials=creds)
        except Exception:
            self.service = None

    def append_rows(self, sheet_name: str, rows: list[list[str]]) -> tuple[bool, str]:
        if not self.service:
            return False, "Google Sheets is not initialized"
        if not rows:
            return True, "No rows to append"
        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            ).execute()
            return True, f"Rows appended to {sheet_name}"
        except Exception as exc:
            return False, f"Google Sheets append error: {exc}"

    def append_memory_fact(
        self,
        *,
        user_id: int,
        chat_id: int,
        category: str,
        key: str,
        value: str,
        source: str,
        created_at: str | None = None,
    ) -> tuple[bool, str]:
        ts = created_at or datetime.now(tz=DEFAULT_TZ).isoformat()
        row = [ts, str(user_id), str(chat_id), category, key, value, source]
        return self.append_rows("memory", [row])

    def append_research_note(
        self,
        *,
        topic: str,
        summary: str,
        sources: list[str] | None = None,
        created_at: str | None = None,
    ) -> tuple[bool, str]:
        ts = created_at or datetime.now(tz=DEFAULT_TZ).isoformat()
        row = [ts, topic, summary[:1000], "\n".join(sources or [])[:2000]]
        return self.append_rows("research", [row])

