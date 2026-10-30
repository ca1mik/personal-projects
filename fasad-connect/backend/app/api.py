from __future__ import annotations

from fastapi import APIRouter

from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.clients.router import router as clients_router
from app.modules.cnc.router import router as cnc_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.directions.router import router as directions_router
from app.modules.documents.router import router as documents_router
from app.modules.imports.router import router as imports_router
from app.modules.leads.router import router as leads_router
from app.modules.messaging.router import router as messaging_router
from app.modules.orders.router import router as orders_router
from app.modules.price_book.router import router as price_book_router
from app.modules.production.router import router as production_router
from app.modules.reference_values.router import router as reference_values_router
from app.modules.reports.router import router as reports_router
from app.modules.stock.router import router as stock_router
from app.modules.templates.router import router as templates_router
from app.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, tags=["admin"])
api_router.include_router(clients_router, prefix="/clients", tags=["clients"])
api_router.include_router(cnc_router)
api_router.include_router(directions_router, tags=["directions"])
api_router.include_router(leads_router, prefix="/leads", tags=["leads"])
api_router.include_router(messaging_router, prefix="/messaging", tags=["messaging"])
api_router.include_router(orders_router, prefix="/orders", tags=["orders"])
api_router.include_router(templates_router, prefix="/templates", tags=["templates"])
api_router.include_router(production_router, tags=["materials"])
api_router.include_router(stock_router, prefix="/stock", tags=["stock"])
api_router.include_router(reports_router, tags=["reports"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(audit_router, tags=["admin"])
api_router.include_router(imports_router, tags=["imports"])
api_router.include_router(price_book_router, tags=["price-book"])
api_router.include_router(reference_values_router, tags=["reference-values"])
api_router.include_router(documents_router)
