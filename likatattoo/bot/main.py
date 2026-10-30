from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.config import ConfigError, load_config
from app.db import Database
from app.google_crm import provision_crm_workspace, resolve_crm_settings, sync_crm_spreadsheet
from app.handlers import build_router
from app.openai_service import TattooSketchService
from app.robokassa_web import start_robokassa_server


async def configure_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="myid", description="Мой Telegram ID"),
            BotCommand(command="booking", description="Оставить заявку"),
            BotCommand(command="generate", description="Генерация эскиза"),
            BotCommand(command="chatgpt", description="Prompt для ChatGPT"),
            BotCommand(command="examples", description="Примеры работ"),
            BotCommand(command="prices", description="Прайс"),
            BotCommand(command="deposit", description="Оплата и бронь"),
            BotCommand(command="portfolio", description="Портфолио-акция"),
            BotCommand(command="contacts", description="Связаться с мастером"),
            BotCommand(command="leads", description="[Мастер] Последние заявки"),
            BotCommand(command="payments", description="[Мастер] Последние платежи"),
            BotCommand(command="help", description="Помощь"),
        ]
    )


async def run_check() -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
    cfg = load_config()
    db = Database(cfg.db_path)
    await db.init()

    print("Lika Tattoo Bot check")
    print(f"Bot dir: {cfg.data_dir.parent}")
    print(f"Database: {cfg.db_path}")
    print(f"Generated images: {cfg.generated_dir}")
    print(f"Portfolio root: {cfg.portfolio_root}")
    print(f"Telegram bot token configured: {cfg.bot_token_ready}")
    print(f"Telegram proxy configured: {bool(cfg.telegram_proxy_url)}")
    print(f"Free generations on start: {cfg.free_generations_on_start}")
    print(f"OpenAI key configured: {cfg.openai_key_ready}")
    print(f"Admin chat configured: {bool(cfg.admin_chat_id)}")
    print(f"Google Sheets consumables configured: {cfg.google_sheets_consumables_ready}")
    print(f"Google Sheets booking-note sync configured: {cfg.google_sheets_api_ready}")
    print(f"Published CSV URL configured: {bool(cfg.google_sheets_published_csv_url)}")
    print(f"Google CRM credentials configured: {cfg.google_crm_credentials_ready}")
    print(f"Google CRM spreadsheet configured: {cfg.google_crm_ready}")
    print(f"Google CRM owner email: {cfg.google_crm_owner_email or 'not set'}")
    print(f"Yandex Disk local path configured: {bool(cfg.yandex_disk_local_path)}")
    print(f"Session deposit provider configured: {cfg.session_deposit_enabled}")
    print(f"Robokassa credentials configured: {cfg.robokassa.ready}")
    print(f"Robokassa callback URLs configured: {cfg.robokassa.callback_urls_ready}")
    print(f"Robokassa enabled: {cfg.robokassa_enabled}")
    print(f"Robokassa test mode: {cfg.robokassa.is_test}")
    print(f"Robokassa bind: {cfg.robokassa.bind_host}:{cfg.robokassa.bind_port}")
    print("Generation packs:")
    for pack in cfg.generation_packs:
        print(f"  - {pack.title}: {pack.credits} credits / {pack.price_xtr} XTR")
    print("Service offers:")
    for offer in cfg.service_offers:
        print(f"  - {offer.title}: {offer.amount_rub} RUB")

    if not cfg.bot_token_ready:
        print("Warning: TELEGRAM_BOT_TOKEN still contains a placeholder.")
    if not cfg.openai_key_ready:
        print("Warning: OPENAI_API_KEY still contains a placeholder.")
    if not cfg.admin_chat_id:
        print("Info: ADMIN_CHAT_ID is empty, so booking and payment notifications are only stored in SQLite.")
    if not cfg.google_sheets_consumables_ready:
        print("Info: Google Sheets consumables sync is not configured, so the public calculator stays on local fallback JSON.")
    if not cfg.google_sheets_api_ready:
        print("Info: Booking-note sync by Google Sheets notes is not configured yet.")
    if not cfg.google_crm_credentials_ready:
        print("Info: Google CRM is not configured yet because no service-account credentials were found in bot/.env.")
    if not cfg.session_deposit_enabled:
        print("Info: session deposit via RUB is disabled until PAYMENTS_PROVIDER_TOKEN is set.")
    if cfg.robokassa.ready and not cfg.robokassa.callback_urls_ready:
        print("Info: Robokassa credentials are set, but callback URLs are still incomplete.")
    return 0


async def run_booking_report(limit: int) -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

    cfg = load_config()
    db = Database(cfg.db_path)
    await db.init()

    counts = await db.count_booking_requests_by_status()
    requests = await db.list_booking_requests(limit=limit)
    total = sum(counts.values())

    print("Booking requests report")
    print(f"Database: {cfg.db_path}")
    print(f"Total requests: {total}")
    if counts:
        print("Statuses:")
        for status, count in counts.items():
            print(f"  - {status}: {count}")
    else:
        print("Statuses: no booking requests yet")

    if not requests:
        print("Latest requests: none")
        return 0

    print(f"Latest requests (up to {limit}):")
    for request in requests:
        client_label = request.full_name or request.username or f"user {request.user_id}"
        print(
            f"  - #{request.request_id} | {request.created_at} | {request.status} | "
            f"{client_label}"
        )
        print(f"    idea: {request.idea}")
        print(f"    size: {request.size} | placement: {request.placement}")
        print(f"    preferred date: {request.preferred_date}")
        print(f"    contact: {request.contact}")
    return 0


async def run_booking_status_update(request_id: int, status: str) -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

    cfg = load_config()
    db = Database(cfg.db_path)
    await db.init()

    updated = await db.update_booking_request_status(request_id, status.strip())
    if not updated:
        print(f"Booking request #{request_id} was not found.")
        return 1

    print(f"Booking request #{request_id} status updated to: {status.strip()}")
    return 0


def _upsert_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_crm_init(owner_email_override: str) -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

    cfg = load_config()
    settings = resolve_crm_settings(cfg)
    owner_email = owner_email_override.strip() or settings.owner_email
    settings = type(settings)(
        project_dir=settings.project_dir,
        db_path=settings.db_path,
        service_account_file=settings.service_account_file,
        service_account_json=settings.service_account_json,
        spreadsheet_id=settings.spreadsheet_id,
        title=settings.title,
        owner_email=owner_email,
    )

    created = provision_crm_workspace(settings, fallback_spreadsheet_id=cfg.google_sheets_spreadsheet_id)
    env_path = Path(__file__).resolve().parent / ".env"
    if settings.service_account_file:
        _upsert_env_value(env_path, "GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE", settings.service_account_file)
    if owner_email:
        _upsert_env_value(env_path, "GOOGLE_CRM_OWNER_EMAIL", owner_email)
    _upsert_env_value(env_path, "GOOGLE_CRM_TITLE", settings.title)
    _upsert_env_value(env_path, "GOOGLE_CRM_SPREADSHEET_ID", created["spreadsheet_id"])

    print("Google CRM created")
    print(f"Spreadsheet ID: {created['spreadsheet_id']}")
    print(f"URL: {created['spreadsheet_url']}")
    print(f"Shared to owner email: {created['shared']}")
    return 0


async def run_crm_sync() -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

    cfg = load_config()
    settings = resolve_crm_settings(cfg)
    result = sync_crm_spreadsheet(settings)
    print("Google CRM synced")
    print(f"Spreadsheet ID: {result['spreadsheet_id']}")
    print(f"URL: {result['spreadsheet_url']}")
    print(f"Lead rows synced: {result['rows']}")
    return 0


async def run_bot() -> int:
    cfg = load_config()
    if not cfg.bot_token_ready:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured. Update bot/.env first.")

    db = Database(cfg.db_path)
    await db.init()
    sketch_service = TattooSketchService(cfg)
    session = AiohttpSession(proxy=cfg.telegram_proxy_url or None)

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(cfg, db, sketch_service))
    http_runner = await start_robokassa_server(cfg, db, bot)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await configure_bot_commands(bot)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
        return 0
    finally:
        await http_runner.cleanup()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lika Tattoo Telegram bot")
    parser.add_argument("--check", action="store_true", help="Run config and storage self-check")
    parser.add_argument(
        "--booking-report",
        action="store_true",
        help="Print booking requests report from SQLite",
    )
    parser.add_argument(
        "--booking-report-limit",
        type=int,
        default=10,
        help="How many recent booking requests to show with --booking-report",
    )
    parser.add_argument(
        "--booking-status",
        nargs=2,
        metavar=("REQUEST_ID", "STATUS"),
        help="Update booking request status, for example: --booking-status 12 contacted",
    )
    parser.add_argument(
        "--crm-init",
        action="store_true",
        help="Create a Google Sheets CRM workbook and save its ID into bot/.env",
    )
    parser.add_argument(
        "--crm-sync",
        action="store_true",
        help="Sync booking requests from SQLite into the configured Google CRM spreadsheet",
    )
    parser.add_argument(
        "--crm-owner-email",
        default="",
        help="Optional email to share the created CRM sheet with",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.check:
            raise SystemExit(asyncio.run(run_check()))
        if args.booking_report:
            raise SystemExit(asyncio.run(run_booking_report(args.booking_report_limit)))
        if args.booking_status:
            request_id = int(args.booking_status[0])
            status = args.booking_status[1]
            raise SystemExit(asyncio.run(run_booking_status_update(request_id, status)))
        if args.crm_init:
            raise SystemExit(asyncio.run(run_crm_init(args.crm_owner_email)))
        if args.crm_sync:
            raise SystemExit(asyncio.run(run_crm_sync()))
        raise SystemExit(asyncio.run(run_bot()))
    except ConfigError as error:
        print(f"Configuration error: {error}")
        raise SystemExit(2) from error
    except RuntimeError as error:
        print(f"Runtime error: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
