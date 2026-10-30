"""Tests for the cold-outreach campaign helpers.

The guards matter more than the happy path here: a mistake in this module is not
a broken screen, it is a wrong letter delivered to a real company.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.modules.messaging.outreach import (
    CampaignState,
    Prospect,
    load_prospects,
    load_state,
    render_body,
    save_state,
    select_batch,
)

LETTER = (
    "Иван Петрович, здравствуйте. Нашёл вас в отраслевом каталоге — «{company}» "
    "делает фасады в плёнке и эмали в городе {city}. Мы сделали систему учёта "
    "для фасадных цехов: заявки из почты и мессенджеров собираются в один экран, "
    "а по каждой детали видно, на каком она этапе. Подскажите, у вас цех сейчас "
    "на 1С или на таблицах?"
)


def _entry(code: str, company: str, city: str, email: str, body: str | None = None) -> dict:
    return {
        "code": code,
        "company": company,
        "city": city,
        "email": email,
        "subject": f"вопрос по учёту деталей — {company}",
        "body": body if body is not None else LETTER.format(company=company, city=city),
    }


def _write(path: Path, entries: list[dict]) -> Path:
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


def _prospect(code: str, email: str) -> Prospect:
    return Prospect(
        code=code,
        company=f"Компания {code}",
        city="Пермь",
        email=email,
        subject="тема",
        body="тело",
    )


def test_loads_valid_prospects(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "p.json",
        [
            _entry("vokrug", "ВОКРУГ", "Челябинск", "fasad@vokrug.ru"),
            _entry("lados", "Ладос-Мебель", "Москва", "alla@lados-m.ru"),
        ],
    )

    prospects = load_prospects(path)

    assert [p.code for p in prospects] == ["vokrug", "lados"]
    assert prospects[0].email == "fasad@vokrug.ru"


def test_accepts_company_name_in_declined_form(tmp_path: Path) -> None:
    """Russian declension must not be mistaken for an impersonal letter."""
    body = (
        "Здравствуйте. Пишу в «Первую Фабрику Фасадов»: видел, что у вас два "
        "представительства и заказы идут от мебельщиков. Мы сделали систему, где "
        "статус каждой детали виден без обзвона цеха. У вас это сейчас в таблицах?"
    )
    path = _write(
        tmp_path / "p.json",
        [_entry("pff", "Первая Фабрика Фасадов", "Реутов", "pffzakaz@mail.ru", body)],
    )

    assert len(load_prospects(path)) == 1


def test_rejects_identical_letters(tmp_path: Path) -> None:
    """Identical bulk letters are advertising without consent, not correspondence."""
    shared = LETTER.format(company="Альфа", city="Пермь")
    path = _write(
        tmp_path / "p.json",
        [
            _entry("a", "Альфа Пермь", "Пермь", "a@example.ru", shared),
            _entry("b", "Альфа Казань", "Казань", "b@example.ru", shared),
        ],
    )

    with pytest.raises(AppError, match="совпадает текст письма"):
        load_prospects(path)


def test_rejects_impersonal_letter(tmp_path: Path) -> None:
    body = (
        "Здравствуйте. Мы разрабатываем системы учёта для производства и предлагаем "
        "рассмотреть сотрудничество. Готовы показать возможности нашего продукта в "
        "удобное для вас время, отвечаем быстро и работаем по всей стране."
    )
    path = _write(tmp_path / "p.json", [_entry("x", "Ависта", "Барнаул", "x@example.ru", body)])

    with pytest.raises(AppError, match="Обезличенное письмо"):
        load_prospects(path)


def test_rejects_malformed_email(tmp_path: Path) -> None:
    path = _write(tmp_path / "p.json", [_entry("x", "Ависта", "Барнаул", "не-почта")])

    with pytest.raises(AppError, match="не похож на почтовый"):
        load_prospects(path)


def test_rejects_duplicate_address(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "p.json",
        [
            _entry("a", "Альфа", "Пермь", "same@example.ru"),
            _entry("b", "Бета", "Казань", "same@example.ru"),
        ],
    )

    with pytest.raises(AppError, match="указан у двух компаний"):
        load_prospects(path)


def test_rejects_stub_body(tmp_path: Path) -> None:
    path = _write(tmp_path / "p.json", [_entry("x", "Ависта", "Барнаул", "x@example.ru", "Ависта")])

    with pytest.raises(AppError, match="похоже на незаполненную заготовку"):
        load_prospects(path)


def test_batch_skips_sent_replied_and_opted_out() -> None:
    prospects = [
        _prospect("a", "a@example.ru"),
        _prospect("b", "b@example.ru"),
        _prospect("c", "c@example.ru"),
        _prospect("d", "d@example.ru"),
    ]
    state = CampaignState(replied={"b"}, opted_out={"c@example.ru"})
    state.record(prospects[0], message_id="<1@x>")

    batch = select_batch(prospects, state, limit=10)

    assert [p.code for p in batch] == ["d"]


def test_daily_limit_counts_only_today() -> None:
    prospects = [_prospect(code, f"{code}@example.ru") for code in ("a", "b", "c")]
    state = CampaignState()
    now = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)
    state.record(prospects[0], message_id="<1@x>", now=datetime(2026, 9, 2, 10, 0, tzinfo=UTC))
    state.record(prospects[1], message_id="<2@x>", now=now)

    batch = select_batch(prospects, state, limit=10, daily_limit=2, now=now)

    assert [p.code for p in batch] == ["c"]


def test_state_survives_a_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = CampaignState(replied={"a"}, opted_out={"x@example.ru"})
    state.record(_prospect("b", "b@example.ru"), message_id="<2@x>")

    save_state(path, state)
    restored = load_state(path)

    assert restored.replied == {"a"}
    assert restored.opted_out == {"x@example.ru"}
    assert restored.was_sent("b")


def test_render_body_guarantees_an_opt_out_line() -> None:
    body = render_body(_prospect("a", "a@example.ru"), signature="ИП Иванов, ИНН 000000000000")

    assert "ИНН 000000000000" in body
    assert "Ответьте «нет»" in body


def test_render_body_keeps_an_existing_opt_out_line() -> None:
    prospect = Prospect(
        code="a",
        company="Альфа",
        city="Пермь",
        email="a@example.ru",
        subject="тема",
        body="Текст письма. Ответьте «нет» — исключу из переписки.",
    )

    body = render_body(prospect, signature="ИП Иванов")

    assert body.count("Ответьте «нет»") == 1
