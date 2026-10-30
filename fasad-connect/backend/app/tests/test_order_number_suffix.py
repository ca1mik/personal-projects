"""Номер зависит только от направления, независимо от артикула и обработки."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.modules.directions.models import ProductionDirection
from app.modules.directions.service import DirectionService
from app.modules.price_book.kinds import (
    DIRECTION_NUMBER_SUFFIXES,
    DIRECTION_PRICE_KINDS,
    PRICE_ITEM_KINDS,
    PRODUCTION_DIRECTION_NAMES,
    direction_price_kind,
    kind_number_suffix,
    production_kind_options,
)

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0007_directions_and_client_org.py"
)


def migration_directions() -> list[tuple[str, str, str, str, int]]:
    """Направления в том виде, в каком их заводит на боевой базе миграция 0007.

    Читаем сам файл миграции, а не копию списка: расхождение кода со справочником
    в БД — это ровно та поломка, из-за которой отборы по направлениям были пустыми.
    """
    spec = importlib.util.spec_from_file_location("migration_0007", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.DIRECTIONS)


def make_direction(code: str) -> ProductionDirection:
    """Направление без БД: для формата номера хватает кода и буквы."""
    return ProductionDirection(
        code=code,
        name=PRODUCTION_DIRECTION_NAMES[code],
        number_suffix=DIRECTION_NUMBER_SUFFIXES[code],
    )


# --- один справочник вместо двух -------------------------------------------


def test_code_tables_match_migration_seed():
    seeded = migration_directions()

    assert [code for code, *_ in seeded] == list(PRODUCTION_DIRECTION_NAMES)
    for code, name, suffix, _description, _sort_order in seeded:
        assert PRODUCTION_DIRECTION_NAMES[code] == name
        assert DIRECTION_NUMBER_SUFFIXES[code] == suffix


def test_direction_and_its_price_kind_give_the_same_letter():
    """«pvc» и «film» — одно и то же покрытие, буква обязана совпадать."""
    for code, suffix in DIRECTION_NUMBER_SUFFIXES.items():
        assert kind_number_suffix(code) == suffix
        assert kind_number_suffix(DIRECTION_PRICE_KINDS[code]) == suffix


def test_production_options_are_direction_codes():
    options = production_kind_options()

    assert [item["code"] for item in options] == [code for code, *_ in migration_directions()]
    for item in options:
        # Тип работ у каждого направления настоящий: под ним заводится
        # номенклатура из артикулов, набранных в заявке руками.
        assert item["kind"] in PRICE_ITEM_KINDS
        assert item["kind"] == direction_price_kind(item["code"])


def test_direction_without_price_kind_returns_empty():
    """Заказчик заводит свои направления — типа работ для них в прайсе нет."""
    assert direction_price_kind("acrylic") == ""


# --- буква в номере ---------------------------------------------------------


def test_direction_letter_wins_over_work_kind():
    """ПВХ с фрезеровкой остаётся «П»: направление выбрал менеджер руками."""
    assert DirectionService.format_order_number(7, make_direction("pvc"), "milling") == "0007-П"
    assert DirectionService.format_order_number(7, make_direction("veneer"), "soap") == "0007-Ш"


@pytest.mark.parametrize("kind", ["paint", "film", "soap", "milling", "veneer", None])
def test_enamel_never_uses_work_kind_letter(kind):
    enamel = make_direction("enamel")
    assert DirectionService.format_order_number(7, enamel, kind) == "0007"


def test_work_kind_letter_without_direction():
    assert DirectionService.format_order_number(7, None, "film") == "0007"
    assert DirectionService.format_order_number(7, None, "veneer") == "0007"


@pytest.mark.parametrize("work_kind", ["board", "edge", "service", "laminate", "", None])
def test_unknown_or_letterless_work_kind_keeps_plain_number(work_kind):
    """Лишняя буква в номере хуже её отсутствия: по ней в цеху ищут пачку."""
    assert DirectionService.format_order_number(7, None, work_kind) == "0007"
    assert DirectionService.format_order_number(7, make_direction("enamel"), work_kind) == "0007"


def test_unknown_kind_never_overrides_direction_letter():
    assert DirectionService.format_order_number(7, make_direction("pvc"), "laminate") == "0007-П"


def test_number_keeps_four_digits_and_grows():
    assert DirectionService.format_order_number(1, None, "milling") == "0001"
    assert DirectionService.format_order_number(12345, None, "milling") == "12345"


@pytest.mark.parametrize("code,expected", [("enamel","004403"),("pvc","004403-П"),("veneer","004403-Ш")])
def test_standard_direction_letter_does_not_depend_on_old_catalog_suffix(code,expected):
    direction=make_direction(code)
    direction.number_suffix="П" if code=="enamel" else "М"
    assert DirectionService.format_order_number_base("004403",direction,"soap")==expected


def test_custom_direction_keeps_its_own_letter():
    direction=ProductionDirection(code="acrylic",name="Акрил",number_suffix="А")
    assert DirectionService.format_order_number_base("004403",direction,"film")=="004403-А"
