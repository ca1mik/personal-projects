from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, get_page_params
from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.leads.schemas import LeadRead
from app.modules.shared.schemas import Envelope
from app.modules.templates.schemas import (
    CatalogEstimateRead,
    CatalogEstimateRequest,
    CatalogLeadCreateRequest,
    CatalogProductRead,
    FilmCuttingEstimateRead,
    FilmCuttingEstimateRequest,
    FilmCuttingLeadCreateRequest,
    FilmCuttingOptionsRead,
    ProductTemplateCreate,
    ProductTemplateRead,
)
from app.modules.templates.service import TemplateService
from app.modules.users.models import User

router = APIRouter()

# Каталог и калькуляторы — рабочий инструмент того, кто называет клиенту цену:
# менеджер по заявке, технолог по заказу. Смотреть каталог можно многим, менять
# справочник изделий — только технологу.
CATALOG_READ = ("templates.manage", "orders.manage", "leads.manage")
TEMPLATES_WRITE = ("templates.manage",)
# Заявка из калькулятора — это уже приём заявки, а не расчёт.
LEADS_WRITE = ("leads.manage",)


@router.get("", response_model=Envelope[list[ProductTemplateRead]])
def list_templates(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CATALOG_READ))],
    params: Annotated[PageParams, Depends(get_page_params)],
) -> dict[str, object]:
    templates, meta = TemplateService.list_templates(db, params)
    return envelope([ProductTemplateRead.model_validate(item) for item in templates], meta)


@router.post("", response_model=Envelope[ProductTemplateRead])
def create_template(
    payload: ProductTemplateCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*TEMPLATES_WRITE))],
) -> dict[str, object]:
    template = TemplateService.create_template(db, payload)
    return envelope(ProductTemplateRead.model_validate(template))


@router.get("/catalog", response_model=Envelope[list[CatalogProductRead]])
def list_catalog(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CATALOG_READ))],
) -> dict[str, object]:
    return envelope(TemplateService.list_catalog(db))


@router.post("/catalog/estimate", response_model=Envelope[CatalogEstimateRead])
def calculate_catalog_estimate(
    payload: CatalogEstimateRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*CATALOG_READ))],
) -> dict[str, object]:
    return envelope(TemplateService.calculate_catalog_estimate(db, payload))


@router.post("/catalog/lead", response_model=Envelope[LeadRead])
def create_catalog_lead(
    payload: CatalogLeadCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*LEADS_WRITE))],
) -> dict[str, object]:
    lead, _ = TemplateService.create_catalog_lead(db, payload, str(current_user.id))
    return envelope(LeadRead.model_validate(lead))


@router.get("/film-cutting/options", response_model=Envelope[FilmCuttingOptionsRead])
def get_film_cutting_options(
    _: Annotated[User, Depends(require_permissions(*CATALOG_READ, "production.manage"))],
) -> dict[str, object]:
    return envelope(TemplateService.get_film_cutting_options())


@router.post("/film-cutting/estimate", response_model=Envelope[FilmCuttingEstimateRead])
def calculate_film_cutting_estimate(
    payload: FilmCuttingEstimateRequest,
    _: Annotated[User, Depends(require_permissions(*CATALOG_READ, "production.manage"))],
) -> dict[str, object]:
    return envelope(TemplateService.calculate_film_cutting_estimate(payload))


@router.post("/film-cutting/lead", response_model=Envelope[LeadRead])
def create_film_cutting_lead(
    payload: FilmCuttingLeadCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*LEADS_WRITE))],
) -> dict[str, object]:
    lead, _ = TemplateService.create_film_cutting_lead(db, payload, str(current_user.id))
    return envelope(LeadRead.model_validate(lead))
