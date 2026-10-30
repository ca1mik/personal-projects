"""Russian display names for reference data

Статусы заказов, участки, этапы и роли приходили в интерфейс английскими
(«Manufacturing», «Cutting Area», «Edge Banding») — фронт печатает их как есть.
Меняются только колонки ``name``. Все ``code`` остаются английскими: на них
завязаны обращения к API, фильтры и переходы по статусам.

Revision ID: 0008_russian_display_names
Revises: 0007_directions_and_client_org
Create Date: 2026-08-04 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_russian_display_names"
down_revision = "0007_directions_and_client_org"
branch_labels = None
depends_on = None


ORDER_STATUSES = {
    "new": ("Новый", "New"),
    "calculating": ("Расчёт", "Calculating"),
    "approved": ("Согласован", "Approved"),
    "paid": ("Оплачен", "Paid"),
    "cutting": ("Раскрой", "Cutting"),
    "cnc": ("ЧПУ", "CNC"),
    "manufacturing": ("В производстве", "Manufacturing"),
    "ready": ("Готов", "Ready"),
    "shipped": ("Отгружен", "Shipped"),
    "cancelled": ("Отменён", "Cancelled"),
}

WORK_CENTERS = {
    "cutting": ("Участок раскроя", "Cutting Area"),
    "edge_banding": ("Участок кромления", "Edge Banding"),
    "cnc": ("Участок ЧПУ", "CNC Area"),
    "assembly": ("Участок сборки", "Assembly"),
    "qc": ("Контроль качества", "Quality Control"),
    "packing": ("Участок упаковки", "Packing"),
}

WORKFLOW_STAGES = {
    "cutting": ("Раскрой", "Cutting"),
    "edge_banding": ("Кромление", "Edge Banding"),
    "cnc": ("ЧПУ", "CNC"),
    "assembly": ("Сборка", "Assembly"),
    "qc": ("Контроль качества", "Quality Control"),
    "packing": ("Упаковка", "Packing"),
}

WORKFLOWS = {
    "default_furniture": ("Базовый маршрут производства", "Default Furniture Flow"),
}

ROLES = {
    "admin": ("Администратор", "Administrator"),
    "manager": ("Менеджер", "Manager"),
    "technologist": ("Технолог", "Technologist"),
    "operator": ("Оператор производства", "Production Operator"),
}

MATERIALS = {
    "ldsp_white_18": ("ЛДСП белая 18 мм", "LDSP White 18 mm"),
    "mdf_oak_16": ("МДФ дуб 16 мм", "MDF Oak 16 mm"),
}

EDGE_MATERIALS = {
    "edge_abs_white_2": ("Кромка ABS белая 2 мм", "ABS White 2 mm"),
    "edge_abs_oak_1": ("Кромка ABS дуб 1 мм", "ABS Oak 1 mm"),
}

HARDWARE = {
    "shelf_pin": ("Полкодержатель", "Shelf pin"),
    "confirmat": ("Конфирмат", "Confirmat screw"),
    "cam_lock": ("Эксцентриковая стяжка", "Cam lock"),
    "cabinet_leg": ("Опора мебельная", "Cabinet leg"),
}

TEMPLATES = {
    "wardrobe_basic": ("Шкаф базовый", "Wardrobe Basic"),
    "kitchen_module_basic": ("Кухонный модуль базовый", "Kitchen Module Basic"),
}

TABLES = [
    ("order_statuses", ORDER_STATUSES),
    ("work_centers", WORK_CENTERS),
    ("workflow_stages", WORKFLOW_STAGES),
    ("production_workflows", WORKFLOWS),
    ("roles", ROLES),
    ("materials", MATERIALS),
    ("edge_materials", EDGE_MATERIALS),
    ("hardware", HARDWARE),
    ("product_templates", TEMPLATES),
]


def _rename(table: str, mapping: dict[str, tuple[str, str]], *, to_russian: bool) -> None:
    connection = op.get_bind()
    for code, (russian, english) in mapping.items():
        connection.execute(
            sa.text(f"UPDATE {table} SET name = :name WHERE code = :code"),  # noqa: S608
            {"name": russian if to_russian else english, "code": code},
        )


def upgrade() -> None:
    for table, mapping in TABLES:
        _rename(table, mapping, to_russian=True)


def downgrade() -> None:
    for table, mapping in TABLES:
        _rename(table, mapping, to_russian=False)
