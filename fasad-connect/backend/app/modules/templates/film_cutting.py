from __future__ import annotations

from dataclasses import dataclass

DEFAULT_FILM_ROLL_WIDTH_MM = 1400
DEFAULT_FILM_TRIM_MARGIN_MM = 60


@dataclass(frozen=True)
class FilmColorDefinition:
    code: str
    name: str
    finish: str


@dataclass(frozen=True)
class FilmMillingDefinition:
    code: str
    name: str
    extra_margin_mm: int
    description: str


@dataclass(frozen=True)
class FilmCatalogItemDefinition:
    code: str
    name: str
    description: str
    default_length_mm: int
    default_width_mm: int
    default_depth_mm: int
    default_quantity: int
    default_milling_code: str
    default_color_code: str


FILM_COLORS: tuple[FilmColorDefinition, ...] = (
    FilmColorDefinition(code="white_gloss", name="Белый глянец", finish="gloss"),
    FilmColorDefinition(code="graphite_matt", name="Графит матовый", finish="matt"),
    FilmColorDefinition(code="cashmere_matt", name="Кашемир матовый", finish="matt"),
    FilmColorDefinition(code="oak_natural", name="Дуб натуральный", finish="wood"),
    FilmColorDefinition(code="black_soft", name="Черный soft-touch", finish="soft"),
)


FILM_MILLINGS: tuple[FilmMillingDefinition, ...] = (
    FilmMillingDefinition(
        code="flat",
        name="Без фрезеровки",
        extra_margin_mm=0,
        description="Плоский фасад без выборки и дополнительных припусков.",
    ),
    FilmMillingDefinition(
        code="frame_light",
        name="Рамка легкая",
        extra_margin_mm=12,
        description="Небольшая рамочная выборка с умеренным запасом на пленку.",
    ),
    FilmMillingDefinition(
        code="frame_deep",
        name="Рамка глубокая",
        extra_margin_mm=20,
        description="Глубокая рамка или филенка, требуется увеличенный запас.",
    ),
    FilmMillingDefinition(
        code="wave",
        name="Волна / сложная фрезеровка",
        extra_margin_mm=28,
        description="Сложный профиль, нужен дополнительный запас для вакуумной формовки.",
    ),
)


FILM_CATALOG_ITEMS: tuple[FilmCatalogItemDefinition, ...] = (
    FilmCatalogItemDefinition(
        code="kitchen_facade_716_396",
        name="Фасад кухни 716 x 396",
        description="Типовой фасад нижнего модуля.",
        default_length_mm=716,
        default_width_mm=396,
        default_depth_mm=20,
        default_quantity=1,
        default_milling_code="frame_light",
        default_color_code="white_gloss",
    ),
    FilmCatalogItemDefinition(
        code="kitchen_facade_920_446",
        name="Фасад кухни 920 x 446",
        description="Типовой фасад высокого модуля или колонны.",
        default_length_mm=920,
        default_width_mm=446,
        default_depth_mm=22,
        default_quantity=1,
        default_milling_code="frame_deep",
        default_color_code="cashmere_matt",
    ),
    FilmCatalogItemDefinition(
        code="wardrobe_door_2200_500",
        name="Дверь шкафа 2200 x 500",
        description="Высокий фасад под шкаф или гардероб.",
        default_length_mm=2200,
        default_width_mm=500,
        default_depth_mm=18,
        default_quantity=1,
        default_milling_code="flat",
        default_color_code="graphite_matt",
    ),
    FilmCatalogItemDefinition(
        code="bathroom_facade_596_296",
        name="Фасад ванной 596 x 296",
        description="Компактный фасад под подвесной модуль.",
        default_length_mm=596,
        default_width_mm=296,
        default_depth_mm=16,
        default_quantity=1,
        default_milling_code="wave",
        default_color_code="oak_natural",
    ),
)


def get_film_color(code: str) -> FilmColorDefinition | None:
    return next((item for item in FILM_COLORS if item.code == code), None)


def get_film_milling(code: str) -> FilmMillingDefinition | None:
    return next((item for item in FILM_MILLINGS if item.code == code), None)


def get_film_catalog_item(code: str) -> FilmCatalogItemDefinition | None:
    return next((item for item in FILM_CATALOG_ITEMS if item.code == code), None)
