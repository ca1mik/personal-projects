"""Разбор текста материала: цвет отдельно, толщина отдельно.

Правило одно на весь проект, поэтому проверяем его прямо, а не через разбор
файла: тем же ``clean_color`` пользуются загрузка бланка, подсказки в полях и
фронт.
"""

from __future__ import annotations

import pytest

from app.core.material_text import clean_color, thickness_from_text


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # запись студии: вид работ, цвет, основа и толщина в одной ячейке
        ("Эмаль RAL 9003 плита 19мм", "RAL 9003"),
        ("Эмаль  RAL  9003  плита 16 мм", "RAL 9003"),
        ("эмаль рал-9003", "RAL 9003"),
        ("RAL9003", "RAL 9003"),
        # без RAL режем основу и толщину, цвет оставляем
        ("ПВХ Белый глянец плита 19мм", "Белый глянец"),
        ("Плёнка Дуб натуральный 16 мм", "Дуб натуральный"),
        # название декора уникально целиком — резать нельзя
        ("Тадж Прага P833UP", "Тадж Прага P833UP"),
        ("Белый глянец", "Белый глянец"),
        # в строке был только вид работ: пустая ячейка бесполезнее исходной
        ("Эмаль", "Эмаль"),
        ("плита 19мм", "плита 19мм"),
        # регистр справочного значения не трогаем
        ("дуб натуральный", "дуб натуральный"),
    ],
)
def test_clean_color(source: str, expected: str) -> None:
    assert clean_color(source) == expected


@pytest.mark.parametrize("source", ["", "   ", None])
def test_clean_color_empty(source: object) -> None:
    assert clean_color(source) is None


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Эмаль RAL 9003 плита 19мм", "19"),
        ("Эмаль RAL 9003 плита 16 мм", "16"),
        ("19,5 мм", "19.5"),
        # голое число из колонки «Мм»
        ("16", "16"),
        ("19.0", "19"),
        # 9003 — это цвет, а не толщина: и по величине, и потому что не «мм»
        ("RAL 9003", None),
        ("Белый глянец", None),
        # вне разумных пределов плиты
        ("0,5 мм", None),
        ("400 мм", None),
    ],
)
def test_thickness_from_text(source: str, expected: str | None) -> None:
    assert thickness_from_text(source) == expected


def test_color_and_thickness_split_one_record() -> None:
    """Одна запись заказчика распадается на цвет и толщину без потерь."""
    source = "Эмаль RAL 9003 плита 19мм"
    assert clean_color(source) == "RAL 9003"
    assert thickness_from_text(source) == "19"
