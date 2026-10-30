"""
Detect installed applications and resolve executable paths.
"""

from __future__ import annotations

import os
from pathlib import Path
from time import monotonic

try:
    import psutil
except Exception:
    psutil = None


ALIASES = {
    "code": "vscode",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "steam": "steam",
    "стим": "steam",
    "браузер": "chrome",
    "проводник": "explorer",
    "блокнот": "notepad",
}

COMMON_APP_PATHS = {
    "vscode": [
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
        r"C:\Users\koall\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    ],
    "pycharm": [
        r"C:\Program Files\JetBrains\PyCharm 2024.3\bin\pycharm64.exe",
        r"C:\Program Files\JetBrains\PyCharm 2024.2\bin\pycharm64.exe",
        r"C:\Program Files\JetBrains\PyCharm 2024.1\bin\pycharm64.exe",
        r"C:\Program Files\JetBrains\PyCharm Community Edition 2024.3\bin\pycharm64.exe",
    ],
    "steam": [
        r"C:\Program Files (x86)\Steam\steam.exe",
        r"C:\Program Files\Steam\steam.exe",
        r"D:\Steam\steam.exe",
        r"E:\Steam\steam.exe",
    ],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "telegram": [r"C:\Users\koall\AppData\Local\Telegram Desktop\Telegram.exe"],
    "discord": [r"C:\Users\koall\AppData\Local\Discord\Discord.exe"],
    "notepad": [r"C:\Windows\System32\notepad.exe"],
    "explorer": [r"C:\Windows\explorer.exe"],
}

_SCAN_CACHE: dict[str, str] = {}
_CACHE_TS = 0.0
_CACHE_TTL_SEC = 120.0


def _available_drives() -> list[str]:
    drives: list[str] = []
    if psutil:
        try:
            for part in psutil.disk_partitions(all=False):
                mount = part.mountpoint
                if os.path.exists(mount):
                    drives.append(mount)
        except Exception:
            pass
    if not drives:
        for drive in ("C:\\", "D:\\", "E:\\", "F:\\", "G:\\"):
            if os.path.exists(drive):
                drives.append(drive)
    uniq: list[str] = []
    for item in drives:
        if item not in uniq:
            uniq.append(item)
    return uniq


def _normalize_name(app_name: str) -> str:
    key = app_name.lower().strip()
    return ALIASES.get(key, key)


def _scan_executable_by_name(app_name: str, max_results: int = 20) -> list[str]:
    target = _normalize_name(app_name)
    hits: list[str] = []
    candidate_names = {
        f"{target}.exe",
        f"{target}64.exe",
        f"{target}32.exe",
    }
    if target == "vscode":
        candidate_names.add("code.exe")
    if target == "pycharm":
        candidate_names.add("pycharm64.exe")

    roots = []
    for drive in _available_drives():
        roots.extend(
            [
                Path(drive) / "Program Files",
                Path(drive) / "Program Files (x86)",
                Path(drive) / "Users",
            ]
        )
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("*.exe"):
                name = path.name.lower()
                if name in candidate_names or target in name:
                    hits.append(str(path))
                    if len(hits) >= max_results:
                        return hits
        except Exception:
            continue
    return hits


def _refresh_cache(force: bool = False):
    global _CACHE_TS
    if not force and (monotonic() - _CACHE_TS) < _CACHE_TTL_SEC and _SCAN_CACHE:
        return
    _SCAN_CACHE.clear()
    for app, paths in COMMON_APP_PATHS.items():
        for path in paths:
            if os.path.isfile(path):
                _SCAN_CACHE[app] = path
                break
    _CACHE_TS = monotonic()


def find_app_path(app_name: str) -> str | None:
    key = _normalize_name(app_name)
    _refresh_cache()
    cached = _SCAN_CACHE.get(key)
    if cached and os.path.isfile(cached):
        return cached

    # direct known paths
    for path in COMMON_APP_PATHS.get(key, []):
        if os.path.isfile(path):
            _SCAN_CACHE[key] = path
            return path

    # dynamic scan
    hits = _scan_executable_by_name(key, max_results=5)
    if hits:
        _SCAN_CACHE[key] = hits[0]
        return hits[0]

    return None


def get_installed_apps() -> dict[str, str | None]:
    # Fast path: only check known locations, do not run full disk scans.
    _refresh_cache(force=True)
    result: dict[str, str | None] = {}
    for app, paths in COMMON_APP_PATHS.items():
        found = None
        for path in paths:
            if os.path.isfile(path):
                found = path
                break
        result[app] = found
    return result


def get_installed_apps_list() -> list[str]:
    installed = get_installed_apps()
    return sorted([name for name, path in installed.items() if path])


def format_apps_list() -> str:
    installed = get_installed_apps()
    available = [f"[ok] {name}" for name, path in installed.items() if path]
    unavailable = [f"[x] {name}" for name, path in installed.items() if not path]
    text = "Installed apps:\n\n"
    text += "\n".join(available) if available else "No known apps found"
    if unavailable:
        text += "\n\nNot found:\n" + "\n".join(unavailable[:6])
    return text
