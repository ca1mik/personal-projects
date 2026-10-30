from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONTACTS_PATH = ROOT / "outreach-contacts.csv"


@dataclass(frozen=True)
class Contact:
    source_record_id: str
    contact_name: str
    contact_info: str
    source: str
    current_context: str
    status: str
    last_known_stage: str
    last_activity_date: str
    next_action_date: str
    next_action: str
    priority: str
    needs_human_review: str
    notes: str


def load_contacts(path: Path) -> list[Contact]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [Contact(**row) for row in csv.DictReader(fh)]


def parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def main() -> int:
    today = date.today()
    contacts = load_contacts(CONTACTS_PATH)
    status_counts = Counter(contact.status for contact in contacts)
    due_today: list[Contact] = []
    warnings: list[str] = []

    for contact in contacts:
        next_action_date = parse_iso_date(contact.next_action_date)
        if next_action_date is not None and next_action_date <= today:
            due_today.append(contact)

        if "точный" in contact.contact_info.lower():
            warnings.append(f"{contact.contact_name}: missing exact contact info")
        if contact.needs_human_review.lower() == "true":
            warnings.append(f"{contact.contact_name}: needs human review")

    print(f"Outreach summary for {today.isoformat()}")
    print()
    print("Statuses:")
    for status, count in sorted(status_counts.items()):
        print(f"  - {status}: {count}")

    print()
    print("Due now:")
    if due_today:
        for contact in due_today:
            print(
                f"  - {contact.contact_name} [{contact.status}] -> {contact.next_action} "
                f"(date: {contact.next_action_date})"
            )
    else:
        print("  - none")

    print()
    print("Warnings:")
    if warnings:
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("  - none")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
