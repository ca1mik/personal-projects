"""
Handler for menu button presses (text-based, not inline).
"""

from telegram import Update
from telegram.ext import ContextTypes

from src.tools.app_detector import get_installed_apps_list, format_apps_list


async def handle_menu_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle button presses from regular keyboard menu."""
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    cfg = ctx.bot_data.get("cfg")
    sec = ctx.bot_data.get("sec")
    db = ctx.bot_data.get("db")
    
    if not cfg or not sec:
        await update.message.reply_text("❌ System not initialized")
        return
    
    user_id = update.effective_user.id if update.effective_user else 0
    chat_id = update.effective_chat.id if update.effective_chat else 0
    
    if not sec.is_allowed(user_id, chat_id):
        await update.message.reply_text("❌ Access denied")
        return
    
    # 📊 Status
    if text == "📊 Статус":
        from src.tools.status import get_status
        await update.message.reply_text(get_status())
        db.log(user_id, chat_id, "menu:status", True, "")
        return
    
    # 🖼️ Screenshot
    # 🖼️ Screenshot
    if text == "🖼️ Скрин":
        try:
            from src.tools.screenshot import make_screenshot
            path = make_screenshot(cfg.workdir / "screens")
            await update.message.reply_document(path.open("rb"), filename=path.name)
            if db:
                db.log(user_id, chat_id, "menu:screenshot", True, "")
        except Exception as e:
            await update.message.reply_text(f"❌ Screenshot error: {e}")
            if db:
                db.log(user_id, chat_id, "menu:screenshot", False, str(e))
        return
    
    # 🔍 File search
    if text == "🔍 Файл":
        ctx.user_data["awaiting_file_search"] = True
        await update.message.reply_text("📄 Введи название файла или часть имени:")
        return
    
    # 📸 Photo search
    if text == "📸 Фото":
        ctx.user_data["awaiting_photo_search"] = True
        await update.message.reply_text("📸 Опиши что ищешь (девушка, пейзаж, природа, etc.):")
        return
    
    # 📅 Calendar
    if text == "📅 Календарь":
        if cfg.use_google_calendar:
            from src.tools.google_services import GoogleCalendarService
            calendar = GoogleCalendarService(cfg.google_credentials_path)
        else:
            from src.tools.integrations import CalendarService
            calendar = CalendarService(cfg.calendar_dir)
        
        ok, message = calendar.list_events(days_ahead=7)
        await update.message.reply_text(message)
        db.log(user_id, chat_id, "menu:calendar", ok, "")
        return
    
    # 📝 Note
    if text == "📝 Заметка":
        ctx.user_data["awaiting_note"] = True
        await update.message.reply_text("📝 Введи текст заметки:")
        return
    
    # 🧠 Ask AI
    if text == "🧠 Спросить AI":
        ctx.user_data["awaiting_ask"] = True
        await update.message.reply_text("🧠 Задай вопрос (mistral:7b):")
        return
    
    # 🎯 Research
    if text == "🎯 Исследовать":
        ctx.user_data["awaiting_research"] = True
        await update.message.reply_text("🎯 Введи тему для исследования:")
        return
    
    # 🚀 Open app
    if text == "🚀 Открыть приложение":
        apps_msg = format_apps_list()
        await update.message.reply_text(apps_msg)
        ctx.user_data["awaiting_open_app"] = True
        await update.message.reply_text("✏️ Напиши: открой [имя приложения]")
        return
    
    # 📧 Email
    if text == "📧 Письмо":
        ctx.user_data["awaiting_email"] = True
        await update.message.reply_text("📧 Напиши: кому@mail.com сообщение")
        return
    
    # 💡 Suggestions
    if text == "💡 Рекомендации":
        from src.tools.smart_recommendations import (
            suggest_break_locations,
            get_time_based_suggestion,
        )
        
        suggestions = suggest_break_locations() + [get_time_based_suggestion()]
        text_msg = "💡 **Рекомендации для тебя:**\n\n" + "\n\n".join(suggestions)
        await update.message.reply_text(text_msg)
        db.log(user_id, chat_id, "menu:suggestions", True, "")
        return
    
    # ❓ Help
    if text == "❓ Помощь":
        help_text = (
            "🤖 **Open Claw Agent - помощь**\n\n"
            "**Доступные команды:**\n"
            "• /start, /help - показать справку\n"
            "• /menu - показать главное меню\n"
            "• /status - статус ПК\n"
            "• /screenshot - скриншот\n"
            "• /check - проверить компоненты\n\n"
            "**Или просто пиши обычным языком:**\n"
            "• \"какой статус пк?\"\n"
            "• \"найди файл диплом\"\n"
            "• \"открой VS Code\"\n"
            "• \"добавь встречу завтра в 15:00\"\n"
            "• \"спроси мне про Python\"\n"
            "• Отправь голосовое сообщение\n\n"
            "**Используй кнопки снизу для быстрого доступа** 👇"
        )
        await update.message.reply_text(help_text)
        return
