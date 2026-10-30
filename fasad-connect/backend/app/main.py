from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.intake_guard import IntakeGuard
from app.core.responses import envelope
from app.db.session import SessionLocal
from app.modules.audit.middleware import AuditContextMiddleware

settings = get_settings()

# Только у портативной сборки: см. app/core/license.py. Обычная разработка и
# docker-прод не ставят LICENSE_LOCK_ENABLED, поэтому сюда даже не заходят —
# импорт license.py тоже происходит только здесь, чтобы Windows-специфичный
# код внутри него не мешал импортировать app.main на Linux.
if settings.license_lock_enabled:
    from app.core.license import enforce_or_exit

    enforce_or_exit(settings.license_file_path)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditContextMiddleware)
app.add_middleware(IntakeGuard)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.message}})


@app.get("/health")
def healthcheck() -> dict[str, object]:
    db_ok = True
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "database": "ok" if db_ok else "error",
    }


@app.get("/")
def root() -> dict[str, object]:
    return envelope({"service": settings.app_name, "docs": "/docs"})
