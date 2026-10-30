from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from decimal import InvalidOperation
from html import escape
from typing import Any

from aiogram import Bot
from aiohttp import web

from .config import Config
from .db import Database
from .google_crm import resolve_crm_settings, sync_crm_spreadsheet
from .robokassa import amount_to_minor_units, verify_result_signature, verify_success_signature

# Статусы заявок для CRM-воронки
CRM_STATUS_ORDER = ["new", "contacted", "consultation", "waiting_reply", "confirmed", "deposit", "done", "archive"]
CRM_STATUS_LABELS = {
    "new": "Новая",
    "contacted": "Связались",
    "consultation": "Консультация",
    "waiting_reply": "Ждём ответа",
    "confirmed": "Подтверждена",
    "deposit": "Предоплата",
    "done": "Сделано",
    "archive": "Архив",
}

WEBSITE_ALLOWED_ORIGINS = {
    "https://www.ppdstr.ru",
    "https://ppdstr.ru",
    "http://www.ppdstr.ru",
    "http://ppdstr.ru",
    "http://127.0.0.1:8812",
    "http://localhost:8812",
    "http://127.0.0.1:8820",
    "http://localhost:8820",
}

WEBSITE_STYLE_LABELS = {
    "lettering": "Надпись",
    "minimal": "Минимализм",
    "graphics": "Графика",
    "color": "Цвет",
    "characters": "Персонажи / аниме",
}

WEBSITE_SIZE_LABELS = {
    "xs": "до 5 см",
    "s": "5–10 см",
    "m": "10–15 см",
    "l": "15–20 см",
    "xl": "20+ см",
}

WEBSITE_PLACEMENT_LABELS = {
    "wrist": "запястье",
    "forearm": "предплечье",
    "shoulder": "плечо",
    "thigh": "бедро",
    "rib": "рёбра",
    "ankle": "голень / щиколотка",
    "back": "спина",
    "other": "другое место",
}

WEBSITE_COLOR_LABELS = {
    "mono": "черно-белая",
    "accent": "1 цветной акцент",
    "duo": "2–3 цвета",
    "full": "плотный цвет",
}

WEBSITE_COMPLEXITY_LABELS = {
    "basic": "базовая",
    "medium": "средняя",
    "high": "высокая",
    "max": "сложная композиция",
}

REQUEST_NOTIFY_TIMEOUT_SECONDS = 5
REQUEST_CRM_TIMEOUT_SECONDS = 15


def _collect_shp(params: Mapping[str, str]) -> dict[str, str]:
    return {key: value for key, value in params.items() if key.startswith("Shp_")}


def _html_page(title: str, body: str) -> str:
    return (
        "<!doctype html>"
        "<html lang='ru'>"
        "<head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)}</title>"
        "<style>"
        "body{font-family:system-ui,-apple-system,sans-serif;background:#111;color:#f5f3ef;"
        "margin:0;padding:32px;line-height:1.5}"
        ".card{max-width:720px;margin:0 auto;padding:24px;border:1px solid #2f2a24;border-radius:20px;"
        "background:#171512}"
        "a{color:#f0b35b}"
        "code{background:#211d19;padding:2px 6px;border-radius:6px}"
        "</style></head>"
        f"<body><div class='card'><h1>{escape(title)}</h1>{body}</div></body></html>"
    )


async def _request_params(request: web.Request) -> dict[str, str]:
    if request.method == "POST":
        data = await request.post()
        return {key: str(value) for key, value in data.items()}
    return {key: str(value) for key, value in request.query.items()}


def _cors_headers(request: web.Request) -> dict[str, str]:
    origin = request.headers.get("Origin", "").strip()
    headers = {"Vary": "Origin"}
    if origin and origin in WEBSITE_ALLOWED_ORIGINS:
        headers.update(
            {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "86400",
            }
        )
    return headers


def _json_response(request: web.Request, payload: Mapping[str, Any], *, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(payload, ensure_ascii=False),
        status=status,
        content_type="application/json",
        headers=_cors_headers(request),
    )


def _contact_channel(contact: str) -> str:
    text = (contact or "").strip().lower()
    if text.startswith("@") or "t.me/" in text or "telegram" in text:
        return "Telegram"
    if "vk.com" in text or text.startswith("vk") or "вк" in text:
        return "VK"
    if "wa.me" in text or "whatsapp" in text or text.startswith("+7") or text.startswith("8") or any(ch.isdigit() for ch in text):
        return "Телефон / WhatsApp"
    return "Свободный контакт"


def _label_or_map(raw_label: Any, raw_value: Any, labels_map: Mapping[str, str]) -> str:
    label = str(raw_label or "").strip()
    if label:
        return label
    value = str(raw_value or "").strip()
    return labels_map.get(value, value)


async def build_robokassa_app(cfg: Config, db: Database, bot: Bot | None) -> web.Application:
    app = web.Application()
    background_tasks: set[asyncio.Task[Any]] = set()

    def schedule_background(coro: Any) -> None:
        task = asyncio.create_task(coro)
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)


    async def notify_admin(message: str) -> None:
        if bot is None or not cfg.admin_chat_id:
            return
        try:
            await asyncio.wait_for(
                bot.send_message(cfg.admin_chat_id, message),
                timeout=REQUEST_NOTIFY_TIMEOUT_SECONDS,
            )
        except Exception:  # noqa: BLE001
            return

    async def sync_booking_followups(booking_id: int, admin_message: str) -> tuple[bool, str]:
        await notify_admin(admin_message)

        try:
            settings = resolve_crm_settings(cfg)
            if not settings.spreadsheet_ready:
                return False, "CRM не настроена в bot/.env."

            await asyncio.wait_for(
                asyncio.to_thread(sync_crm_spreadsheet, settings),
                timeout=REQUEST_CRM_TIMEOUT_SECONDS,
            )
            return True, ""
        except Exception as error:  # noqa: BLE001
            crm_error = str(error)
            await notify_admin(
                "CRM sync error\n"
                f"Заявка #{booking_id}\n"
                f"{escape(crm_error)}"
            )
            return False, crm_error

    async def health(_: web.Request) -> web.Response:
        return web.json_response(
            {
                "ok": True,
                "merchant": bool(cfg.robokassa.merchant_login),
                "callbacks_ready": cfg.robokassa.callback_urls_ready,
            }
        )

    # --- CRM API эндпоинты ---

    async def crm_options(request: web.Request) -> web.Response:
        headers = _cors_headers(request)
        if request.headers.get("Origin", "").strip() and "Access-Control-Allow-Origin" not in headers:
            raise web.HTTPForbidden(text="Origin is not allowed.")
        return web.Response(status=204, headers=headers)

    async def crm_stats(request: web.Request) -> web.Response:
        """GET /api/crm-stats — воронка, конверсия, follow-up."""
        try:
            stats = await db.get_crm_stats()
        except Exception as error:  # noqa: BLE001
            return _json_response(request, {"ok": False, "error": str(error)}, status=500)

        total = stats.total
        done_count = stats.status_counts.get("done", 0)
        deposit_count = stats.status_counts.get("deposit", 0)
        contacted_count = stats.status_counts.get("contacted", 0) + stats.status_counts.get("consultation", 0)

        def pct(part: int, base: int) -> str:
            return f"{round(part / base * 100)}%" if base > 0 else "0%"

        funnel = [
            {
                "status": s,
                "label": CRM_STATUS_LABELS.get(s, s),
                "count": stats.status_counts.get(s, 0),
                "pct": pct(stats.status_counts.get(s, 0), total),
            }
            for s in CRM_STATUS_ORDER
        ]

        return _json_response(request, {
            "ok": True,
            "total": total,
            "funnel": funnel,
            "conversion": {
                "contacted_pct": pct(contacted_count, total),
                "deposit_pct": pct(deposit_count, total),
                "done_pct": pct(done_count, total),
            },
            "stale_count": len(stats.stale_leads),
            "stale_leads": stats.stale_leads,
        })

    async def crm_leads(request: web.Request) -> web.Response:
        """GET /api/crm-leads — последние лиды."""
        try:
            limit_str = request.rel_url.query.get("limit", "50")
            limit = min(int(limit_str), 200)
        except ValueError:
            limit = 50
        try:
            leads = await db.list_booking_requests(limit=limit)
        except Exception as error:  # noqa: BLE001
            return _json_response(request, {"ok": False, "error": str(error)}, status=500)

        return _json_response(request, {
            "ok": True,
            "leads": [
                {
                    "id": lead.request_id,
                    "status": lead.status,
                    "status_label": CRM_STATUS_LABELS.get(lead.status, lead.status),
                    "created_at": lead.created_at,
                    "status_updated_at": lead.status_updated_at,
                    "name": lead.full_name or lead.username or f"user {lead.user_id}",
                    "contact": lead.contact,
                    "idea": lead.idea,
                    "size": lead.size,
                    "placement": lead.placement,
                    "source": lead.source,
                }
                for lead in leads
            ],
        })

    async def crm_payments(request: web.Request) -> web.Response:
        """GET /api/crm-payments — последние платежи."""
        try:
            payments = await db.list_payments_for_crm(limit=50)
        except Exception as error:  # noqa: BLE001
            return _json_response(request, {"ok": False, "error": str(error)}, status=500)

        total_paid = sum(p.amount_rub for p in payments if p.status == "paid")
        return _json_response(request, {
            "ok": True,
            "total_paid_rub": total_paid,
            "payments": [
                {
                    "id": p.payment_id,
                    "channel": p.channel,
                    "offer_title": p.offer_title,
                    "amount_rub": p.amount_rub,
                    "status": p.status,
                    "paid_at": p.paid_at,
                    "created_at": p.created_at,
                }
                for p in payments
            ],
        })

    async def crm_sync_endpoint(request: web.Request) -> web.Response:
        """POST /api/crm-sync — запускает CRM sync в фоне."""
        if request.headers.get("Origin", "").strip() and "Access-Control-Allow-Origin" not in _cors_headers(request):
            raise web.HTTPForbidden(text="Origin is not allowed.")
        try:
            settings = resolve_crm_settings(cfg)
            if not settings.spreadsheet_ready:
                return _json_response(request, {"ok": False, "error": "CRM не настроена в bot/.env."}, status=503)
            schedule_background(asyncio.to_thread(sync_crm_spreadsheet, settings))
            return _json_response(request, {"ok": True, "message": "CRM sync запущен в фоне"})
        except Exception as error:  # noqa: BLE001
            return _json_response(request, {"ok": False, "error": str(error)}, status=500)

    async def booking_status_update(request: web.Request) -> web.Response:
        """POST /api/booking-status — меняет статус заявки."""
        if request.headers.get("Origin", "").strip() and "Access-Control-Allow-Origin" not in _cors_headers(request):
            raise web.HTTPForbidden(text="Origin is not allowed.")
        try:
            payload = await request.json()
        except (json.JSONDecodeError, ValueError):
            return _json_response(request, {"ok": False, "error": "invalid_json"}, status=400)

        request_id = payload.get("request_id")
        status = str(payload.get("status", "")).strip()
        if not isinstance(request_id, int) or not status:
            return _json_response(request, {"ok": False, "error": "Нужны request_id (число) и status"}, status=400)
        if status not in CRM_STATUS_ORDER:
            return _json_response(
                request,
                {"ok": False, "error": f"Неизвестный статус: {status}"},
                status=400,
            )

        updated = await db.update_booking_request_status(request_id, status)
        if not updated:
            return _json_response(request, {"ok": False, "error": f"Заявка #{request_id} не найдена"}, status=404)

        # Автосинх CRM в фоне
        settings = resolve_crm_settings(cfg)
        if settings.spreadsheet_ready:
            schedule_background(asyncio.to_thread(sync_crm_spreadsheet, settings))

        return _json_response(request, {
            "ok": True,
            "request_id": request_id,
            "status": status,
            "status_label": CRM_STATUS_LABELS.get(status, status),
        })

    async def booking_request_options(request: web.Request) -> web.Response:
        headers = _cors_headers(request)
        if request.headers.get("Origin", "").strip() and "Access-Control-Allow-Origin" not in headers:
            raise web.HTTPForbidden(text="Origin is not allowed.")
        return web.Response(status=204, headers=headers)

    async def booking_request_submit(request: web.Request) -> web.Response:
        if request.headers.get("Origin", "").strip() and "Access-Control-Allow-Origin" not in _cors_headers(request):
            raise web.HTTPForbidden(text="Origin is not allowed.")

        try:
            raw_payload = await request.json()
        except (json.JSONDecodeError, ValueError):
            return _json_response(
                request,
                {"ok": False, "error": "invalid_json", "message": "Не удалось прочитать JSON заявки."},
                status=400,
            )

        if not isinstance(raw_payload, Mapping):
            return _json_response(
                request,
                {"ok": False, "error": "invalid_payload", "message": "Неверный формат данных заявки."},
                status=400,
            )

        name = str(raw_payload.get("name", "")).strip()
        contact = str(raw_payload.get("contact", "")).strip()
        idea = str(raw_payload.get("idea", "")).strip()
        comment = str(raw_payload.get("comment", "")).strip()
        consent = bool(raw_payload.get("consent"))
        calc = raw_payload.get("calc") if isinstance(raw_payload.get("calc"), Mapping) else {}
        selected_work = raw_payload.get("selectedWork") if isinstance(raw_payload.get("selectedWork"), Mapping) else {}

        if not all((contact, idea)) or not consent:
            return _json_response(
                request,
                {
                    "ok": False,
                    "error": "validation_failed",
                    "message": "Нужны контакт, идея и согласие с обработкой данных.",
                },
                status=400,
            )

        if not name:
            name = "Без имени"

        style_label = _label_or_map(calc.get("styleLabel"), calc.get("style"), WEBSITE_STYLE_LABELS)
        size_label = _label_or_map(calc.get("sizeLabel"), calc.get("size"), WEBSITE_SIZE_LABELS)
        placement_label = _label_or_map(calc.get("placementLabel"), calc.get("placement"), WEBSITE_PLACEMENT_LABELS)
        color_label = _label_or_map(calc.get("colorLabel"), calc.get("color"), WEBSITE_COLOR_LABELS)
        complexity_label = _label_or_map(calc.get("complexityLabel"), calc.get("complexity"), WEBSITE_COMPLEXITY_LABELS)
        has_sketch_label = str(calc.get("hasSketchLabel", "")).strip()
        first_tattoo_label = str(calc.get("firstTattooLabel", "")).strip()
        hours_label = str(calc.get("hoursLabel", "")).strip()
        materials_label = str(calc.get("materialsLabel", "")).strip()
        price_range = str(calc.get("priceRange", "")).strip()
        selected_work_title = str(selected_work.get("title", "")).strip()
        selected_work_price = str(selected_work.get("price", "")).strip()

        details_payload = {
            "channel": "website-form",
            "contact_channel": _contact_channel(contact),
            "comment": comment,
            "style_label": style_label,
            "size_label": size_label,
            "placement_label": placement_label,
            "color_label": color_label,
            "complexity_label": complexity_label,
            "has_sketch_label": has_sketch_label,
            "first_tattoo_label": first_tattoo_label,
            "hours_label": hours_label,
            "calc_price_range": price_range,
            "calc_materials_label": materials_label,
            "selected_work_id": str(selected_work.get("id", "")).strip(),
            "selected_work_title": selected_work_title,
            "selected_work_note": selected_work_price,
            "draft_text": str(raw_payload.get("draftText", "")).strip(),
            "followup_hint": "Референсы можно дослать в личные сообщения после открытия чата.",
        }

        booking = await db.create_booking_request(
            user_id=0,
            username=None,
            full_name=name,
            idea=idea,
            size=size_label or "уточнить",
            placement=placement_label or "уточнить",
            preferred_date=comment or "сайт: время не указано",
            contact=contact,
            status="new",
            source="website-form",
            details_json=json.dumps(details_payload, ensure_ascii=False),
        )

        calc_line = f"{price_range or 'ориентир уточнить'} · {hours_label or 'время уточнить'}"
        params_line = ", ".join(
            part for part in (style_label, size_label, placement_label, color_label, complexity_label) if part
        ) or "уточнить"
        work_line = (
            f"\nПохожая работа: {escape(selected_work_title)} ({escape(selected_work_price)})"
            if selected_work_title
            else ""
        )
        comment_line = f"\nКогда удобно / комментарий: {escape(comment)}" if comment else ""
        sketch_line = f"\nЭскиз: {escape(has_sketch_label)}" if has_sketch_label else ""
        first_tattoo_line = f"\nПервая татуировка: {escape(first_tattoo_label)}" if first_tattoo_label else ""

        admin_message = (
            "<b>Новая заявка с сайта</b>\n"
            f"Заявка: <b>#{booking.request_id}</b>\n"
            f"Имя: {escape(name)}\n"
            f"Контакт: {escape(contact)}\n"
            f"Идея: {escape(idea)}\n"
            f"Параметры: {escape(params_line)}\n"
            f"Расчет: {escape(calc_line)}"
            f"{sketch_line}"
            f"{first_tattoo_line}"
            f"{work_line}"
            f"{comment_line}"
        )
        crm_ready = resolve_crm_settings(cfg).spreadsheet_ready
        schedule_background(sync_booking_followups(booking.request_id, admin_message))

        return _json_response(
            request,
            {
                "ok": True,
                "request_id": booking.request_id,
                "crm_synced": False,
                "crm_pending": crm_ready,
                "crm_error": "" if crm_ready else "CRM не настроена в bot/.env.",
            },
            status=201,
        )

    async def result(request: web.Request) -> web.Response:
        params = await _request_params(request)
        invoice_id_text = params.get("InvId", "").strip()
        out_sum_text = params.get("OutSum", "").strip()
        signature = params.get("SignatureValue", "").strip()
        if not invoice_id_text or not out_sum_text or not signature:
            raise web.HTTPBadRequest(text="Missing Robokassa callback fields.")

        try:
            invoice_id = int(invoice_id_text)
            out_sum_minor = amount_to_minor_units(out_sum_text)
        except (ValueError, InvalidOperation) as error:
            raise web.HTTPBadRequest(text="Invalid invoice or amount.") from error

        invoice = await db.get_robokassa_invoice(invoice_id)
        if invoice is None:
            raise web.HTTPNotFound(text="Invoice not found.")

        shp = _collect_shp(params)
        expected_shp = {}
        if invoice.shp_json:
            import json

            expected_shp = json.loads(invoice.shp_json)

        if expected_shp and shp != expected_shp:
            raise web.HTTPBadRequest(text="Shp parameters mismatch.")

        if not verify_result_signature(
            cfg.robokassa,
            signature=signature,
            out_sum=out_sum_text,
            invoice_id=invoice_id,
            shp=shp,
        ):
            raise web.HTTPForbidden(text="Invalid signature.")

        result = await db.apply_robokassa_result(
            invoice_id=invoice_id,
            out_sum_minor=out_sum_minor,
            currency="RUB",
            email=params.get("EMail") or None,
            payment_method=params.get("IncCurrLabel") or None,
            op_key=params.get("OpKey") or None,
            callback_payload=params,
        )
        if result.applied:
            await notify_admin(
                "Новая оплата через Robokassa\n"
                f"InvId: {invoice_id}\n"
                f"Сценарий: {invoice.offer_title}\n"
                f"Сумма: {invoice.amount_rub} ₽\n"
                f"Email: {params.get('EMail') or 'не указан'}"
            )
        return web.Response(text=f"OK{invoice_id}")

    async def success(request: web.Request) -> web.Response:
        params = await _request_params(request)
        invoice_id_text = params.get("InvId", "").strip()
        out_sum_text = params.get("OutSum", "").strip()
        signature = params.get("SignatureValue", "").strip()
        shp = _collect_shp(params)

        verified = False
        if invoice_id_text and out_sum_text and signature:
            try:
                invoice_id = int(invoice_id_text)
            except ValueError:
                invoice_id = None
            else:
                verified = verify_success_signature(
                    cfg.robokassa,
                    signature=signature,
                    out_sum=out_sum_text,
                    invoice_id=invoice_id,
                    shp=shp,
                )

        title = "Оплата принята" if verified else "Платеж обрабатывается"
        body = (
            "<p>Спасибо. Если платеж уже оплачен, бот и база получат подтверждение через ResultURL.</p>"
            f"<p>Проверь сообщение в Telegram и при необходимости открой чат с ботом снова.</p>"
            f"<p>InvId: <code>{escape(invoice_id_text or 'не указан')}</code></p>"
        )
        return web.Response(text=_html_page(title, body), content_type="text/html")

    async def fail(request: web.Request) -> web.Response:
        params = await _request_params(request)
        invoice_id_text = params.get("InvId", "").strip()
        body = (
            "<p>Платеж не завершен или пользователь вернулся со страницы оплаты без подтверждения.</p>"
            "<p>Можно вернуться в бот и открыть оплату заново.</p>"
            f"<p>InvId: <code>{escape(invoice_id_text or 'не указан')}</code></p>"
        )
        return web.Response(text=_html_page("Оплата не завершена", body), content_type="text/html")

    app.router.add_get("/robokassa/health", health)
    app.router.add_route("OPTIONS", "/api/booking-request", booking_request_options)
    app.router.add_post("/api/booking-request", booking_request_submit)
    app.router.add_route("*", "/robokassa/result", result)
    app.router.add_route("*", "/robokassa/success", success)
    app.router.add_route("*", "/robokassa/fail", fail)
    # CRM API эндпоинты
    app.router.add_route("OPTIONS", "/api/crm-stats", crm_options)
    app.router.add_route("OPTIONS", "/api/crm-leads", crm_options)
    app.router.add_route("OPTIONS", "/api/crm-payments", crm_options)
    app.router.add_route("OPTIONS", "/api/crm-sync", crm_options)
    app.router.add_route("OPTIONS", "/api/booking-status", crm_options)
    app.router.add_get("/api/crm-stats", crm_stats)
    app.router.add_get("/api/crm-leads", crm_leads)
    app.router.add_get("/api/crm-payments", crm_payments)
    app.router.add_post("/api/crm-sync", crm_sync_endpoint)
    app.router.add_post("/api/booking-status", booking_status_update)
    return app


async def start_robokassa_server(cfg: Config, db: Database, bot: Bot | None) -> web.AppRunner:
    app = await build_robokassa_app(cfg, db, bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=cfg.robokassa.bind_host, port=cfg.robokassa.bind_port)
    await site.start()
    return runner
