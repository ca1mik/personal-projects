"""
Интерактивное меню с кнопками внизу (ReplyKeyboardMarkup).
"""

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu keyboard - appears at the bottom of screen."""
    buttons = [
        ["📊 Статус", "🖼️ Скрин"],
        ["🔍 Файл", "📸 Фото"],
        ["📅 Календарь", "📝 Заметка"],
        ["🧠 Спросить AI", "🎯 Исследовать"],
        ["🚀 Открыть приложение", "📧 Письмо"],
        ["💡 Рекомендации", "❓ Помощь"],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)


async def show_main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Display main menu with buttons."""
    menu_text = (
        "🤖 **Open Claw Agent**\n\n"
        "Выбери действие или просто пиши обычным языком:\n"
        "• \"найди файл диплом\"\n"
        "• \"открой VSCode\"\n"
        "• \"добавь встречу завтра в 15:00\"\n"
        "• \"скрин экрана\"\n\n"
        "Используй кнопки снизу 👇"
    )
    
    keyboard = get_main_menu_keyboard()
    
    if update.message:
        await update.message.reply_text(menu_text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text=menu_text)


# Структура меню
MENU_STRUCTURE = {
    "main": {
        "text": "🤖 Open Claw Agent - главное меню",
        "buttons": [
            ("📊 Информация", "info"),
            ("🔍 Поиск", "search"),
            ("📧 Связь и документы", "communication"),
            ("🖱️ Управление ПК", "control"),
            ("🧠 AI помощник", "ai"),
        ]
    },
    
    "info": {
        "text": "📊 Информация о компьютере",
        "buttons": [
            ("📈 Статус ПК", "cmd:status"),
            ("🖼️ Скриншот", "cmd:screenshot"),
            ("💾 Инфо о системе", "cmd:pc_info"),
            ("← Назад", "main"),
        ]
    },
    
    "search": {
        "text": "🔍 Поиск на компьютере",
        "buttons": [
            ("📄 Файлы", "search:files"),
            ("🖼️ Фото", "search:photos"),
            ("📝 Документы", "search:documents"),
            ("🎵 Музыка", "search:music"),
            ("← Назад", "main"),
        ]
    },
    
    "search:files": {
        "text": "📄 Поиск файлов\n\nСкажи название файла в следующем сообщении",
        "buttons": [
            ("← Назад", "search"),
        ]
    },
    
    "search:photos": {
        "text": "🖼️ Поиск фото\n\nОпиши что ищешь в следующем сообщении:\n✓ \"фото девушки\"\n✓ \"пейзажи\"\n✓ \"вчернаашние фото\"\n",
        "buttons": [
            ("← Назад", "search"),
        ]
    },
    
    "search:documents": {
        "text": "📝 Поиск в документах\n\nЧто ищешь? (слово, название, фраза)",
        "buttons": [
            ("← Назад", "search"),
        ]
    },
    
    "search:music": {
        "text": "🎵 Поиск музыки\n\nЧто ищешь? (название, артист, жанр)",
        "buttons": [
            ("← Назад", "search"),
        ]
    },
    
    "communication": {
        "text": "📧 Связь и документы",
        "buttons": [
            ("📧 Отправить письмо", "cmd:email"),
            ("📅 Календарь", "calendar"),
            ("📝 Заметки", "notes"),
            ("← Назад", "main"),
        ]
    },
    
    "calendar": {
        "text": "📅 Календарь",
        "buttons": [
            ("➕ Добавить встречу", "cmd:calendar_add"),
            ("👀 Просмотр встреч", "cmd:calendar_view"),
            ("← Назад", "communication"),
        ]
    },
    
    "notes": {
        "text": "📝 Заметки",
        "buttons": [
            ("➕ Новая заметка", "cmd:note_create"),
            ("📖 Мои заметки", "cmd:notes_list"),
            ("← Назад", "communication"),
        ]
    },
    
    "control": {
        "text": "🖱️ Управление ПК",
        "buttons": [
            ("🖱️ Мышь", "control:mouse"),
            ("⌨️ Клавиатура", "control:keyboard"),
            ("🐳 Docker", "cmd:docker"),
            ("← Назад", "main"),
        ]
    },
    
    "control:mouse": {
        "text": "🖱️ Управление мышью\n\nЧто ты хочешь?\n• Переместить мышь\n• Кликнуть\n• Двойной клик",
        "buttons": [
            ("➡️ Переместить", "mouse:move"),
            ("🔘 Кликнуть", "mouse:click"),
            ("🔘🔘 Двойной клик", "mouse:double"),
            ("← Назад", "control"),
        ]
    },
    
    "mouse:move": {
        "text": "🖱️ Переместить мышь\n\nНапиши координаты: 'X Y'\nПример: '500 300'",
        "buttons": [
            ("← Назад", "control:mouse"),
        ]
    },
    
    "mouse:click": {
        "text": "🔘 Кликнуть мышью\n\nНапиши координаты: 'X Y'\nПример: '500 300'",
        "buttons": [
            ("← Назад", "control:mouse"),
        ]
    },
    
    "mouse:double": {
        "text": "🔘🔘 Двойной клик\n\nНапиши координаты: 'X Y'\nПример: '500 300'",
        "buttons": [
            ("← Назад", "control:mouse"),
        ]
    },
    
    "control:keyboard": {
        "text": "⌨️ Управление клавиатурой\n\nЧто ты хочешь напечатать?",
        "buttons": [
            ("← Назад", "control"),
        ]
    },
    
    "ai": {
        "text": "🧠 AI помощник",
        "buttons": [
            ("💬 Вопрос", "cmd:ask"),
            ("📚 Исследование", "cmd:research"),
            ("← Назад", "main"),
        ]
    },
}


def get_menu_keyboard(menu_key: str) -> InlineKeyboardMarkup:
    """Получить клавиатуру для меню"""
    if menu_key not in MENU_STRUCTURE:
        menu_key = "main"
    
    menu = MENU_STRUCTURE[menu_key]
    buttons = []
    
    for label, callback_data in menu["buttons"]:
        buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])
    
    return InlineKeyboardMarkup(buttons)


def get_menu_text(menu_key: str) -> str:
    """Получить текст меню"""
    if menu_key not in MENU_STRUCTURE:
        menu_key = "main"
    
    return MENU_STRUCTURE[menu_key]["text"]


async def show_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE, menu_key: str = "main"):
    """Показать меню"""
    text = get_menu_text(menu_key)
    keyboard = get_menu_keyboard(menu_key)
    
    if update.callback_query:
        # Редактируем существующее сообщение
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=keyboard
        )
    else:
        # Отправляем новое сообщение
        await update.message.reply_text(
            text=text,
            reply_markup=keyboard
        )
