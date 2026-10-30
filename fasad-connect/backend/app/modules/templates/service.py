from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.pagination import PageParams, pagination_meta
from app.modules.leads.models import Lead
from app.modules.leads.service import LeadService
from app.modules.messaging.inbox_service import InboxService
from app.modules.messaging.schemas import UnifiedLeadIn, UnifiedSenderIn
from app.modules.production.models import Material
from app.modules.production.schemas import MaterialRead
from app.modules.templates.catalog import CATALOG_PRODUCTS, get_catalog_definition
from app.modules.templates.film_cutting import (
    DEFAULT_FILM_ROLL_WIDTH_MM,
    DEFAULT_FILM_TRIM_MARGIN_MM,
    FILM_CATALOG_ITEMS,
    FILM_COLORS,
    FILM_MILLINGS,
    get_film_catalog_item,
    get_film_color,
    get_film_milling,
)
from app.modules.templates.models import ProductTemplate
from app.modules.templates.schemas import (
    CatalogEstimateComponent,
    CatalogEstimateRead,
    CatalogEstimateRequest,
    CatalogLeadCreateRequest,
    CatalogProductRead,
    FilmCatalogItemRead,
    FilmColorRead,
    FilmCuttingColorPlanRead,
    FilmCuttingEstimateRead,
    FilmCuttingEstimateRequest,
    FilmCuttingLayoutItemRead,
    FilmCuttingLayoutRowRead,
    FilmCuttingLeadCreateRequest,
    FilmCuttingLineRead,
    FilmCuttingOptionsRead,
    FilmMillingRead,
    ProductTemplateCreate,
)


class TemplateService:
    @staticmethod
    def list_templates(db: Session, params: PageParams) -> tuple[list[ProductTemplate], dict]:
        stmt = select(ProductTemplate).order_by(ProductTemplate.created_at.desc())
        total = db.scalar(select(func.count()).select_from(ProductTemplate)) or 0
        templates = db.scalars(stmt.offset(params.offset).limit(params.size)).all()
        return templates, pagination_meta(total, params)

    @staticmethod
    def create_template(db: Session, payload: ProductTemplateCreate) -> ProductTemplate:
        template = ProductTemplate(**payload.model_dump())
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    @staticmethod
    def list_catalog(db: Session) -> list[CatalogProductRead]:
        materials = {
            item.code: item
            for item in db.scalars(
                select(Material).where(Material.is_active.is_(True)).order_by(Material.name.asc())
            ).all()
        }

        catalog: list[CatalogProductRead] = []
        for definition in CATALOG_PRODUCTS:
            available_materials = [
                MaterialRead.model_validate(materials[code])
                for code in definition.available_material_codes
                if code in materials
            ]
            catalog.append(
                CatalogProductRead(
                    code=definition.code,
                    name=definition.name,
                    category=definition.category,
                    template_code=definition.template_code,
                    description=definition.description,
                    bot_menu_label=definition.bot_menu_label,
                    default_material_code=definition.default_material_code,
                    requires_depth=definition.requires_depth,
                    min_width=definition.min_width,
                    max_width=definition.max_width,
                    min_height=definition.min_height,
                    max_height=definition.max_height,
                    min_depth=definition.min_depth,
                    max_depth=definition.max_depth,
                    bot_questions=list(definition.bot_questions),
                    available_materials=available_materials,
                )
            )
        return catalog

    @staticmethod
    def _round_money(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _round_metric(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _round_percent(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _get_material(db: Session, material_code: str | None, fallback_code: str) -> Material:
        target_code = material_code or fallback_code
        material = db.scalar(
            select(Material).where(Material.code == target_code, Material.is_active.is_(True))
        )
        if material:
            return material

        fallback = db.scalar(
            select(Material).where(Material.code == fallback_code, Material.is_active.is_(True))
        )
        if fallback:
            return fallback

        raise AppError("No active material found for catalog estimate")

    @staticmethod
    def _validate_dimensions(payload: CatalogEstimateRequest, product_code: str) -> None:
        definition = get_catalog_definition(product_code)
        if definition is None:
            raise AppError("Catalog product not found")

        if not definition.min_width <= payload.width <= definition.max_width:
            raise AppError(
                f"Width must be between {definition.min_width} and {definition.max_width} mm"
            )
        if not definition.min_height <= payload.height <= definition.max_height:
            raise AppError(
                f"Height must be between {definition.min_height} and {definition.max_height} mm"
            )
        if not definition.min_depth <= payload.depth <= definition.max_depth:
            raise AppError(
                f"Depth must be between {definition.min_depth} and {definition.max_depth} mm"
            )

    @staticmethod
    def calculate_catalog_estimate(
        db: Session,
        payload: CatalogEstimateRequest,
    ) -> CatalogEstimateRead:
        TemplateService._validate_dimensions(payload, payload.product_code)
        definition = get_catalog_definition(payload.product_code)
        if definition is None:
            raise AppError("Catalog product not found")

        material = TemplateService._get_material(
            db,
            payload.material_code,
            definition.default_material_code,
        )

        width = Decimal(payload.width)
        height = Decimal(payload.height)
        depth = Decimal(payload.depth)
        quantity = Decimal(payload.quantity)
        visible_area = (width * height * quantity) / Decimal("1000000")

        if definition.code == "wardrobe_basic":
            shelves_count = max(1, int(payload.width / 800))
            board_area = (
                (Decimal("2") * height * depth)
                + (Decimal("2") * (width - Decimal("36")) * depth)
                + (width * height * Decimal("0.32"))
                + (Decimal(shelves_count) * (width - Decimal("36")) * (depth - Decimal("20")))
            ) / Decimal("1000000")
            edge_length = (
                (
                    (Decimal("2") * height)
                    + (Decimal("4") * width)
                    + (Decimal("6") * depth)
                    + (Decimal(shelves_count) * Decimal("2") * width)
                )
                * quantity
            ) / Decimal("1000")
        else:
            board_area = (
                (Decimal("2") * height * depth)
                + (Decimal("2") * (width - Decimal("36")) * depth)
                + (width * height * Decimal("0.68"))
            ) / Decimal("1000000")
            edge_length = (
                ((Decimal("2") * height) + (Decimal("5") * width) + (Decimal("4") * depth))
                * quantity
            ) / Decimal("1000")

        board_area *= quantity

        material_cost = TemplateService._round_money(board_area * material.price)
        edge_cost = TemplateService._round_money(edge_length * definition.edge_rate_per_meter)
        hardware_cost = TemplateService._round_money(definition.hardware_flat_amount * quantity)
        work_cost = TemplateService._round_money(
            (board_area * definition.work_rate_per_sqm) + (visible_area * Decimal("950"))
        )

        components = [
            CatalogEstimateComponent(
                code="material",
                name=f"Material {material.name}",
                amount=material_cost,
                unit="sqm",
                quantity=TemplateService._round_metric(board_area),
            ),
            CatalogEstimateComponent(
                code="edge",
                name="Edge processing",
                amount=edge_cost,
                unit="m",
                quantity=TemplateService._round_metric(edge_length),
            ),
            CatalogEstimateComponent(
                code="hardware",
                name="Hardware set",
                amount=hardware_cost,
                unit="set",
                quantity=quantity,
            ),
            CatalogEstimateComponent(
                code="work",
                name="Production work",
                amount=work_cost,
                unit="job",
                quantity=quantity,
            ),
        ]

        subtotal = sum((item.amount for item in components), Decimal("0"))
        final_amount = TemplateService._round_money(subtotal * definition.markup_coefficient)
        area_sqm = TemplateService._round_metric(visible_area)
        material_area_sqm = TemplateService._round_metric(board_area)
        edge_length_m = TemplateService._round_metric(edge_length)

        lead_preview_text = "\n".join(
            [
                f"Product: {definition.name}",
                f"Size: {payload.width}x{payload.height}x{payload.depth} mm",
                f"Quantity: {payload.quantity}",
                f"Visible area: {area_sqm} sqm",
                f"Material area: {material_area_sqm} sqm",
                f"Material: {material.name}",
                f"Estimated total: {final_amount} {get_settings().default_currency}",
            ]
        )

        return CatalogEstimateRead(
            product_code=definition.code,
            product_name=definition.name,
            material_code=material.code,
            material_name=material.name,
            width=payload.width,
            height=payload.height,
            depth=payload.depth,
            quantity=payload.quantity,
            area_sqm=area_sqm,
            material_area_sqm=material_area_sqm,
            edge_length_m=edge_length_m,
            subtotal=TemplateService._round_money(subtotal),
            final_amount=final_amount,
            currency=get_settings().default_currency,
            components=components,
            lead_preview_text=lead_preview_text,
        )

    @staticmethod
    def create_catalog_lead(
        db: Session,
        payload: CatalogLeadCreateRequest,
        acting_user_id: str | None = None,
    ) -> tuple[Lead, CatalogEstimateRead]:
        estimate = TemplateService.calculate_catalog_estimate(
            db,
            CatalogEstimateRequest(
                product_code=payload.product_code,
                width=payload.width,
                height=payload.height,
                depth=payload.depth,
                quantity=payload.quantity,
                material_code=payload.material_code,
            ),
        )
        # Тема и текст уходят прямо в интерфейс и в разговор с клиентом,
        # поэтому они на русском, как и весь остальной интерфейс.
        subject = f"Расчёт по справочнику: {estimate.product_name}"
        comment_line = f"\nКомментарий: {payload.comment}" if payload.comment else ""
        text = (
            f"{estimate.lead_preview_text}\n"
            f"Клиент: {payload.client_name or 'имя не указано'}\n"
            f"Телефон: {payload.phone or 'не указан'}"
            f"{comment_line}"
        )
        intake_payload = UnifiedLeadIn(
            source_channel=payload.source_channel,
            subject=subject,
            text=text,
            sender=UnifiedSenderIn(
                full_name=payload.client_name,
                phone=payload.phone,
                email=payload.email,
            ),
            raw_payload={
                "catalog_product_code": payload.product_code,
                "quantity": payload.quantity,
                "material_code": estimate.material_code,
                "estimate": estimate.model_dump(mode="json"),
                "comment": payload.comment,
            },
        )
        lead = LeadService.intake_lead(
            db,
            intake_payload,
            acting_user_id=acting_user_id,
        )
        InboxService.record_inbound_lead(db, intake_payload, lead, acting_user_id)
        return lead, estimate

    @staticmethod
    def get_film_cutting_options() -> FilmCuttingOptionsRead:
        return FilmCuttingOptionsRead(
            default_roll_width_mm=DEFAULT_FILM_ROLL_WIDTH_MM,
            default_trim_margin_mm=DEFAULT_FILM_TRIM_MARGIN_MM,
            colors=[
                FilmColorRead(code=item.code, name=item.name, finish=item.finish)
                for item in FILM_COLORS
            ],
            millings=[
                FilmMillingRead(
                    code=item.code,
                    name=item.name,
                    extra_margin_mm=item.extra_margin_mm,
                    description=item.description,
                )
                for item in FILM_MILLINGS
            ],
            catalog_items=[
                FilmCatalogItemRead(
                    code=item.code,
                    name=item.name,
                    description=item.description,
                    default_length_mm=item.default_length_mm,
                    default_width_mm=item.default_width_mm,
                    default_depth_mm=item.default_depth_mm,
                    default_quantity=item.default_quantity,
                    default_milling_code=item.default_milling_code,
                    default_color_code=item.default_color_code,
                )
                for item in FILM_CATALOG_ITEMS
            ],
        )

    @staticmethod
    def _validate_film_line(payload_line: Any) -> tuple[Any, Any, Any]:
        color = get_film_color(payload_line.color_code)
        if color is None:
            raise AppError(f"Film color '{payload_line.color_code}' not found")

        milling = get_film_milling(payload_line.milling_code)
        if milling is None:
            raise AppError(f"Film milling '{payload_line.milling_code}' not found")

        catalog_item = None
        if payload_line.catalog_item_code:
            catalog_item = get_film_catalog_item(payload_line.catalog_item_code)
            if catalog_item is None:
                raise AppError(f"Film catalog item '{payload_line.catalog_item_code}' not found")

        return color, milling, catalog_item

    @staticmethod
    def _build_film_preview_text(estimate: FilmCuttingEstimateRead) -> str:
        color_lines = [
            (
                f"- {item.color_name}: длина рулона ~ {item.estimated_roll_length_mm} мм, "
                f"площадь {item.estimated_roll_area_sqm} м2, отход {item.waste_percent}%"
            )
            for item in estimate.color_plans
        ]
        return "\n".join(
            [
                "Раскрой пленки менеджера",
                f"Позиций: {len(estimate.lines)}",
                f"Деталей: {estimate.total_details}",
                f"Полезная площадь: {estimate.total_net_area_sqm} м2",
                f"Площадь заготовок: {estimate.total_blank_area_sqm} м2",
                f"Оценка рулона: {estimate.estimated_roll_length_mm} мм / {estimate.estimated_roll_area_sqm} м2",
                f"Отход: {estimate.waste_area_sqm} м2 ({estimate.waste_percent}%)",
                "Цветовые планы:",
                *color_lines,
            ]
        )

    @staticmethod
    def calculate_film_cutting_estimate(
        payload: FilmCuttingEstimateRequest,
    ) -> FilmCuttingEstimateRead:
        line_reads: list[FilmCuttingLineRead] = []
        units_by_color: dict[str, list[dict[str, int | str]]] = {}

        total_details = 0
        total_net_area = Decimal("0")
        total_blank_area = Decimal("0")

        for index, line in enumerate(payload.lines, start=1):
            color, milling, catalog_item = TemplateService._validate_film_line(line)

            blank_margin_mm = line.depth_mm + payload.trim_margin_mm + milling.extra_margin_mm
            blank_length_mm = line.length_mm + (blank_margin_mm * 2)
            blank_width_mm = line.width_mm + (blank_margin_mm * 2)

            net_area = (
                Decimal(line.length_mm)
                * Decimal(line.width_mm)
                * Decimal(line.quantity)
                / Decimal("1000000")
            )
            blank_area = (
                Decimal(blank_length_mm)
                * Decimal(blank_width_mm)
                * Decimal(line.quantity)
                / Decimal("1000000")
            )
            source_name = line.name or (catalog_item.name if catalog_item else f"Деталь {index}")

            line_reads.append(
                FilmCuttingLineRead(
                    line_index=index,
                    catalog_item_code=line.catalog_item_code,
                    name=source_name,
                    length_mm=line.length_mm,
                    width_mm=line.width_mm,
                    quantity=line.quantity,
                    depth_mm=line.depth_mm,
                    milling_code=line.milling_code,
                    milling_name=milling.name,
                    color_code=line.color_code,
                    color_name=color.name,
                    net_area_sqm=TemplateService._round_metric(net_area),
                    blank_length_mm=blank_length_mm,
                    blank_width_mm=blank_width_mm,
                    blank_area_sqm=TemplateService._round_metric(blank_area),
                )
            )

            total_details += line.quantity
            total_net_area += net_area
            total_blank_area += blank_area

            for _ in range(line.quantity):
                across_width_mm = min(blank_length_mm, blank_width_mm)
                along_length_mm = max(blank_length_mm, blank_width_mm)
                if across_width_mm > payload.roll_width_mm:
                    raise AppError(
                        f"Blank '{source_name}' does not fit roll width {payload.roll_width_mm} mm"
                    )
                units_by_color.setdefault(line.color_code, []).append(
                    {
                        "line_index": index,
                        "source_name": source_name,
                        "across_width_mm": across_width_mm,
                        "along_length_mm": along_length_mm,
                    }
                )

        color_plans: list[FilmCuttingColorPlanRead] = []
        total_roll_length_mm = 0
        total_roll_area = Decimal("0")

        for color_code, units in units_by_color.items():
            units.sort(
                key=lambda item: (
                    int(item["along_length_mm"]),
                    int(item["across_width_mm"]),
                ),
                reverse=True,
            )

            rows: list[dict[str, Any]] = []
            for unit in units:
                placed = False
                for row in rows:
                    remaining_width = payload.roll_width_mm - row["used_width_mm"]
                    if int(unit["across_width_mm"]) <= remaining_width:
                        row["items"].append(unit)
                        row["used_width_mm"] += int(unit["across_width_mm"])
                        row["length_mm"] = max(row["length_mm"], int(unit["along_length_mm"]))
                        placed = True
                        break
                if not placed:
                    rows.append(
                        {
                            "length_mm": int(unit["along_length_mm"]),
                            "used_width_mm": int(unit["across_width_mm"]),
                            "items": [unit],
                        }
                    )

            y_offset = 0
            layout_rows: list[FilmCuttingLayoutRowRead] = []
            color_blank_area = Decimal("0")
            color_net_area = Decimal("0")
            item_count = len(units)
            related_lines = [line for line in line_reads if line.color_code == color_code]
            for line in related_lines:
                color_blank_area += line.blank_area_sqm
                color_net_area += line.net_area_sqm

            for row_index, row in enumerate(rows, start=1):
                x_offset = 0
                items: list[FilmCuttingLayoutItemRead] = []
                for unit in row["items"]:
                    items.append(
                        FilmCuttingLayoutItemRead(
                            line_index=int(unit["line_index"]),
                            source_name=str(unit["source_name"]),
                            x_mm=x_offset,
                            y_mm=y_offset,
                            length_mm=int(unit["along_length_mm"]),
                            width_mm=int(unit["across_width_mm"]),
                        )
                    )
                    x_offset += int(unit["across_width_mm"])

                layout_rows.append(
                    FilmCuttingLayoutRowRead(
                        row_index=row_index,
                        y_mm=y_offset,
                        length_mm=row["length_mm"],
                        used_width_mm=row["used_width_mm"],
                        remaining_width_mm=payload.roll_width_mm - row["used_width_mm"],
                        items=items,
                    )
                )
                y_offset += row["length_mm"]

            roll_length_mm = sum(row["length_mm"] for row in rows)
            roll_area = (
                Decimal(payload.roll_width_mm) * Decimal(roll_length_mm) / Decimal("1000000")
            )
            waste_area = max(roll_area - color_blank_area, Decimal("0"))
            waste_percent = (
                TemplateService._round_percent((waste_area / roll_area) * Decimal("100"))
                if roll_area > 0
                else Decimal("0.00")
            )

            color = get_film_color(color_code)
            color_plans.append(
                FilmCuttingColorPlanRead(
                    color_code=color_code,
                    color_name=color.name if color else color_code,
                    item_count=item_count,
                    net_area_sqm=TemplateService._round_metric(color_net_area),
                    blank_area_sqm=TemplateService._round_metric(color_blank_area),
                    estimated_roll_length_mm=roll_length_mm,
                    estimated_roll_area_sqm=TemplateService._round_metric(roll_area),
                    waste_area_sqm=TemplateService._round_metric(waste_area),
                    waste_percent=waste_percent,
                    layout_rows=layout_rows,
                )
            )
            total_roll_length_mm += roll_length_mm
            total_roll_area += roll_area

        total_waste_area = max(total_roll_area - total_blank_area, Decimal("0"))
        estimate = FilmCuttingEstimateRead(
            roll_width_mm=payload.roll_width_mm,
            trim_margin_mm=payload.trim_margin_mm,
            total_details=total_details,
            total_net_area_sqm=TemplateService._round_metric(total_net_area),
            total_blank_area_sqm=TemplateService._round_metric(total_blank_area),
            estimated_roll_length_mm=total_roll_length_mm,
            estimated_roll_area_sqm=TemplateService._round_metric(total_roll_area),
            waste_area_sqm=TemplateService._round_metric(total_waste_area),
            waste_percent=(
                TemplateService._round_percent(
                    (total_waste_area / total_roll_area) * Decimal("100")
                )
                if total_roll_area > 0
                else Decimal("0.00")
            ),
            lines=line_reads,
            color_plans=color_plans,
            lead_preview_text="",
        )
        estimate.lead_preview_text = TemplateService._build_film_preview_text(estimate)
        return estimate

    @staticmethod
    def create_film_cutting_lead(
        db: Session,
        payload: FilmCuttingLeadCreateRequest,
        acting_user_id: str | None = None,
    ) -> tuple[Lead, FilmCuttingEstimateRead]:
        estimate = TemplateService.calculate_film_cutting_estimate(
            FilmCuttingEstimateRequest(
                roll_width_mm=payload.roll_width_mm,
                trim_margin_mm=payload.trim_margin_mm,
                lines=payload.lines,
            )
        )
        subject = f"Раскрой пленки / {len(payload.lines)} поз."
        comment_line = f"\nКомментарий: {payload.comment}" if payload.comment else ""
        text = (
            f"{estimate.lead_preview_text}\n"
            f"Клиент: {payload.client_name or 'Не указан'}\n"
            f"Телефон: {payload.phone or 'Не указан'}"
            f"{comment_line}"
        )
        intake_payload = UnifiedLeadIn(
            source_channel=payload.source_channel,
            subject=subject,
            text=text,
            sender=UnifiedSenderIn(
                full_name=payload.client_name,
                phone=payload.phone,
                email=payload.email,
            ),
            raw_payload={
                "film_cutting_estimate": estimate.model_dump(mode="json"),
                "lines": [line.model_dump(mode="json") for line in payload.lines],
                "comment": payload.comment,
            },
        )
        lead = LeadService.intake_lead(db, intake_payload, acting_user_id=acting_user_id)
        InboxService.record_inbound_lead(db, intake_payload, lead, acting_user_id)
        return lead, estimate
