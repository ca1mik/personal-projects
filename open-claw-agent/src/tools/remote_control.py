"""
Remote desktop control helpers.
"""

from __future__ import annotations

import base64
import os
import re
import subprocess
from pathlib import Path

import requests

try:
    import pyautogui

    PYAUTOGUI_AVAILABLE = True
except Exception:
    PYAUTOGUI_AVAILABLE = False


def is_remote_control_available() -> bool:
    return PYAUTOGUI_AVAILABLE


def move_mouse(x: int, y: int) -> tuple[bool, str]:
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui is not installed"
    try:
        pyautogui.moveTo(x, y, duration=0.4)
        return True, f"Mouse moved to ({x}, {y})"
    except Exception as exc:
        return False, str(exc)


def mouse_click(x: int | None = None, y: int | None = None, button: str = "left") -> tuple[bool, str]:
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui is not installed"
    try:
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)
        return True, f"Mouse {button} click completed"
    except Exception as exc:
        return False, str(exc)


def keyboard_press(key: str) -> tuple[bool, str]:
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui is not installed"
    try:
        pyautogui.press(key)
        return True, f"Key '{key}' pressed"
    except Exception:
        return False, f"Unknown key: {key}"


def keyboard_type(text: str, interval: float = 0.04) -> tuple[bool, str]:
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui is not installed"
    try:
        pyautogui.typewrite(text, interval=interval)
        return True, "Text typed"
    except Exception as exc:
        return False, str(exc)


def hotkey(keys: list[str]) -> tuple[bool, str]:
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui is not installed"
    try:
        pyautogui.hotkey(*keys)
        return True, f"Hotkey {' + '.join(keys)} executed"
    except Exception as exc:
        return False, str(exc)


def open_application(app_name: str) -> tuple[bool, str]:
    from src.tools.app_detector import find_app_path

    key = app_name.lower().strip()
    exe_path = find_app_path(key)
    if exe_path:
        try:
            subprocess.Popen([exe_path], shell=False)
            return True, f"Opening: {key}"
        except Exception as exc:
            return False, f"Failed to open {key}: {exc}"

    # URI/path fallbacks
    uri_fallbacks = {
        "steam": "steam://open/main",
        "telegram": "tg://",
        "discord": "discord://",
    }
    uri = uri_fallbacks.get(key)
    if uri:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", uri], shell=False)
            return True, f"Opening via URI: {key}"
        except Exception as exc:
            return False, f"Failed to open {key}: {exc}"

    return False, f"Unsupported or not found app: {app_name}"


def _image_to_base64(image_path: Path) -> str:
    with image_path.open("rb") as fp:
        return base64.b64encode(fp.read()).decode("utf-8")


def _parse_xy(reply: str) -> tuple[int, int] | None:
    # expected format "x,y"
    m = re.search(r"(-?\d+)\s*[,; ]\s*(-?\d+)", reply)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def click_on_screen_target(screen_path: Path, target_description: str) -> tuple[bool, str]:
    """
    Uses Ollama vision model to estimate click coordinates and performs a click.
    """
    if not PYAUTOGUI_AVAILABLE:
        return False, "pyautogui is not installed"
    if not screen_path.exists():
        return False, "screenshot file does not exist"

    try:
        b64 = _image_to_base64(screen_path)
        prompt = (
            "You see a desktop screenshot. Find the best click point for this target: "
            f"'{target_description}'. Return ONLY coordinates in format x,y with integers."
        )
        preferred = os.getenv("VISION_MODEL", "qwen3-vl:8b").strip() or "qwen3-vl:8b"
        models = [preferred, "qwen3-vl:8b", "llava:7b"]
        last_answer = ""
        for model in models:
            payload = {
                "model": model,
                "prompt": prompt,
                "images": [b64],
                "stream": False,
            }
            resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
            if resp.status_code != 200:
                continue
            answer = resp.json().get("response", "").strip()
            last_answer = answer
            xy = _parse_xy(answer)
            if not xy:
                continue
            x, y = xy
            pyautogui.click(x, y, button="left")
            return True, f"Clicked target '{target_description}' at ({x}, {y}) using {model}"
        return False, f"Could not parse coordinates from vision model response: {last_answer[:160]}"
    except Exception as exc:
        return False, f"Vision click error: {exc}"
