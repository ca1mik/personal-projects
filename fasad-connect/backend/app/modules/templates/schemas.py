from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.modules.production.schemas import MaterialRead
from app.modules.shared.schemas import ORMModel


class ProductTemplateCreate(BaseModel):
    code: str = Field(min_length=3, max_length=100)
    name: str
    category: str
    description: str | None = None
    is_active: bool = True
    formula_config_json: dict[str, Any] = Field(default_factory=dict)


class ProductTemplateRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    description: str | None
    is_active: bool
    formula_config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CatalogEstimateComponent(BaseModel):
    code: str
    name: str
    amount: Decimal
    unit: str
    quantity: Decimal


class CatalogProductRead(BaseModel):
    code: str
    name: str
    category: str
    template_code: str | None
    description: str
    bot_menu_label: str
    default_material_code: str
    requires_depth: bool
    min_width: int
    max_width: int
    min_height: int
    max_height: int
    min_depth: int
    max_depth: int
    bot_questions: list[str] = Field(default_factory=list)
    available_materials: list[MaterialRead] = Field(default_factory=list)


class CatalogEstimateRequest(BaseModel):
    product_code: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    depth: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1)
    material_code: str | None = None


class CatalogLeadCreateRequest(CatalogEstimateRequest):
    client_name: str | None = None
    phone: str | None = None
    email: str | None = None
    comment: str | None = None
    source_channel: str = "catalog_demo"


class CatalogEstimateRead(BaseModel):
    product_code: str
    product_name: str
    material_code: str
    material_name: str | None
    width: int
    height: int
    depth: int
    quantity: int
    area_sqm: Decimal
    material_area_sqm: Decimal
    edge_length_m: Decimal
    subtotal: Decimal
    final_amount: Decimal
    currency: str
    components: list[CatalogEstimateComponent] = Field(default_factory=list)
    lead_preview_text: str


class FilmColorRead(BaseModel):
    code: str
    name: str
    finish: str


class FilmMillingRead(BaseModel):
    code: str
    name: str
    extra_margin_mm: int
    description: str


class FilmCatalogItemRead(BaseModel):
    code: str
    name: str
    description: str
    default_length_mm: int
    default_width_mm: int
    default_depth_mm: int
    default_quantity: int
    default_milling_code: str
    default_color_code: str


class FilmCuttingLineIn(BaseModel):
    catalog_item_code: str | None = None
    name: str | None = None
    length_mm: int = Field(ge=1)
    width_mm: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1, le=10_000)
    depth_mm: int = Field(default=16, ge=0)
    milling_code: str
    color_code: str


class FilmCuttingEstimateRequest(BaseModel):
    roll_width_mm: int = Field(default=1400, ge=300)
    trim_margin_mm: int = Field(default=60, ge=0)
    lines: list[FilmCuttingLineIn] = Field(min_length=1, max_length=10_000)

    @model_validator(mode="after")
    def limit_total_details(self) -> FilmCuttingEstimateRequest:
        if sum(line.quantity for line in self.lines) > 10_000:
            raise ValueError("One cutting estimate may contain at most 10000 details")
        return self


class FilmCuttingLeadCreateRequest(FilmCuttingEstimateRequest):
    client_name: str | None = None
    phone: str | None = None
    email: str | None = None
    comment: str | None = None
    source_channel: str = "manager_film_cutting"


class FilmCuttingLineRead(BaseModel):
    line_index: int
    catalog_item_code: str | None
    name: str
    length_mm: int
    width_mm: int
    quantity: int
    depth_mm: int
    milling_code: str
    milling_name: str
    color_code: str
    color_name: str
    net_area_sqm: Decimal
    blank_length_mm: int
    blank_width_mm: int
    blank_area_sqm: Decimal


class FilmCuttingLayoutItemRead(BaseModel):
    line_index: int
    source_name: str
    x_mm: int
    y_mm: int
    length_mm: int
    width_mm: int


class FilmCuttingLayoutRowRead(BaseModel):
    row_index: int
    y_mm: int
    length_mm: int
    used_width_mm: int
    remaining_width_mm: int
    items: list[FilmCuttingLayoutItemRead] = Field(default_factory=list)


class FilmCuttingColorPlanRead(BaseModel):
    color_code: str
    color_name: str
    item_count: int
    net_area_sqm: Decimal
    blank_area_sqm: Decimal
    estimated_roll_length_mm: int
    estimated_roll_area_sqm: Decimal
    waste_area_sqm: Decimal
    waste_percent: Decimal
    layout_rows: list[FilmCuttingLayoutRowRead] = Field(default_factory=list)


class FilmCuttingOptionsRead(BaseModel):
    default_roll_width_mm: int
    default_trim_margin_mm: int
    colors: list[FilmColorRead] = Field(default_factory=list)
    millings: list[FilmMillingRead] = Field(default_factory=list)
    catalog_items: list[FilmCatalogItemRead] = Field(default_factory=list)


class FilmCuttingEstimateRead(BaseModel):
    roll_width_mm: int
    trim_margin_mm: int
    total_details: int
    total_net_area_sqm: Decimal
    total_blank_area_sqm: Decimal
    estimated_roll_length_mm: int
    estimated_roll_area_sqm: Decimal
    waste_area_sqm: Decimal
    waste_percent: Decimal
    lines: list[FilmCuttingLineRead] = Field(default_factory=list)
    color_plans: list[FilmCuttingColorPlanRead] = Field(default_factory=list)
    lead_preview_text: str
