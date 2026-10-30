from __future__ import annotations

from typing import Literal

StartAction = Literal[
    "home",
    "booking",
    "generate",
    "chatgpt",
    "deposit",
    "portfolio",
    "examples",
    "contacts",
]

_ALIASES: dict[str, StartAction] = {
    "": "home",
    "home": "home",
    "menu": "home",
    "start": "home",
    "booking": "booking",
    "book": "booking",
    "request": "booking",
    "lead": "booking",
    "generate": "generate",
    "gen": "generate",
    "idea": "generate",
    "sketch": "generate",
    "chatgpt": "chatgpt",
    "gpt": "chatgpt",
    "prompt": "chatgpt",
    "deposit": "deposit",
    "pay": "deposit",
    "payment": "deposit",
    "reserve": "deposit",
    "portfolio": "portfolio",
    "promo": "portfolio",
    "materials": "portfolio",
    "examples": "examples",
    "works": "examples",
    "gallery": "examples",
    "contacts": "contacts",
    "contact": "contacts",
    "master": "contacts",
    "write": "contacts",
}


def extract_start_argument(text: str | None) -> str:
    if not text:
        return ""
    normalized = " ".join(text.strip().split())
    if not normalized.lower().startswith("/start"):
        return ""
    parts = normalized.split(" ", 1)
    return parts[1] if len(parts) == 2 else ""


def resolve_start_action(argument: str | None) -> StartAction:
    token = (argument or "").strip().lower().replace("-", "_")
    return _ALIASES.get(token, "home")
