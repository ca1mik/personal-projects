from __future__ import annotations

from app.google_sheets_sync import (
    build_booking_snapshot,
    is_slot_booked_by_cell_note,
    parse_consumables_rows,
)


def test_is_slot_booked_by_cell_note_uses_note_only() -> None:
    assert is_slot_booked_by_cell_note({"formattedValue": "12:00", "note": "Клиент подтвержден"}) is True
    assert is_slot_booked_by_cell_note({"formattedValue": "12:00", "note": ""}) is False
    assert is_slot_booked_by_cell_note({"formattedValue": "занято"}) is False
    assert is_slot_booked_by_cell_note(None) is False


def test_parse_consumables_rows_builds_frontend_payload() -> None:
    rows = [
        ["Наименование", "Цена", "Категория", "Ед", "Кол-во", "Комментарий"],
        ["Игла RL", "190", "Иглы", "шт", "1", "Базовая игла"],
        ["Пленка", "120", "Защита", "шт", "1", ""],
    ]

    payload = parse_consumables_rows(rows, source="google-sheets")

    assert payload["source"] == "google-sheets"
    assert payload["minimum_charge"] == 1600
    assert len(payload["items"]) == 2
    assert payload["items"][0]["name"] == "Игла RL"
    assert payload["items"][0]["unit_price"] == 190


def test_build_booking_snapshot_marks_busy_slots_by_note() -> None:
    payload = {
        "sheets": [
            {
                "data": [
                    {
                        "rowData": [
                            {
                                "values": [
                                    {"formattedValue": ""},
                                    {"formattedValue": "Пн"},
                                    {"formattedValue": "Вт"},
                                ]
                            },
                            {
                                "values": [
                                    {"formattedValue": "12:00"},
                                    {"formattedValue": "", "note": "Анна / 12:00"},
                                    {"formattedValue": ""},
                                ]
                            },
                            {
                                "values": [
                                    {"formattedValue": "15:00"},
                                    {"formattedValue": "окно"},
                                    {"formattedValue": "", "note": ""},
                                ]
                            },
                        ]
                    }
                ]
            }
        ]
    }

    snapshot = build_booking_snapshot(payload, source="google-sheets")

    assert snapshot["summary"]["bookedCount"] == 1
    assert snapshot["summary"]["availableCount"] == 3
    assert snapshot["slots"][0]["booked"] is True
    assert snapshot["slots"][0]["day"] == "Пн"
    assert snapshot["slots"][1]["booked"] is False
