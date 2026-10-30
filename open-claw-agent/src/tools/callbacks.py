"""
Callback query handler for inline menu buttons.
"""

from telegram import Update
from telegram.ext import ContextTypes

from src.tools.menu import show_menu


async def handle_menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    callback_data = query.data

    cfg = ctx.bot_data.get("cfg")
    sec = ctx.bot_data.get("sec")
    db = ctx.bot_data.get("db")

    user_id = update.effective_user.id if update.effective_user else 0
    chat_id = update.effective_chat.id if update.effective_chat else 0

    if not sec.is_allowed(user_id, chat_id):
        await query.answer("Access denied")
        return

    await query.answer()

    nav_keys = {
        "main",
        "info",
        "search",
        "communication",
        "control",
        "ai",
        "search:photos",
        "search:music",
        "calendar",
        "notes",
        "control:mouse",
        "control:keyboard",
    }
    if callback_data in nav_keys:
        await show_menu(update, ctx, menu_key=callback_data)
        return

    if callback_data == "cmd:status":
        from src.tools.status import get_status

        await query.edit_message_text(text=get_status())
        db.log(user_id, chat_id, "/menu:status", True, "")
        return

    if callback_data == "cmd:screenshot":
        from src.tools.screenshot import make_screenshot

        path = make_screenshot(cfg.workdir / "screens")
        await query.edit_message_text(text="Screenshot created.")
        await ctx.bot.send_document(chat_id, path.open("rb"), filename=path.name)
        db.log(user_id, chat_id, "/menu:screenshot", True, "")
        return

    if callback_data == "cmd:pc_info":
        from src.tools.status import get_status

        await query.edit_message_text(text=get_status())
        db.log(user_id, chat_id, "/menu:pc_info", True, "")
        return

    if callback_data == "cmd:ask":
        ctx.user_data["awaiting_ask"] = True
        await query.edit_message_text(text="Send your question in the next message.")
        return

    if callback_data == "cmd:research":
        ctx.user_data["awaiting_research"] = True
        await query.edit_message_text(text="Send a topic for research in the next message.")
        return

    if callback_data == "cmd:email":
        ctx.user_data["awaiting_email"] = True
        await query.edit_message_text(
            text="Send one message like: send file diploma to user@mail.com"
        )
        return

    if callback_data == "cmd:calendar_add":
        ctx.user_data["awaiting_calendar"] = True
        await query.edit_message_text(text="Send event details in the next message.")
        return

    if callback_data == "cmd:calendar_view":
        if cfg.use_google_calendar:
            from src.tools.google_services import GoogleCalendarService

            calendar_service = GoogleCalendarService(cfg.google_credentials_path)
        else:
            from src.tools.integrations import CalendarService

            calendar_service = CalendarService(cfg.calendar_dir)
        ok, message = calendar_service.list_events(days_ahead=7)
        await query.edit_message_text(text=message)
        db.log(user_id, chat_id, "/menu:calendar_view", ok, "")
        return

    if callback_data == "cmd:note_create":
        ctx.user_data["awaiting_note"] = True
        await query.edit_message_text(text="Send note text in the next message.")
        return

    if callback_data == "cmd:notes_list":
        if cfg.use_google_notes:
            await query.edit_message_text(
                text="Google Notes enabled. Open your Drive folder OpenClawNotes."
            )
        else:
            from src.tools.integrations import NotesService

            notes_service = NotesService(cfg.notes_dir)
            notes = notes_service.list_notes(limit=10)
            if notes:
                await query.edit_message_text(
                    text="Recent notes:\n" + "\n".join(f"- {item}" for item in notes)
                )
            else:
                await query.edit_message_text(text="No notes yet.")
        db.log(user_id, chat_id, "/menu:notes_list", True, "")
        return

    if callback_data == "cmd:docker":
        from src.tools.docker_ops import docker_ps

        message = docker_ps()
        if len(message) > 3500:
            out_file = cfg.workdir / "docker_ps.txt"
            out_file.write_text(message, encoding="utf-8")
            await query.edit_message_text(text="Docker output is too long, sending file.")
            await ctx.bot.send_document(chat_id, out_file.open("rb"), filename=out_file.name)
        else:
            await query.edit_message_text(text=message)
        db.log(user_id, chat_id, "/menu:docker", True, "")
        return

    if callback_data in {"mouse:move", "mouse:click", "mouse:double"}:
        ctx.user_data["awaiting_mouse"] = callback_data
        await query.edit_message_text(text="Send coordinates in format: X Y")
        return

    if callback_data == "search:files":
        ctx.user_data["awaiting_file_search"] = True
        await query.edit_message_text(text="Send file name or part of name.")
        return

    if callback_data in {"search:photos:people", "search:photos:landscape", "search:photos:date"}:
        mode = callback_data.split(":")[-1]
        ctx.user_data["awaiting_photo_search"] = mode
        await query.edit_message_text(text="Send photo search query.")
        return

    if callback_data == "search:documents":
        ctx.user_data["awaiting_doc_search"] = True
        await query.edit_message_text(text="Send document query.")
        return
    
    if callback_data == "cmd:suggestions":
        from src.tools.smart_recommendations import (
            get_calendar_recommendations,
            suggest_break_locations,
            get_time_based_suggestion,
        )
        
        # Get calendar events first
        if cfg.use_google_calendar:
            from src.tools.google_services import GoogleCalendarService
            calendar = GoogleCalendarService(cfg.google_credentials_path)
            ok, events_text = calendar.list_events(days_ahead=7)
        else:
            from src.tools.integrations import CalendarService
            calendar = CalendarService(cfg.calendar_dir)
            ok, events_text = calendar.list_events(days_ahead=7)
        
        suggestions = suggest_break_locations() + [get_time_based_suggestion()]
        text = "💡 **Рекомендации для тебя:**\n\n" + "\n\n".join(suggestions)
        
        await query.edit_message_text(text=text)
        db.log(user_id, chat_id, "/menu:suggestions", True, "")
        return

    if callback_data == "search:photos":
        ctx.user_data["awaiting_photo_search"] = True
        await query.edit_message_text(text="📸 Опиши что ищешь: девушка, пейзаж, природа, и т.д.")
        return
    
    if callback_data == "search:files":
        ctx.user_data["awaiting_file_search"] = True
        await query.edit_message_text(text="📄 Введи название файла или часть имени")
        return
    
    if callback_data == "cmd:note":
        ctx.user_data["awaiting_note"] = True
        await query.edit_message_text(text="📝 Введи текст заметки в следующем сообщении")
        return
    
    if callback_data == "calendar:view":
        if cfg.use_google_calendar:
            from src.tools.google_services import GoogleCalendarService
            calendar_service = GoogleCalendarService(cfg.google_credentials_path)
        else:
            from src.tools.integrations import CalendarService
            calendar_service = CalendarService(cfg.calendar_dir)
        ok, message = calendar_service.list_events(days_ahead=7)
        await query.edit_message_text(text=message)
        db.log(user_id, chat_id, "/menu:calendar_view", ok, "")
        return
    
    if callback_data == "cmd:open_app":
        apps_text = "🚀 **Доступные приложения:**\n\n"
        apps_text += "steam, chrome, firefox, edge\n"
        apps_text += "pycharm, vscode, code\n"
        apps_text += "telegram, discord\n"
        apps_text += "notepad, explorer\n\n"
        apps_text += "✏️ Напиши: открой [имя приложения]"
        ctx.user_data["awaiting_open_app"] = True
        await query.edit_message_text(text=apps_text)
        return
    
    if callback_data == "cmd:ask":
        ctx.user_data["awaiting_ask"] = True
        await query.edit_message_text(text="🧠 Задай вопрос AI (mistral:7b)")
        return
    
    if callback_data == "cmd:research":
        ctx.user_data["awaiting_research"] = True
        await query.edit_message_text(text="🎯 Введи тему для исследования")
        return
    
    if callback_data == "cmd:email":
        ctx.user_data["awaiting_email"] = True
        await query.edit_message_text(text="📧 Напиши: email@example.com кратко сообщение")
        return
