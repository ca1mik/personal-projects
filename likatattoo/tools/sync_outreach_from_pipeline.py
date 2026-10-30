from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
PIPELINE_PATH = ROOT / "client-pipeline.csv"
OUTREACH_PATH = ROOT / "outreach-contacts.csv"
BOT_ENV_PATH = PROJECT_ROOT / "bot" / ".env"

OUTREACH_HEADERS = [
    "source_record_id",
    "contact_name",
    "contact_info",
    "source",
    "current_context",
    "status",
    "last_known_stage",
    "last_activity_date",
    "next_action_date",
    "next_action",
    "priority",
    "needs_human_review",
    "notes",
]


@dataclass(frozen=True)
class PipelineRow:
    id: str
    date_in: str
    client_name: str
    source: str
    service: str
    idea_or_reference: str
    size_cm: str
    placement: str
    quoted_price: str
    deposit: str
    session_date: str
    status: str
    followup_date: str
    review_status: str
    content_status: str
    notes: str


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTREACH_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def load_session_deposit_rub(default: int = 1500) -> int:
    if not BOT_ENV_PATH.exists():
        return default

    for line in BOT_ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("SESSION_DEPOSIT_RUB="):
            continue
        raw = line.split("=", 1)[1].strip()
        try:
            return int(raw)
        except ValueError:
            return default
    return default


def normalize_contact_info(existing: dict[str, str] | None, source: str) -> str:
    if existing:
        current = existing.get("contact_info", "").strip()
        if current:
            return current
    return f"{source} (точный профиль не зафиксирован)"


def build_context(row: PipelineRow) -> str:
    parts = [row.service]
    if row.idea_or_reference:
        parts.append(row.idea_or_reference)
    if row.size_cm:
        parts.append(f"{row.size_cm} см")
    if row.placement:
        parts.append(row.placement)
    if row.quoted_price:
        parts.append(f"quoted price {row.quoted_price} ₽")
    if row.session_date:
        parts.append(f"session date {row.session_date}")
    if row.deposit:
        parts.append(f"deposit in source file {row.deposit} ₽")
    return ", ".join(parts)


def derive_status(stage: str, existing: dict[str, str] | None) -> str:
    if existing:
        current = existing.get("status", "").strip()
        if current:
            return current

    lowered = stage.lower()
    if "нов" in lowered:
        return "new"
    if "переписк" in lowered:
        return "sent_first_message"
    if "дума" in lowered:
        return "replied_neutral"
    if "запис" in lowered or "выполн" in lowered:
        return "closed"
    return "needs_human_review"


def derive_priority(row: PipelineRow, needs_human_review: bool, existing: dict[str, str] | None) -> str:
    if existing:
        current = existing.get("priority", "").strip()
        if current:
            return current

    if row.session_date:
        return "high"
    if needs_human_review:
        return "medium"
    lowered = row.status.lower()
    if "дума" in lowered or "переписк" in lowered:
        return "medium"
    return "low"


def derive_next_action(status: str, needs_human_review: bool, existing: dict[str, str] | None) -> str:
    if existing:
        current = existing.get("next_action", "").strip()
        if current:
            return current

    if needs_human_review:
        return "Проверить вручную перед любым новым сообщением"
    if status == "new":
        return "Подготовить персонализированное первое сообщение"
    if status == "sent_first_message":
        return "Проверить, нужен ли мягкий follow-up"
    if status == "follow_up_sent":
        return "Ждать ответ или перевести в closed"
    if status == "replied_positive":
        return "Предложить следующий конкретный шаг"
    if status == "replied_neutral":
        return "Подготовить мягкий follow-up по сроку"
    if status == "replied_negative":
        return "Закрыть без повторного касания"
    if status == "closed":
        return "Без новых касаний"
    return "Проверить вручную"


def derive_next_action_date(row: PipelineRow, existing: dict[str, str] | None) -> str:
    if existing:
        current = existing.get("next_action_date", "").strip()
        if current:
            return current
    if row.followup_date:
        return row.followup_date
    return row.date_in


def merge_notes(existing: dict[str, str] | None, row_notes: str, issues: list[str]) -> str:
    notes: list[str] = []
    if existing:
        current = existing.get("notes", "").strip()
        if current:
            notes.append(current)
    if row_notes:
        notes.append(f"Source notes: {row_notes}")
    for issue in issues:
        if issue not in notes:
            notes.append(issue)
    return " | ".join(notes)


def has_exact_contact_info(value: str) -> bool:
    lowered = value.lower()
    return "точный" not in lowered and "не зафиксирован" not in lowered


def build_review_issues(row: PipelineRow, contact_info: str, configured_deposit_rub: int, today: date) -> list[str]:
    issues: list[str] = []

    if not has_exact_contact_info(contact_info):
        issues.append("Нужен точный контакт.")

    date_in = parse_iso(row.date_in)
    if date_in is None:
        issues.append("Некорректная дата входа в pipeline.")
    elif date_in > today:
        issues.append(f"Лид датирован будущей датой {row.date_in}.")

    if row.deposit:
        try:
            deposit_value = int(row.deposit)
        except ValueError:
            issues.append("Некорректное значение депозита в source file.")
        else:
            if deposit_value > 0 and deposit_value != configured_deposit_rub:
                issues.append(
                    f"Депозит в source file {deposit_value} ₽ отличается от текущей политики {configured_deposit_rub} ₽."
                )

    if row.session_date and parse_iso(row.session_date) is None:
        issues.append("Некорректная дата сеанса в source file.")

    return issues


def row_from_pipeline(
    row: PipelineRow,
    existing: dict[str, str] | None,
    configured_deposit_rub: int,
    today: date,
) -> dict[str, str]:
    contact_info = normalize_contact_info(existing, row.source)
    issues = build_review_issues(row, contact_info, configured_deposit_rub, today)
    needs_human_review = "true" if issues else "false"
    derived_status = derive_status(row.status, existing)
    final_status = "needs_human_review" if needs_human_review == "true" else derived_status

    return {
        "source_record_id": row.id,
        "contact_name": row.client_name,
        "contact_info": contact_info,
        "source": row.source,
        "current_context": build_context(row),
        "status": final_status,
        "last_known_stage": row.status,
        "last_activity_date": row.date_in,
        "next_action_date": derive_next_action_date(row, existing),
        "next_action": derive_next_action(final_status, needs_human_review == "true", existing),
        "priority": derive_priority(row, needs_human_review == "true", existing),
        "needs_human_review": needs_human_review,
        "notes": merge_notes(existing, row.notes, issues),
    }


def sync_rows() -> list[dict[str, str]]:
    today = date.today()
    configured_deposit_rub = load_session_deposit_rub()

    pipeline_rows = [PipelineRow(**row) for row in load_rows(PIPELINE_PATH)]
    existing_rows = {
        row["source_record_id"]: row
        for row in load_rows(OUTREACH_PATH)
        if row.get("source_record_id")
    } if OUTREACH_PATH.exists() else {}

    synced: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for pipeline_row in pipeline_rows:
        existing = existing_rows.get(pipeline_row.id)
        synced.append(row_from_pipeline(pipeline_row, existing, configured_deposit_rub, today))
        seen_ids.add(pipeline_row.id)

    for source_record_id, row in existing_rows.items():
        if source_record_id not in seen_ids:
            synced.append(row)

    priority_order = {"high": 0, "medium": 1, "low": 2}
    synced.sort(
        key=lambda item: (
            priority_order.get(item.get("priority", "low"), 9),
            item.get("next_action_date", ""),
            item.get("contact_name", ""),
        )
    )
    return synced


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync outreach contacts from client pipeline.")
    parser.add_argument("--write", action="store_true", help="Write synced data back to outreach-contacts.csv")
    args = parser.parse_args()

    synced = sync_rows()
    print(f"Prepared {len(synced)} outreach contact rows.")

    if args.write:
        write_rows(OUTREACH_PATH, synced)
        print(f"Updated {OUTREACH_PATH}")
    else:
        print("Dry run only. Use --write to persist changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
