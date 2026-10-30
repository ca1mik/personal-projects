from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.app.config import get_settings
from apps.api.app.errors import AppError
from apps.api.app.routers.health import router as health_router
from apps.api.app.routers.jobs import router as jobs_router
from apps.api.app.storage import ensure_storage_dirs


settings = get_settings()
app = FastAPI(title="Enya Local 3D Studio API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.web_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    ensure_storage_dirs()


@app.exception_handler(AppError)
async def app_error_handler(_, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": exc.errors()[0]["msg"] if exc.errors() else "Validation failed.",
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
            },
        },
    )


app.include_router(health_router)
app.include_router(jobs_router)

