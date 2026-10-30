import asyncio
import json
import re
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
)

from src.config import load_config
from src.db import AuditDB
from src.security import Security
from src.executor import TaskRegistry, run_cmd
from src.tools.status import get_status
from src.tools.screenshot import make_screenshot
from src.tools.docker_ops import docker_available, docker_ps, docker_restart
from src.tools.ollama_agent import ask_ollama, test_ollama_available
from src.tools.file_search import find_files
from src.tools.remote_control import is_remote_control_available, move_mouse, mouse_click, keyboard_press, keyboard_type, hotkey
from src.tools.nlu import NLUEngine
from src.tools.integrations import EmailService, CalendarService, NotesService
from src.tools.contacts import get_contacts
from src.tools.google_services import GoogleSheetsService
from src.tools.memory import get_memory
from src.tools.self_research import run_proactive_research_once

HELP_TEXT = (
    "🤖 Open Claw Agent\n\n"
    "**📝 Обычные команды:**\n"
    "/status — статус ПК\n"
    "/screenshot — скрин\n"
    "/tasks — список задач\n"
    "/run <task_id> — выполнить задачу\n"
    "/ask <question> — спросить AI (mistral:7b)\n"
    "/find <filename> — найти файл на ПК\n"
    "/mouse move <x> <y> — переместить мышь\n"
    "/mouse click — клик левой кнопкой\n"
    "/mouse rclick — правый клик\n"
    "/keyboard key <name> — нажать клавишу\n"
    "/keyboard type <text> — напечатать текст\n"
    "/docker ps — список контейнеров\n"
    "/docker restart <name> — рестарт контейнера\n"
    "/confirm <code> — подтвердить опасное действие\n\n"
    "**🧠 Умный режим (если включён в .env ENABLE_NLU=true):**\n"
    "Просто пиши обычным языком:\n"
    "- \"какой статус пк?\" → выполнит /status\n"
    "- \"найди диплом\" → найдёт файл\n"
    "- \"скрин экрана\" → сделает скрин\n"
    "- \"расскажи про Python\" → спросит AI\n"
    "- \"сохрани заметку про встречу\" → создаст заметку\n"
    "- Отправь голосовое сообщение → транскрибирует и выполнит\n"
)

def _who(update: Update) -> tuple[int, int]:
    user_id = update.effective_user.id if update.effective_user else 0
    chat_id = update.effective_chat.id if update.effective_chat else 0
    return user_id, chat_id

async def guarded(update: Update, ctx: ContextTypes.DEFAULT_TYPE, sec: Security) -> bool:
    user_id, chat_id = _who(update)
    if not sec.is_allowed(user_id, chat_id):
        await update.message.reply_text("⛔ Access denied.")
        return False
    return True

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from src.tools.menu import show_main_menu
    await update.message.reply_text(HELP_TEXT)
    await show_main_menu(update, ctx)

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from src.tools.menu import show_main_menu
    await update.message.reply_text(HELP_TEXT)
    await show_main_menu(update, ctx)

async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Проверить статус всех интеграций"""
    sec = ctx.bot_data["sec"]
    cfg = ctx.bot_data["cfg"]
    
    if not await guarded(update, ctx, sec):
        return
    
    checks = []
    
    # Ollama
    from src.tools.ollama_agent import test_ollama_available
    ollama_ok = test_ollama_available()
    checks.append(f"{'✅' if ollama_ok else '❌'} Ollama: {'доступна' if ollama_ok else 'НЕ ЗАПУЩЕНА'}")
    
    # Speech Recognition
    from src.tools.speech_to_text import is_speech_recognition_available
    sr_ok = is_speech_recognition_available()
    checks.append(f"{'✅' if sr_ok else '❌'} Speech Recognition: {'установлена' if sr_ok else 'НЕ УСТАНОВЛЕНА'}")
    
    # Remote Control
    from src.tools.remote_control import is_remote_control_available
    rc_ok = is_remote_control_available()
    checks.append(f"{'✅' if rc_ok else '❌'} Remote Control (pyautogui): {'установлена' if rc_ok else 'НЕ УСТАНОВЛЕНА'}")
    
    # Google Calendar
    if cfg.use_google_calendar:
        from src.tools.google_services import GoogleCalendarService
        gcal = GoogleCalendarService(cfg.google_credentials_path)
        gcal_ok = gcal.service is not None
        checks.append(f"{'✅' if gcal_ok else '❌'} Google Calendar: {'готова' if gcal_ok else 'ОШИБКА ИНИЦИАЛИЗАЦИИ'}")
    else:
        checks.append(f"⚪ Google Calendar: отключена в .env")
    
    # Google Notes
    if cfg.use_google_notes:
        from src.tools.google_services import GoogleNotesService
        gnotes = GoogleNotesService(cfg.google_credentials_path)
        gnotes_ok = gnotes.service_docs is not None
        checks.append(f"{'✅' if gnotes_ok else '❌'} Google Notes: {'готовы' if gnotes_ok else 'ОШИБКА ИНИЦИАЛИЗАЦИИ'}")
    else:
        checks.append(f"⚪ Google Notes: отключены в .env")
    
    # Google Sheets memory
    if cfg.use_google_sheets_memory:
        sheets = GoogleSheetsService(cfg.google_credentials_path, cfg.google_memory_sheet_id)
        sheets_ok = sheets.service is not None and bool(cfg.google_memory_sheet_id)
        checks.append(
            f"{'вњ…' if sheets_ok else 'вќЊ'} Google Sheets Memory: "
            f"{'ready' if sheets_ok else 'not initialized / missing GOOGLE_MEMORY_SHEET_ID'}"
        )
    else:
        checks.append("вљЄ Google Sheets Memory: disabled in .env")

    proactive_status = "enabled" if cfg.proactive_research_enabled else "disabled"
    checks.append(
        f"{'вњ…' if cfg.proactive_research_enabled else 'вљЄ'} "
        f"Proactive Research: {proactive_status}"
    )

    # Email
    if cfg.email_address and cfg.email_password:
        checks.append(f"✅ Email SMTP: настроена")
    else:
        checks.append(f"❌ Email SMTP: НЕ НАСТРОЕНА")
    
    # NLU
    nlu = ctx.bot_data.get("nlu")
    nlu_ok = nlu is not None and cfg.enable_nlu
    checks.append(f"{'✅' if nlu_ok else '❌'} NLU Smart Mode: {'ВКЛЮЧЕНА' if nlu_ok else 'отключена'}")
    
    msg = "🔍 **Статус системы:**\n\n" + "\n".join(checks)
    await update.message.reply_text(msg)

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Показать интерактивное меню"""
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    
    if not await guarded(update, ctx, sec):
        return
    
    user_id, chat_id = _who(update)
    
    try:
        from src.tools.menu import show_main_menu
        await show_main_menu(update, ctx)
        db.log(user_id, chat_id, "/menu", True, None)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        db.log(user_id, chat_id, "/menu", False, str(e))
        db.log(user_id, chat_id, "/menu", False, str(e))

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = ctx.bot_data["cfg"]
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    if not await guarded(update, ctx, sec):
        return
    try:
        text = get_status()
        await update.message.reply_text(text)
        user_id, chat_id = _who(update)
        db.log(user_id, chat_id, "/status", True, None)
    except Exception as e:
        user_id, chat_id = _who(update)
        db.log(user_id, chat_id, "/status", False, str(e))
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_screenshot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = ctx.bot_data["cfg"]
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    if not await guarded(update, ctx, sec):
        return
    try:
        p = make_screenshot(cfg.workdir / "screens")
        await update.message.reply_document(document=p.open("rb"), filename=p.name)
        user_id, chat_id = _who(update)
        db.log(user_id, chat_id, "/screenshot", True, str(p))
    except Exception as e:
        user_id, chat_id = _who(update)
        db.log(user_id, chat_id, "/screenshot", False, str(e))
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    reg = ctx.bot_data["reg"]
    if not await guarded(update, ctx, sec):
        return
    reg.reload()
    lines = ["📋 Tasks:"]
    for task_id, desc, dangerous in reg.list_tasks():
        lines.append(f"- {task_id} {'⚠️' if dangerous else ''} — {desc}")
    await update.message.reply_text("\n".join(lines))
    user_id, chat_id = _who(update)
    db.log(user_id, chat_id, "/tasks", True, None)

async def cmd_run(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = ctx.bot_data["cfg"]
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    reg = ctx.bot_data["reg"]
    if not await guarded(update, ctx, sec):
        return

    if not ctx.args:
        await update.message.reply_text("Usage: /run <task_id>")
        return

    task_id = ctx.args[0].strip()
    reg.reload()
    spec = reg.get(task_id)
    if not spec:
        await update.message.reply_text("❌ Unknown task_id. Use /tasks")
        return

    cmd = spec.get("cmd")
    if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
        await update.message.reply_text("❌ Bad task format in tasks.yaml")
        return

    dangerous = bool(spec.get("dangerous", False))
    user_id, chat_id = _who(update)

    if dangerous:
        code = sec.create_confirm(user_id, chat_id, {"type": "run", "task_id": task_id})
        await update.message.reply_text(
            f"⚠️ Task '{task_id}' is dangerous.\n"
            f"Confirm within {sec.confirm_ttl}s:\n"
            f"/confirm {code}"
        )
        db.log(user_id, chat_id, f"/run {task_id}", True, "pending_confirm")
        return

    await update.message.reply_text(f"▶️ Running: {task_id}")
    rc, out = await run_cmd(cmd, cwd=str(cfg.workdir))
    ok = (rc == 0)
    db.log(user_id, chat_id, f"/run {task_id}", ok, out[:1500])

    msg = f"✅ Done (rc={rc})\n"
    if out.strip():
        if len(out) > 3500:
            # если много вывода — в файл
            out_file = cfg.workdir / f"task_{task_id}_output.txt"
            out_file.write_text(out, encoding="utf-8", errors="replace")
            await update.message.reply_document(out_file.open("rb"), filename=out_file.name)
            await update.message.reply_text(msg + "Output: (sent as file)")
        else:
            await update.message.reply_text(msg + out)
    else:
        await update.message.reply_text(msg + "(no output)")

async def cmd_docker(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = ctx.bot_data["cfg"]
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    if not await guarded(update, ctx, sec):
        return

    if not ctx.args:
        await update.message.reply_text("Usage: /docker ps | /docker restart <name>")
        return

    sub = ctx.args[0].lower()
    user_id, chat_id = _who(update)

    if not docker_available():
        await update.message.reply_text("❌ docker python sdk not available (or not installed).")
        db.log(user_id, chat_id, f"/docker {sub}", False, "docker sdk missing")
        return

    try:
        if sub == "ps":
            text = docker_ps()
            await update.message.reply_text("🐳 Containers:\n" + text)
            db.log(user_id, chat_id, "/docker ps", True, None)
        elif sub == "restart":
            if len(ctx.args) < 2:
                await update.message.reply_text("Usage: /docker restart <name>")
                return
            name = ctx.args[1]
            code = sec.create_confirm(user_id, chat_id, {"type": "docker_restart", "name": name})
            await update.message.reply_text(
                f"⚠️ Restart container '{name}'. Confirm within {sec.confirm_ttl}s:\n/confirm {code}"
            )
            db.log(user_id, chat_id, f"/docker restart {name}", True, "pending_confirm")
        else:
            await update.message.reply_text("Unknown docker command. Use: ps, restart")
    except Exception as e:
        db.log(user_id, chat_id, f"/docker {sub}", False, str(e))
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = ctx.bot_data["cfg"]
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    reg = ctx.bot_data["reg"]

    if not await guarded(update, ctx, sec):
        return

    if not ctx.args:
        await update.message.reply_text("Usage: /confirm <code>")
        return

    code = ctx.args[0].strip()
    user_id, chat_id = _who(update)
    payload = sec.consume_confirm(user_id, chat_id, code)

    if not payload:
        await update.message.reply_text("❌ No pending action / expired / wrong code.")
        db.log(user_id, chat_id, f"/confirm {code}", False, "invalid_or_expired")
        return

    try:
        if payload["type"] == "run":
            task_id = payload["task_id"]
            reg.reload()
            spec = reg.get(task_id)
            if not spec:
                await update.message.reply_text("❌ Unknown task_id now. Use /tasks")
                return
            cmd = spec.get("cmd")
            await update.message.reply_text(f"▶️ Confirmed. Running: {task_id}")
            rc, out = await run_cmd(cmd, cwd=str(cfg.workdir))
            ok = (rc == 0)
            db.log(user_id, chat_id, f"CONFIRMED /run {task_id}", ok, out[:1500])

            msg = f"✅ Done (rc={rc})\n"
            if out.strip():
                if len(out) > 3500:
                    out_file = cfg.workdir / f"task_{task_id}_output.txt"
                    out_file.write_text(out, encoding="utf-8", errors="replace")
                    await update.message.reply_document(out_file.open("rb"), filename=out_file.name)
                    await update.message.reply_text(msg + "Output: (sent as file)")
                else:
                    await update.message.reply_text(msg + out)
            else:
                await update.message.reply_text(msg + "(no output)")

        elif payload["type"] == "docker_restart":
            name = payload["name"]
            await update.message.reply_text(f"▶️ Confirmed. Restarting: {name}")
            text = docker_restart(name)
            await update.message.reply_text("✅ " + text)
            db.log(user_id, chat_id, f"CONFIRMED docker restart {name}", True, None)

        else:
            await update.message.reply_text("❌ Unknown payload type.")
            db.log(user_id, chat_id, f"/confirm {code}", False, "unknown_payload")
    except Exception as e:
        db.log(user_id, chat_id, f"/confirm {code}", False, str(e))
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = ctx.bot_data["cfg"]
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    
    if not await guarded(update, ctx, sec):
        return

    if not ctx.args:
        await update.message.reply_text("Usage: /ask <question>")
        return

    question = " ".join(ctx.args)
    user_id, chat_id = _who(update)

    if not test_ollama_available():
        await update.message.reply_text("❌ Ollama не запущена на localhost:11434")
        db.log(user_id, chat_id, "/ask", False, "ollama_unavailable")
        return

    # Отправляем "думаю" сообщение и запоминаем его ID
    thinking_msg = await update.message.reply_text("🤔 Думаю на твой вопрос...")
    
    try:
        ok, response = await ask_ollama(question)
        if not ok:
            # Удаляем "думаю" и отправляем ошибку
            await thinking_msg.delete()
            await update.message.reply_text(response)
            db.log(user_id, chat_id, "/ask", False, response)
            return

        db.log(user_id, chat_id, "/ask", True, question[:100])

        # Удаляем "думаю" сообщение
        await thinking_msg.delete()

        # Если ответ короткий — прямо в чат
        if len(response) <= 3500:
            await update.message.reply_text(f"🤖 {response}")
        else:
            # Если длинный — в файл
            out_file = cfg.workdir / "ollama_response.txt"
            out_file.write_text(response, encoding="utf-8", errors="replace")
            await update.message.reply_document(out_file.open("rb"), filename=out_file.name)
            await update.message.reply_text(f"🤖 Ответ отправлен в файл (длина: {len(response)} символов)")

    except Exception as e:
        await thinking_msg.delete()
        db.log(user_id, chat_id, "/ask", False, str(e))
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_find(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = ctx.bot_data["cfg"]
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    
    if not await guarded(update, ctx, sec):
        return

    if not ctx.args:
        await update.message.reply_text("Usage: /find <filename or .ext>")
        return

    query = " ".join(ctx.args)
    user_id, chat_id = _who(update)

    searching_msg = await update.message.reply_text(f"🔍 Ищу '{query}'...")
    
    try:
        results = find_files(query, max_results=10)

        await searching_msg.delete()

        if not results:
            await update.message.reply_text(f"❌ Файлы '{query}' не найдены")
            db.log(user_id, chat_id, "/find", False, query)
            return

        msg = f"✅ Найдено {len(results)} файл(ов):\n\n"
        for path in results:
            msg += f"📄 {path}\n"

        if len(msg) > 3500:
            out_file = cfg.workdir / "find_results.txt"
            out_file.write_text(msg, encoding="utf-8")
            await update.message.reply_document(out_file.open("rb"), filename="find_results.txt")
        else:
            await update.message.reply_text(msg)

        db.log(user_id, chat_id, "/find", True, query)

    except Exception as e:
        await searching_msg.delete()
        db.log(user_id, chat_id, "/find", False, str(e))
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_mouse(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    
    if not await guarded(update, ctx, sec):
        return

    if not ctx.args:
        await update.message.reply_text(
            "Usage:\n"
            "/mouse move <x> <y>\n"
            "/mouse click [x y]\n"
            "/mouse rclick [x y]"
        )
        return

    user_id, chat_id = _who(update)

    if not is_remote_control_available():
        await update.message.reply_text("❌ pyautogui не установлен. pip install pyautogui")
        db.log(user_id, chat_id, "/mouse", False, "pyautogui_missing")
        return

    try:
        cmd = ctx.args[0].lower()

        if cmd == "move" and len(ctx.args) >= 3:
            x, y = int(ctx.args[1]), int(ctx.args[2])
            ok, msg = move_mouse(x, y)
            await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
            db.log(user_id, chat_id, "/mouse move", ok, msg)

        elif cmd == "click":
            x = y = None
            if len(ctx.args) >= 3:
                x, y = int(ctx.args[1]), int(ctx.args[2])
            ok, msg = mouse_click(x, y, "left")
            await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
            db.log(user_id, chat_id, "/mouse click", ok, msg)

        elif cmd == "rclick":
            x = y = None
            if len(ctx.args) >= 3:
                x, y = int(ctx.args[1]), int(ctx.args[2])
            ok, msg = mouse_click(x, y, "right")
            await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
            db.log(user_id, chat_id, "/mouse rclick", ok, msg)

        else:
            await update.message.reply_text("❌ Unknown mouse command")

    except ValueError as e:
        await update.message.reply_text(f"❌ Неверные координаты: {e}")
        db.log(user_id, chat_id, "/mouse", False, str(e))
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        db.log(user_id, chat_id, "/mouse", False, str(e))


async def cmd_keyboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sec = ctx.bot_data["sec"]
    db = ctx.bot_data["db"]
    
    if not await guarded(update, ctx, sec):
        return

    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Usage:\n"
            "/keyboard key <name> (enter, space, tab, esc, etc)\n"
            "/keyboard type <text>"
        )
        return

    user_id, chat_id = _who(update)

    if not is_remote_control_available():
        await update.message.reply_text("❌ pyautogui не установлен. pip install pyautogui")
        db.log(user_id, chat_id, "/keyboard", False, "pyautogui_missing")
        return

    try:
        subcmd = ctx.args[0].lower()

        if subcmd == "key":
            key = ctx.args[1].lower()
            ok, msg = keyboard_press(key)
            await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
            db.log(user_id, chat_id, "/keyboard key", ok, msg)

        elif subcmd == "type":
            text = " ".join(ctx.args[1:])
            ok, msg = keyboard_type(text)
            await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
            db.log(user_id, chat_id, "/keyboard type", ok, f"text: {text[:50]}")

        else:
            await update.message.reply_text("❌ Unknown keyboard command")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        db.log(user_id, chat_id, "/keyboard", False, str(e))

def _proactive_topics_path(workdir: Path) -> Path:
    return workdir / "proactive_topics.json"


def _load_proactive_topics(cfg) -> list[str]:
    path = _proactive_topics_path(cfg.workdir)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            topics = payload.get("topics", [])
            if isinstance(topics, list):
                cleaned = [str(x).strip() for x in topics if str(x).strip()]
                if cleaned:
                    return cleaned
        except Exception:
            pass
    return list(getattr(cfg, "proactive_topics", []) or [])


async def proactive_research_job(context: ContextTypes.DEFAULT_TYPE):
    app = context.application
    cfg = app.bot_data.get("cfg")
    if not cfg or not getattr(cfg, "proactive_research_enabled", False):
        return

    topics = app.bot_data.get("proactive_topics") or []
    if not topics:
        return

    idx = int(app.bot_data.get("proactive_topic_index", 0))
    topic = topics[idx % len(topics)]
    app.bot_data["proactive_topic_index"] = (idx + 1) % len(topics)

    ok, summary, report_path, sources = await run_proactive_research_once(
        [topic],
        cfg.workdir / "research",
    )
    if not ok:
        return

    memory = get_memory()
    memory.add_proactive_report(topic=topic, summary=summary[:2000], sources=sources)

    if getattr(cfg, "use_google_sheets_memory", False) and getattr(cfg, "google_memory_sheet_id", ""):
        sheets = GoogleSheetsService(cfg.google_credentials_path, cfg.google_memory_sheet_id)
        sheets.append_research_note(topic=topic, summary=summary[:1000], sources=sources[:10])

    if not getattr(cfg, "proactive_research_send_to_chat", False):
        return

    active_chats = app.bot_data.get("active_chats", set())
    if not active_chats:
        active_chats = set(cfg.allowed_chat_ids)
    if not active_chats:
        return

    msg = f"Proactive research update on '{topic}':\n{summary[:1200]}"
    for chat_id in active_chats:
        try:
            await app.bot.send_message(chat_id=chat_id, text=msg)
            if report_path and report_path.exists():
                await app.bot.send_document(
                    chat_id=chat_id,
                    document=report_path.open("rb"),
                    filename=report_path.name,
                )
        except Exception:
            continue


def main():
    cfg = load_config()
    db = AuditDB(cfg.db_path)
    sec = Security(cfg.allowed_user_ids, cfg.allowed_chat_ids, cfg.confirm_ttl)

    tasks_path = Path("tasks.yaml")
    if not tasks_path.exists():
        raise RuntimeError("tasks.yaml not found рядом с запуском")

    reg = TaskRegistry(tasks_path)
    
    # Инициализируем NLU (умный анализ текста)
    nlu = NLUEngine() if cfg.enable_nlu else None

    contacts = get_contacts()
    app = Application.builder().token(cfg.token).build()
    app.bot_data["cfg"] = cfg
    app.bot_data["db"] = db
    app.bot_data["sec"] = sec
    app.bot_data["reg"] = reg
    app.bot_data["nlu"] = nlu
    app.bot_data["contacts"] = contacts
    app.bot_data["active_chats"] = set()
    app.bot_data["proactive_topics"] = _load_proactive_topics(cfg)
    app.bot_data["proactive_topic_index"] = 0

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("screenshot", cmd_screenshot))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("ask", cmd_ask))
    app.add_handler(CommandHandler("find", cmd_find))
    app.add_handler(CommandHandler("mouse", cmd_mouse))
    app.add_handler(CommandHandler("keyboard", cmd_keyboard))
    app.add_handler(CommandHandler("docker", cmd_docker))
    app.add_handler(CommandHandler("confirm", cmd_confirm))
    
    # Handler for menu button presses (text-based keyboard)
    from src.tools.menu_handler import handle_menu_button
    menu_buttons = ["📊 Статус", "🖼️ Скрин", "🔍 Файл", "📸 Фото", 
                    "📅 Календарь", "📝 Заметка", "🧠 Спросить AI", 
                    "🎯 Исследовать", "🚀 Открыть приложение", "📧 Письмо",
                    "💡 Рекомендации", "❓ Помощь"]
    menu_filter = filters.TEXT & ~filters.COMMAND
    for btn in menu_buttons:
        menu_filter = menu_filter | filters.Regex(f"^{btn.replace('🚀 ', '').replace('❓ ', '')}")
    
    # Умный обработчик для текстовых сообщений и голоса (если NLU включён)
    if cfg.enable_nlu:
        try:
            from src.tools.smart_handler import handle_smart_message
        except Exception as e:
            print(f"smart handler unavailable: {e}")
            handle_smart_message = None

        if handle_smart_message:
            # First check if it's a menu button
            app.add_handler(MessageHandler(filters.Regex("|".join([re.escape(btn) for btn in menu_buttons])), handle_menu_button))
            # Then handle smart messages
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_smart_message))
            app.add_handler(MessageHandler(filters.VOICE, handle_smart_message))
    else:
        # If no NLU, still handle menu buttons
        app.add_handler(MessageHandler(filters.Regex("|".join([re.escape(btn) for btn in menu_buttons])), handle_menu_button))

    print("Open Claw Agent started.")
    if cfg.enable_nlu:
        print("Smart NLU mode ENABLED")
    if cfg.proactive_research_enabled:
        if app.job_queue:
            interval_sec = max(300, int(cfg.proactive_research_interval_minutes) * 60)
            app.job_queue.run_repeating(proactive_research_job, interval=interval_sec, first=120)
            print(f"Proactive research mode ENABLED (every {cfg.proactive_research_interval_minutes} min)")
        else:
            print("Proactive research requested, but JobQueue is unavailable.")
    app.run_polling()

if __name__ == "__main__":
    main()
