"""Cold outreach: personalised first-touch letters over the existing email channel.

This is a sales tool, not a mass mailer, and the difference is legal as much as
stylistic. Russian ad law (38-ФЗ art. 18) treats identical messages sent in bulk
without prior consent as advertising; an individually written business letter
addressed to a named company is ordinary correspondence. :func:`load_prospects`
therefore refuses a campaign in which two prospects share a body, so that
distinction cannot be lost by accident once the list grows.

Delivery reuses a configured email :class:`~app.modules.messaging.models.ChannelAccount`:
credentials stay encrypted where the admin UI already put them, no new secret is
introduced, and replies arrive through the normal inbox flow instead of a side
channel that nobody watches.

State lives in a small JSON file rather than a table. A campaign is a handful of
letters a person sends by hand over a few weeks; that does not justify a
migration, and a file can be read, edited and backed up without the app running.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.core.exceptions import AppError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")

OPT_OUT_MARKER = "Ответьте «нет»"
"""Every letter has to offer a one-word refusal; :func:`render_body` adds it if missing."""

MIN_BODY_LENGTH = 120

WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
STEM_LENGTH = 4
"""Russian declines names — «Первая Фабрика» becomes «Первую Фабрику» in a letter.

Comparing whole words would therefore reject correct, well-written letters, so
the personalisation check compares four-letter stems instead.
"""

GENERIC_STEMS = frozenset(
    {"фаса", "мебе", "фабр", "комп", "прои", "груп", "цент", "диза", "заво", "стил", "деко"}
)
"""Words that say nothing about *which* company this is: every letter here has them."""


@dataclass(frozen=True)
class Prospect:
    """One company on the list, with the letter written specifically for it."""

    code: str
    company: str
    city: str
    email: str
    subject: str
    body: str
    note: str = ""


@dataclass
class CampaignState:
    """What has already happened, so nothing is sent twice."""

    sent: dict[str, list[dict]] = field(default_factory=dict)
    replied: set[str] = field(default_factory=set)
    opted_out: set[str] = field(default_factory=set)

    def was_sent(self, code: str) -> bool:
        return bool(self.sent.get(code))

    def sent_today(self, *, now: datetime | None = None) -> int:
        today = (now or datetime.now(UTC)).date().isoformat()
        return sum(
            1
            for touches in self.sent.values()
            for touch in touches
            if str(touch.get("at", ""))[:10] == today
        )

    def record(self, prospect: Prospect, *, message_id: str, now: datetime | None = None) -> None:
        self.sent.setdefault(prospect.code, []).append(
            {
                "at": (now or datetime.now(UTC)).isoformat(),
                "email": prospect.email,
                "subject": prospect.subject,
                "message_id": message_id,
            }
        )


def load_prospects(path: Path) -> list[Prospect]:
    """Read the prospect file and refuse anything that would make a bad campaign."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AppError(f"Файл со списком компаний не найден: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AppError(f"Список компаний повреждён и не читается как JSON: {exc}") from exc

    if not isinstance(raw, list) or not raw:
        raise AppError("Список компаний пуст или имеет неверный формат — ожидается массив.")

    prospects: list[Prospect] = []
    for index, item in enumerate(raw, start=1):
        try:
            prospect = Prospect(
                code=str(item["code"]).strip(),
                company=str(item["company"]).strip(),
                city=str(item.get("city", "")).strip(),
                email=str(item["email"]).strip().lower(),
                subject=str(item["subject"]).strip(),
                body=str(item["body"]).strip(),
                note=str(item.get("note", "")).strip(),
            )
        except (KeyError, TypeError) as exc:
            raise AppError(f"Запись №{index} в списке неполная: не хватает поля {exc}") from exc
        _validate(prospect, index)
        prospects.append(prospect)

    _reject_duplicates(prospects)
    return prospects


def _validate(prospect: Prospect, index: int) -> None:
    if not EMAIL_RE.match(prospect.email):
        raise AppError(
            f"Запись №{index} («{prospect.company}»): адрес «{prospect.email}» "
            "не похож на почтовый. Письмо ушло бы в никуда."
        )
    if not prospect.subject:
        raise AppError(f"Запись №{index} («{prospect.company}»): пустая тема письма.")
    if len(prospect.body) < MIN_BODY_LENGTH:
        raise AppError(
            f"Запись №{index} («{prospect.company}»): текст письма короче "
            f"{MIN_BODY_LENGTH} символов — похоже на незаполненную заготовку."
        )
    if not _mentions_addressee(prospect):
        raise AppError(
            f"Запись №{index} («{prospect.company}»): в тексте нет ни названия компании, "
            "ни города. Обезличенное письмо — это уже рассылка, а не деловое обращение."
        )


def _stems(text: str) -> set[str]:
    return {word[:STEM_LENGTH].lower() for word in WORD_RE.findall(text)}


def _mentions_addressee(prospect: Prospect) -> bool:
    """True when the letter names this company or its city, declension allowed."""
    identifying = (_stems(prospect.company) | _stems(prospect.city)) - GENERIC_STEMS
    if not identifying:
        return True
    return bool(identifying & _stems(prospect.body))


def _reject_duplicates(prospects: list[Prospect]) -> None:
    by_code: dict[str, str] = {}
    by_email: dict[str, str] = {}
    by_body: dict[str, str] = {}

    for prospect in prospects:
        if prospect.code in by_code:
            raise AppError(
                f"Код «{prospect.code}» встречается дважды: "
                f"«{by_code[prospect.code]}» и «{prospect.company}»."
            )
        by_code[prospect.code] = prospect.company

        if prospect.email in by_email:
            raise AppError(
                f"Адрес {prospect.email} указан у двух компаний: "
                f"«{by_email[prospect.email]}» и «{prospect.company}». "
                "Второе письмо на тот же ящик выглядит как спам."
            )
        by_email[prospect.email] = prospect.company

        fingerprint = " ".join(prospect.body.split())
        if fingerprint in by_body:
            raise AppError(
                f"У компаний «{by_body[fingerprint]}» и «{prospect.company}» "
                "совпадает текст письма. Одинаковые письма по списку — это реклама "
                "без согласия (ст. 18 38-ФЗ), а не деловая переписка. "
                "Напишите каждой компании отдельно."
            )
        by_body[fingerprint] = prospect.company


def load_state(path: Path) -> CampaignState:
    if not path.exists():
        return CampaignState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AppError(
            f"Журнал отправок повреждён: {exc}. Исправьте или удалите файл {path} — "
            "при удалении история касаний будет потеряна и письма могут уйти повторно."
        ) from exc
    return CampaignState(
        sent=dict(raw.get("sent") or {}),
        replied=set(raw.get("replied") or []),
        opted_out={str(value).lower() for value in (raw.get("opted_out") or [])},
    )


def save_state(path: Path, state: CampaignState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sent": state.sent,
        "replied": sorted(state.replied),
        "opted_out": sorted(state.opted_out),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def select_batch(
    prospects: list[Prospect],
    state: CampaignState,
    *,
    limit: int,
    daily_limit: int | None = None,
    now: datetime | None = None,
) -> list[Prospect]:
    """Pick who to write to next, honouring every reason not to write."""
    if limit <= 0:
        return []

    remaining = limit
    if daily_limit is not None:
        remaining = min(remaining, max(0, daily_limit - state.sent_today(now=now)))

    batch: list[Prospect] = []
    for prospect in prospects:
        if len(batch) >= remaining:
            break
        if state.was_sent(prospect.code):
            continue
        if prospect.code in state.replied:
            continue
        if prospect.email in state.opted_out:
            continue
        batch.append(prospect)
    return batch


def render_body(prospect: Prospect, *, signature: str) -> str:
    """Attach the sender's requisites and guarantee the opt-out line is present."""
    parts = [prospect.body.strip()]
    if signature.strip():
        parts.append(signature.strip())
    text = "\n\n".join(parts)
    if OPT_OUT_MARKER not in text:
        text += "\n\nОтветьте «нет» — больше не напишу."
    return text
