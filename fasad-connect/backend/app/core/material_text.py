"""Разбор текста, которым студия описывает материал детали.

В колонке «Цвет» заказчик пишет строкой всё сразу: вид работ, основу и
толщину — «Эмаль RAL 9003 плита 19мм». Для человека это одна запись, для
системы — три разных поля: толщина живёт в своей графе и делит карты раскроя,
вид работ приходит артикулом из справочника, а цветом остаётся только цвет.

Правило нужно одно на весь проект: тем же текстом приходят и загруженный файл
заказчика, и набранная руками строка, и подсказки в полях. Пока правил было
два, файл и клавиатура давали разные значения, и один цвет разъезжался на два
материала — а значит и на два листа.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# «RAL 9003», «RAL9003», «рал-9003» — заказчик пишет по-разному, а в заказ
# должно попасть одно каноничное написание.
RAL_PATTERN = re.compile(r"\b(?:RAL|РАЛ)\s*-?\s*(\d{3,4})\b", re.IGNORECASE)

# Толщина внутри текста: «плита 19мм», «16 мм», «19,5 мм».
# Взгляд назад обязателен: без него из «RAL 9003мм» вырезалось бы «003».
THICKNESS_IN_TEXT_PATTERN = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:[.,]\d+)?)\s*мм",
    re.IGNORECASE,
)

# Разумные пределы толщины плиты: всё вне их — не толщина, а случайное число.
MIN_THICKNESS_MM = Decimal("1")
MAX_THICKNESS_MM = Decimal("100")

# Основа и вид работ. Это не цвет: на чём делают — отдельное поле, а вид работ
# приходит артикулом из справочника.
KIND_WORDS = (
    "эмаль",
    "эмалевый",
    "эмалированный",
    "пвх",
    "pvc",
    "плёнка",
    "пленка",
    "плита",
    "мдф",
    "mdf",
    "лдсп",
    "хдф",
    "дсп",
    "шпон",
    "шпонированный",
    "массив",
    "акрил",
    "пластик",
)

KIND_PATTERN = re.compile(
    r"(?:(?<=\s)|^)(?:" + "|".join(KIND_WORDS) + r")(?=\s|$)",
    re.IGNORECASE,
)

# Мусор, остающийся на стыках после вырезания слов.
LEFTOVER_SEPARATORS = re.compile(r"^[\s,;·—–-]+|[\s,;·—–-]+$")


def collapse_spaces(value: object) -> str:
    """Схлопывает пробелы: «Эмаль  RAL  9003» и «Эмаль RAL 9003» — одно и то же."""
    return " ".join(str(value or "").split())


def format_thickness(number: Decimal) -> str:
    """«19.0» → «19», «19.50» → «19.5»: в заказ идёт число, а не запись из ячейки."""
    return format(number.normalize(), "f")


def thickness_from_text(value: object) -> str | None:
    """Толщина из свободного текста: «Эмаль RAL 9003 плита 19мм» → «19».

    Годится и для колонки «Мм», и для названия цвета: в бланке заказчика
    колонка пустая, а толщина написана внутри цвета.
    """
    text = collapse_spaces(value)
    if not text:
        return None

    candidates = [match.group(1) for match in THICKNESS_IN_TEXT_PATTERN.finditer(text)]
    if not candidates:
        # в колонке «Мм» пишут голое число, без единиц измерения
        bare = text.replace(",", ".")
        if re.fullmatch(r"\d{1,3}(?:\.\d+)?", bare):
            candidates = [bare]

    for candidate in candidates:
        try:
            number = Decimal(candidate.replace(",", "."))
        except InvalidOperation:
            continue
        if MIN_THICKNESS_MM <= number <= MAX_THICKNESS_MM:
            return format_thickness(number)
    return None


def clean_color(value: object) -> str | None:
    """Цвет в том виде, в каком его нужно хранить и показывать.

    Есть RAL — от записи остаётся каноничное «RAL 9003», всё остальное
    («Эмаль», «плита 19мм») к цвету отношения не имеет. Нет RAL — вырезаем
    толщину и основу, а название декора оставляем целиком: «Тадж Прага P833UP»
    резать нельзя, там значим каждый символ.

    Если после чистки не осталось ничего, значит в строке был только вид работ:
    возвращаем исходную запись — она полезнее пустого значения.
    """
    text = collapse_spaces(value)
    if not text:
        return None

    match = RAL_PATTERN.search(text)
    if match:
        return f"RAL {match.group(1)}"

    stripped = collapse_spaces(KIND_PATTERN.sub(" ", THICKNESS_IN_TEXT_PATTERN.sub(" ", text)))
    stripped = LEFTOVER_SEPARATORS.sub("", stripped)
    if not stripped:
        return text

    # Заглавная возвращается, только если её срезали вместе с видом работ:
    # «ПВХ Белый глянец» → «Белый глянец», а «дуб натуральный» из справочника
    # остаётся как записан.
    if stripped[0] != text[0] and stripped[0].isalpha():
        return stripped[0].upper() + stripped[1:]
    return stripped
