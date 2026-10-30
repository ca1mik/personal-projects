"""
Модуль для интерактивной GUI автоматизации.
- Открытие приложений
- Выполнение действий (клик, набор текста)
- Скриншот после каждого действия
- Управляемые сценарии (Steam, браузер и т.д.)
"""

import subprocess
import time
import re
from pathlib import Path
from typing import Optional

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False


# Карта приложений с путями и параметрами
APP_REGISTRY = {
    "steam": {
        "paths": [
            r"C:\Program Files (x86)\Steam\steam.exe",
            r"C:\Program Files\Steam\steam.exe",
            r"D:\SteamLibrary\steamapps\common\Steam\steam.exe",
            r"E:\SteamLibrary\steamapps\common\Steam\steam.exe",
        ],
        "protocol": "steam://",
    },
    "chrome": {
        "paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "protocol": None,
    },
    "firefox": {
        "paths": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
        "protocol": None,
    },
    "edge": {
        "paths": [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "protocol": None,
    },
    "explorer": {
        "paths": [
            r"C:\Windows\explorer.exe",
        ],
        "protocol": None,
    },
    "notepad": {
        "paths": [
            r"C:\Windows\System32\notepad.exe",
        ],
        "protocol": None,
    },
    "telegram": {
        "paths": [
            r"C:\Users\koall\AppData\Local\Telegram Desktop\Telegram.exe",
            r"C:\Users\koall\AppData\Roaming\Telegram Desktop\Telegram.exe",
        ],
        "protocol": "tg://",
    },
    "discord": {
        "paths": [
            r"C:\Users\koall\AppData\Local\Discord\app-1.x.x\Discord.exe",
            r"C:\Users\koall\AppData\Local\Discord\app\Discord.exe",
        ],
        "protocol": "discord://",
    },
    "pycharm": {
        "paths": [
            r"C:\Program Files\JetBrains\PyCharm 2024.1\bin\pycharm64.exe",
            r"C:\Program Files\JetBrains\PyCharm 2023.3\bin\pycharm64.exe",
            r"C:\Program Files\JetBrains\PyCharm Community Edition\bin\pycharm.exe",
        ],
        "protocol": None,
    },
    "vscode": {
        "paths": [
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Users\koall\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        ],
        "protocol": None,
    },
    "code": {
        "paths": [
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Users\koall\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        ],
        "protocol": None,
    },
}


def find_app_executable(app_name: str) -> Optional[str]:
    """
    Ищет исполняемый файл приложения по имени
    """
    app_name_lower = app_name.lower().strip()
    
    if app_name_lower in APP_REGISTRY:
        entry = APP_REGISTRY[app_name_lower]
        for path in entry.get("paths", []):
            if Path(path).exists():
                return path
    
    return None


async def open_app(app_name: str, args: list[str] = None) -> tuple[bool, str]:
    """
    Открывает приложение по имени
    """
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui не установлен"
    
    app_path = find_app_executable(app_name)
    if not app_path:
        return False, f"Приложение '{app_name}' не найдено"
    
    try:
        if args:
            subprocess.Popen([app_path] + args)
        else:
            subprocess.Popen([app_path])
        
        time.sleep(2)  # Даём время на загрузку
        return True, f"'{app_name}' открыт"
    except Exception as e:
        return False, f"Ошибка открытия: {str(e)[:100]}"


async def click_at(x: int, y: int) -> tuple[bool, str]:
    """
    Клик в координаты экрана
    """
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui не установлен"
    
    try:
        pyautogui.click(x, y)
        time.sleep(0.5)
        return True, f"Клик в ({x}, {y})"
    except Exception as e:
        return False, f"Ошибка клика: {str(e)[:50]}"


async def type_text(text: str) -> tuple[bool, str]:
    """
    Вводит текст в активное окно
    """
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui не установлен"
    
    try:
        # pyautogui не умеет кириллицу напрямую, используем clipboard
        import subprocess
        # Копируем текст в буфер обмена
        process = subprocess.Popen(
            ["powershell", "-Command", f"[System.Windows.Forms.SendKeys]::SendWait('{text}')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        process.wait(timeout=2)
        time.sleep(0.5)
        return True, f"Текст введён: {text[:30]}"
    except Exception as e:
        return False, f"Ошибка ввода: {str(e)[:50]}"


async def press_key(key: str) -> tuple[bool, str]:
    """
    Нажимает клавишу
    """
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui не установлен"
    
    try:
        pyautogui.press(key.lower())
        time.sleep(0.2)
        return True, f"Клавиша '{key}' нажата"
    except Exception as e:
        return False, f"Ошибка: {str(e)[:50]}"


async def hotkey(keys: str) -> tuple[bool, str]:
    """
    Комбинация клавиш (например "ctrl+c")
    """
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui не установлен"
    
    try:
        parts = keys.lower().split("+")
        pyautogui.hotkey(*parts)
        time.sleep(0.2)
        return True, f"Комбинация '{keys}' нажата"
    except Exception as e:
        return False, f"Ошибка: {str(e)[:50]}"


# Сценарии автоматизации
SCENARIOS = {
    "steam_search_game": """
        Открыть Steam
        Клик на поиск
        Ввести имя игры (будет передано как аргумент)
        Скриншот результатов поиска
    """,
    "open_and_download": """
        Открыть браузер
        Перейти на URL (будет передано как аргумент)
        Скриншот страницы
        Клик на кнопку загрузки
        Скриншот диалога загрузки
    """,
    "email_compose": """
        Открыть почту
        Клик на "Новое письмо"
        Ввести адрес получателя
        Ввести тему и текст
        Скриншот черновика
        Отправить
    """,
}


async def execute_scenario(scenario_name: str, params: dict = None) -> tuple[bool, list[str]]:
    """
    Выполняет заготовленный сценарий
    Возвращает список скриншотов
    """
    from src.tools.screenshot import make_screenshot
    from src.config import load_config
    
    cfg = load_config()
    scenario_dir = cfg.workdir / "scenarios"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    
    screenshots = []
    
    try:
        if scenario_name == "steam_search_game":
            game_name = (params or {}).get("game_name", "Dota 2")
            
            ok, msg = await open_app("steam")
            if not ok:
                return False, [msg]
            
            time.sleep(3)
            
            # Клик на поиск в Steam (примерные координаты, могут отличаться)
            await click_at(700, 300)
            time.sleep(0.5)
            await type_text(game_name)
            time.sleep(1)
            
            # Скриншот
            ss_path = make_screenshot(scenario_dir)
            screenshots.append(str(ss_path))
            
            return True, screenshots
        
        elif scenario_name == "browser_open":
            url = (params or {}).get("url", "https://google.com")
            
            ok, msg = await open_app("chrome")
            if not ok:
                return False, [msg]
            
            time.sleep(3)
            
            # Адресная строка Ctrl+L
            await hotkey("ctrl+l")
            time.sleep(0.5)
            await type_text(url)
            await press_key("enter")
            time.sleep(3)
            
            # Скриншот
            ss_path = make_screenshot(scenario_dir)
            screenshots.append(str(ss_path))
            
            return True, screenshots
        
        else:
            return False, [f"Неизвестный сценарий: {scenario_name}"]
    
    except Exception as e:
        return False, [f"Ошибка сценария: {str(e)[:100]}"]


async def interactive_gui_guide(instructions: str) -> tuple[bool, str]:
    """
    Интерактивный гайд для пользователя
    Анализирует инструкции и предлагает шаги
    """
    try:
        from src.tools.ollama_agent import ask_ollama
        
        system_prompt = (
            "Ты помощник для GUI автоматизации. "
            "Пользователь даёт инструкцию что он хочет сделать. "
            "Разбей это на конкретные шаги (открыть приложение, клик, ввод текста, скриншот). "
            "Формат ответа: каждый шаг на новой строке в виде: ДЕЙСТВИЕ: параметры"
        )
        
        prompt = f"{system_prompt}\n\nИнструкция: {instructions}"
        
        ok, response = await ask_ollama(prompt)
        if not ok:
            return False, response
        
        return True, response
    
    except Exception as e:
        return False, f"Ошибка: {str(e)[:100]}"

