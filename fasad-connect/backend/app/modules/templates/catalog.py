from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class CatalogProductDefinition:
    code: str
    name: str
    category: str
    template_code: str | None
    description: str
    bot_menu_label: str
    default_material_code: str
    available_material_codes: tuple[str, ...]
    requires_depth: bool
    min_width: int
    max_width: int
    min_height: int
    max_height: int
    min_depth: int
    max_depth: int
    markup_coefficient: Decimal
    work_rate_per_sqm: Decimal
    hardware_flat_amount: Decimal
    edge_rate_per_meter: Decimal
    bot_questions: tuple[str, ...] = field(default_factory=tuple)


CATALOG_PRODUCTS: tuple[CatalogProductDefinition, ...] = (
    CatalogProductDefinition(
        code="wardrobe_basic",
        name="Шкаф базовый",
        category="wardrobe",
        template_code="wardrobe_basic",
        description=(
            "Типовой шкаф: расчёт по габаритам, площади материала, кромке " "и базовой работе."
        ),
        bot_menu_label="Шкаф",
        default_material_code="ldsp_white_18",
        available_material_codes=("ldsp_white_18", "mdf_oak_16"),
        requires_depth=True,
        min_width=600,
        max_width=3000,
        min_height=1800,
        max_height=3000,
        min_depth=350,
        max_depth=800,
        markup_coefficient=Decimal("1.18"),
        work_rate_per_sqm=Decimal("2850"),
        hardware_flat_amount=Decimal("3200"),
        edge_rate_per_meter=Decimal("42"),
        bot_questions=(
            "Введите ширину шкафа в мм.",
            "Введите высоту шкафа в мм.",
            "Введите глубину шкафа в мм.",
            "Выберите материал корпуса.",
            "Как вас зовут?",
            "Оставьте номер телефона для менеджера.",
        ),
    ),
    CatalogProductDefinition(
        code="kitchen_module_basic",
        name="Кухонный модуль базовый",
        category="kitchen",
        template_code="kitchen_module_basic",
        description=("Типовой кухонный модуль для быстрой оценки стоимости при приёме " "заявки."),
        bot_menu_label="Кухонный модуль",
        default_material_code="ldsp_white_18",
        available_material_codes=("ldsp_white_18", "mdf_oak_16"),
        requires_depth=True,
        min_width=300,
        max_width=1200,
        min_height=600,
        max_height=1100,
        min_depth=300,
        max_depth=700,
        markup_coefficient=Decimal("1.2"),
        work_rate_per_sqm=Decimal("3100"),
        hardware_flat_amount=Decimal("2200"),
        edge_rate_per_meter=Decimal("38"),
        bot_questions=(
            "Введите ширину модуля в мм.",
            "Введите высоту модуля в мм.",
            "Введите глубину модуля в мм.",
            "Выберите материал корпуса или фасада.",
            "Как вас зовут?",
            "Оставьте номер телефона для менеджера.",
        ),
    ),
)


def get_catalog_definition(code: str) -> CatalogProductDefinition | None:
    return next((item for item in CATALOG_PRODUCTS if item.code == code), None)
