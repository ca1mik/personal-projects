from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .auth import SessionStore
from .config import PROJECT_ROOT, get_settings
from .monitor import MonitoringService
from .schemas import StartMonitoringRequest


def create_app() -> FastAPI:
    settings = get_settings()
    session_store = SessionStore()
    monitoring_service = MonitoringService(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.sessions = session_store
        app.state.monitoring_service = monitoring_service
        app.state.settings = settings
        try:
            yield
        finally:
            await monitoring_service.shutdown()

    app = FastAPI(title="Tinkoff Stock Monitor MVP", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

    def current_user(request: Request) -> str | None:
        cookie_name = settings.session_cookie_name
        return session_store.get(request.cookies.get(cookie_name))

    def ensure_user(request: Request) -> str:
        user = current_user(request)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user

    def dashboard_defaults() -> dict[str, str | int]:
        state = monitoring_service.snapshot()["settings"]
        return {
            "tickers": ", ".join(state["tickers"]),
            "change_percent": state["change_percent"],
            "window_minutes": state["window_minutes"],
            "rollback_percent": state["rollback_percent"],
        }

    @app.get("/", response_class=HTMLResponse)
    async def login_page(request: Request) -> Response:
        if current_user(request):
            return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)

        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": None,
                "default_login": settings.app_login,
                "default_password": settings.app_password,
            },
        )

    @app.post("/login", response_class=HTMLResponse)
    async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ) -> Response:
        if username != settings.app_login or password != settings.app_password:
            return templates.TemplateResponse(
                request,
                "login.html",
                {
                    "error": "Неверный логин или пароль.",
                    "default_login": settings.app_login,
                    "default_password": settings.app_password,
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        session_id = session_store.create(username)
        response = RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            settings.session_cookie_name,
            session_id,
            httponly=True,
            samesite="lax",
            secure=settings.cookie_secure,
        )
        return response

    @app.get("/logout")
    async def logout(request: Request) -> Response:
        session_store.delete(request.cookies.get(settings.session_cookie_name))
        response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(settings.session_cookie_name)
        return response

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request) -> Response:
        user = current_user(request)
        if user is None:
            return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "username": user,
                "defaults": dashboard_defaults(),
            },
        )

    @app.get("/api/state")
    async def api_state(request: Request) -> JSONResponse:
        ensure_user(request)
        return JSONResponse(monitoring_service.snapshot())

    @app.get("/api/stream")
    async def api_stream(request: Request) -> StreamingResponse:
        ensure_user(request)

        async def event_generator():
            while True:
                if await request.is_disconnected():
                    break
                payload = json.dumps(monitoring_service.snapshot(), ensure_ascii=False)
                yield f"event: state\ndata: {payload}\n\n"
                await asyncio.sleep(1)

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)

    @app.post("/api/start")
    async def api_start(request: Request, body: StartMonitoringRequest) -> JSONResponse:
        ensure_user(request)
        await monitoring_service.start_monitoring(body)
        return JSONResponse({"ok": True, "state": monitoring_service.snapshot()})

    @app.post("/api/stop")
    async def api_stop(request: Request) -> JSONResponse:
        ensure_user(request)
        await monitoring_service.stop_monitoring()
        return JSONResponse({"ok": True, "state": monitoring_service.snapshot()})

    return app
