from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOT_ROOT = ROOT / "bot"
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from app.config import load_config  # noqa: E402
from app.google_sheets_sync import (  # noqa: E402
    GoogleSheetsSettings,
    build_booking_snapshot,
    default_booking_snapshot,
    fetch_booking_grid,
    fetch_consumables_rows,
    parse_consumables_rows,
    write_json,
)


SITE_DATA_DIR = ROOT / "site" / "data"
CONSUMABLES_JSON = SITE_DATA_DIR / "consumables.json"
BOOKING_JSON = SITE_DATA_DIR / "booking-snapshot.json"
SPREADSHEET_ID_PATTERN = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh public site JSON data from Google Sheets with safe local fallback."
    )
    parser.add_argument(
        "--spreadsheet-url",
        help="Public Google Sheets URL. If passed, the script auto-builds the consumables CSV export URL.",
    )
    parser.add_argument(
        "--consumables-gid",
        default="0",
        help="Sheet gid for published consumables CSV when --spreadsheet-url is used. Defaults to 0.",
    )
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Do not fail if Google Sheets is unavailable; keep current fallback JSON instead.",
    )
    return parser.parse_args()


def _load_existing(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _settings_from_config() -> GoogleSheetsSettings:
    cfg = load_config()
    return GoogleSheetsSettings(
        spreadsheet_id=cfg.google_sheets_spreadsheet_id,
        consumables_range=cfg.google_sheets_consumables_range,
        booking_range=cfg.google_sheets_booking_range,
        service_account_file=cfg.google_sheets_service_account_file,
        service_account_json=cfg.google_sheets_service_account_json,
        published_csv_url=cfg.google_sheets_published_csv_url,
    )


def _spreadsheet_id_from_url(raw_url: str) -> str:
    match = SPREADSHEET_ID_PATTERN.search(raw_url or "")
    if match is None:
        raise ValueError("Could not parse spreadsheet ID from the provided Google Sheets URL.")
    return match.group(1)


def _settings_from_args(args: argparse.Namespace) -> GoogleSheetsSettings:
    settings = _settings_from_config()
    if not args.spreadsheet_url:
        return settings

    spreadsheet_id = _spreadsheet_id_from_url(args.spreadsheet_url)
    published_csv_url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export"
        f"?format=csv&gid={args.consumables_gid}"
    )
    return GoogleSheetsSettings(
        spreadsheet_id=spreadsheet_id,
        consumables_range=settings.consumables_range,
        booking_range=settings.booking_range,
        service_account_file=settings.service_account_file,
        service_account_json=settings.service_account_json,
        published_csv_url=published_csv_url,
    )


def main() -> int:
    args = parse_args()
    settings = _settings_from_args(args)

    existing_consumables = _load_existing(CONSUMABLES_JSON)
    existing_booking = _load_existing(BOOKING_JSON)

    try:
        if settings.consumables_ready:
            consumables_rows = fetch_consumables_rows(settings)
            consumables_payload = parse_consumables_rows(
                consumables_rows,
                source="google-sheets" if not settings.published_csv_url else "google-sheets-csv",
            )
            write_json(CONSUMABLES_JSON, consumables_payload)
            print(f"Updated {CONSUMABLES_JSON}")
        elif existing_consumables is None:
            raise RuntimeError("Consumables sync is not configured and no local fallback JSON exists.")

        if settings.api_ready:
            booking_grid = fetch_booking_grid(settings)
            booking_payload = build_booking_snapshot(booking_grid, source="google-sheets-notes")
            write_json(BOOKING_JSON, booking_payload)
            print(f"Updated {BOOKING_JSON}")
        elif existing_booking is None:
            write_json(BOOKING_JSON, default_booking_snapshot(reason="unconfigured"))
            print(f"Created fallback {BOOKING_JSON}")
    except Exception as error:  # noqa: BLE001
        if not args.allow_fallback:
            raise
        if existing_consumables is not None:
            write_json(CONSUMABLES_JSON, existing_consumables)
        if existing_booking is not None:
            write_json(BOOKING_JSON, existing_booking)
        print(f"Google Sheets sync fallback used: {error}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
