"""
Rule-first NLU classifier with optional Ollama fallback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


SEND_VERBS = ["скинь", "пришли", "отправь", "send"]


@dataclass
class Intent:
    intent: str
    confidence: float
    entities: dict
    raw_text: str


class NLUEngine:
    def __init__(self):
        self.keywords = {
            "status": ["status", "статус", "состояние", "пк", "компьютер"],
            "screenshot": ["screenshot", "скрин", "скриншот", "экран"],
            "find": ["find", "найди", "поищи", "найти", "файл", "фото", "документ"],
            "email_send": ["почта", "email", "mail", "письмо"],
            "file_to_chat": ["в чат", "пришли файл", "скинь файл", "file to chat", "с компа"],
            "calendar_add": ["календар", "встреч", "событ", "запланируй", "appointment", "event"],
            "calendar_free": ["свободн", "окно", "slot", "когда можно", "когда свободно"],
            "meeting_brief": ["бриф", "подготов", "что учесть", "чеклист", "prepare meeting"],
            "note_create": ["замет", "note", "запомни", "запиши"],
            "memory_set": ["запомни", "remember this", "запиши в память", "сохрани это"],
            "memory_get": ["что ты помнишь", "что помнишь", "my profile", "что знаешь обо мне"],
            "research": ["исследуй", "анализ", "research", "найди информацию"],
            "proactive_research_config": ["следи за", "мониторь", "наблюдай за", "track topic"],
            "open_app": ["открой", "запусти", "open", "launch", "steam", "стим", "chrome", "vscode", "pycharm"],
            "click_ui": ["нажми", "кликни", "click", "press"],
            "ask": ["что", "как", "почему", "расскажи", "объясни"],
        }

    async def analyze(self, text: str, use_ollama: bool = True) -> Intent:
        text_lower = text.lower().strip()
        intent, confidence = self._fast_match(text_lower)
        if use_ollama and confidence < 0.45:
            intent, confidence = await self._ollama_classify(text)
        entities = self._extract_entities(text, intent)
        return Intent(intent=intent, confidence=confidence, entities=entities, raw_text=text)

    def _fast_match(self, text_lower: str) -> tuple[str, float]:
        has_email = bool(re.search(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", text_lower))
        has_send = any(v in text_lower for v in SEND_VERBS)

        if any(x in text_lower for x in ["что ты помнишь", "что помнишь", "что знаешь обо мне", "my profile"]):
            return "memory_get", 0.97
        if any(x in text_lower for x in ["запомни", "запиши в память", "remember this"]):
            return "memory_set", 0.95
        if any(x in text_lower for x in ["следи за", "мониторь", "наблюдай за", "track topic"]):
            return "proactive_research_config", 0.95
        if "свобод" in text_lower and any(x in text_lower for x in ["календар", "окно", "slot", "когда"]):
            return "calendar_free", 0.94
        if any(x in text_lower for x in ["подготов", "бриф", "чеклист"]) and "встреч" in text_lower:
            return "meeting_brief", 0.93
        if any(x in text_lower for x in ["нажми", "кликни", "click", "press"]):
            return "click_ui", 0.95
        if has_send and (has_email or "почт" in text_lower or "email" in text_lower):
            return "email_send", 0.95
        if has_send and (
            "в чат" in text_lower
            or "с компа" in text_lower
            or "с компьют" in text_lower
            or "файл" in text_lower
        ):
            return "file_to_chat", 0.92

        best_intent = "ask"
        best_score = 0.0
        for intent, words in self.keywords.items():
            score = sum(1.0 for word in words if word in text_lower)
            if score > best_score:
                best_intent = intent
                best_score = score
        confidence = min(1.0, best_score / 2.2) if best_score > 0 else 0.25
        return best_intent, confidence

    async def _ollama_classify(self, text: str) -> tuple[str, float]:
        try:
            from src.tools.ollama_agent import ask_ollama

            prompt = (
                "Classify user message into one intent and return exactly: intent:score\n"
                "Intents: status,screenshot,find,email_send,file_to_chat,calendar_add,calendar_free,"
                "meeting_brief,note_create,memory_set,memory_get,research,proactive_research_config,"
                "open_app,click_ui,ask\n"
                f"Message: {text}"
            )
            ok, response = await ask_ollama(prompt)
            if not ok or ":" not in response:
                return "ask", 0.4
            name, score_part = response.split(":", 1)
            score_match = re.search(r"\d+(?:\.\d+)?", score_part)
            if not score_match:
                return "ask", 0.4
            score = float(score_match.group(0))
            return name.strip().lower(), max(0.0, min(1.0, score))
        except Exception:
            return "ask", 0.4

    def _extract_entities(self, text: str, intent: str) -> dict:
        out: dict = {}
        text_lower = text.lower()

        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
        if email_match:
            out["email"] = email_match.group(0)

        if intent in {"find", "email_send", "file_to_chat"}:
            cleaned = re.sub(
                r"^(найди|поищи|найти|пришли|скинь|отправь|send)\s+",
                "",
                text_lower,
                flags=re.IGNORECASE,
            ).strip()
            cleaned = re.sub(
                r"\b(файл|файлы|фото|документ|документы|на|в|чат|почту|с|компа|компьютера|мой|моя|моего|мне|please|пожалуйста)\b",
                " ",
                cleaned,
            )
            cleaned = re.sub(
                r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b",
                " ",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?:;")
            if cleaned:
                out["filename"] = cleaned

        if intent == "calendar_add":
            out["description"] = re.sub(
                r"^(добавь|запланируй|создай)\s+",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()[:220]

        if intent == "calendar_free":
            out["date_query"] = text[:120]

        if intent == "meeting_brief":
            out["event_hint"] = re.sub(
                r"^(подготовь|сделай|дай)\s+",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()[:220]

        if intent == "note_create":
            out["content"] = text[:500]

        if intent == "memory_set":
            payload = re.sub(
                r"^(запомни|запиши в память|remember this|сохрани это)\s*[:,\-]?\s*",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
            out["memory_text"] = payload or text

        if intent == "research":
            out["topic"] = re.sub(
                r"^(исследуй|проанализируй|research)\s+",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()[:220]

        if intent == "proactive_research_config":
            cleaned = re.sub(
                r"^(следи за|мониторь|наблюдай за|track topic)\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
            items = [x.strip() for x in re.split(r",|;| и ", cleaned) if x.strip()]
            if items:
                out["topics"] = items

        if intent == "open_app":
            for candidate in [
                "steam",
                "chrome",
                "edge",
                "browser",
                "explorer",
                "notepad",
                "telegram",
                "discord",
                "pycharm",
                "vscode",
                "firefox",
            ]:
                if candidate in text_lower:
                    out["app_name"] = candidate
                    break
            if "стим" in text_lower and "app_name" not in out:
                out["app_name"] = "steam"
            if "браузер" in text_lower and "app_name" not in out:
                out["app_name"] = "chrome"
            if "проводник" in text_lower and "app_name" not in out:
                out["app_name"] = "explorer"

        if intent == "click_ui":
            target = re.sub(r"^(нажми|кликни|click|press)\s+(на|по)?\s*", "", text_lower).strip()
            if target:
                out["target"] = target

        return out

