"""
Smart text/voice handler for OpenClaw.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from src.tools.file_search import find_documents, find_files, find_photos
from src.tools.google_services import GoogleCalendarService, GoogleSheetsService
from src.tools.integrations import CalendarService, EmailService, NotesService
from src.tools.memory import ChatMemory, get_memory
from src.tools.ollama_agent import ask_ollama, test_ollama_available
from src.tools.remote_control import click_on_screen_target, open_application
from src.tools.screenshot import make_screenshot
from src.tools.self_research import (
    build_meeting_brief,
    research_topic,
    suggest_for_event,
    suggest_places_for_event,
)
from src.tools.speech_to_text import is_speech_recognition_available, transcribe_voice
from src.tools.status import get_status


RU_FIND_VERBS = ["найди", "поищи", "найти", "find"]
RU_FILLER_WORDS = {
    "файл",
    "файлы",
    "фото",
    "фотки",
    "документ",
    "документы",
    "на",
    "пк",
    "компе",
    "компьютере",
    "мой",
    "моя",
    "моего",
    "мне",
    "в",
    "чат",
    "почту",
    "с",
    "компа",
    "компьютера",
}
RU_PHOTO_MARKERS = ["фото", "фотки", "картинк", "изображен", "image", "picture", "photo"]
RU_DOC_MARKERS = ["документ", "контекст", "текст", "pdf", "doc"]
RU_MONTHS = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "мая": 5,
    "май": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _who(update: Update) -> tuple[int, int]:
    user_id = update.effective_user.id if update.effective_user else 0
    chat_id = update.effective_chat.id if update.effective_chat else 0
    return user_id, chat_id


def _extract_email(text: str) -> str | None:
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None


def _render_paths(title: str, paths: list[str]) -> str:
    if not paths:
        return f"{title}: nothing found"
    lines = [f"{title}: found {len(paths)} file(s)"]
    lines.extend(f"- {p}" for p in paths)
    return "\n".join(lines)


async def _send_text_or_file(update: Update, cfg, text: str, out_name: str):
    if len(text) <= 3500:
        await update.message.reply_text(text)
        return
    out_path = cfg.workdir / out_name
    out_path.write_text(text, encoding="utf-8")
    await update.message.reply_document(out_path.open("rb"), filename=out_path.name)


def _normalize_find_query(text: str) -> tuple[str, list[str]]:
    cleaned = text.lower().strip()
    for verb in RU_FIND_VERBS + ["send", "пришли", "скинь", "отправь"]:
        prefix = f"{verb} "
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    words = re.split(r"\s+", cleaned)
    tokens = [w for w in words if w and w not in RU_FILLER_WORDS]
    primary = " ".join(tokens).strip() or cleaned
    return primary, tokens


def _query_variants(primary: str, tokens: list[str]) -> list[str]:
    endings = ("а", "у", "е", "ой", "ого", "ому", "ами", "ями", "ов", "ев", "ы", "и")
    variants: list[str] = []
    for item in [primary] + tokens:
        token = item.strip()
        if not token:
            continue
        variants.append(token)
        for ending in endings:
            if token.endswith(ending) and len(token) - len(ending) >= 4:
                variants.append(token[: -len(ending)])
    uniq: list[str] = []
    for v in variants:
        if v not in uniq:
            uniq.append(v)
    return uniq


def _search_by_variants(search_fn, query: str, tokens: list[str], max_results: int = 20) -> list[str]:
    for variant in _query_variants(query, tokens):
        if len(variant) < 2:
            continue
        results = search_fn(variant, max_results=max_results)
        if results:
            return results
    return []


def _is_photo_query(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in RU_PHOTO_MARKERS)


def _is_document_query(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in RU_DOC_MARKERS)


def _extract_datetime_from_text(text: str) -> datetime | None:
    lowered = text.lower()
    now = datetime.now()
    hm = re.search(r"(\d{1,2})[:.](\d{2})", lowered)
    hour = int(hm.group(1)) if hm else 14
    minute = int(hm.group(2)) if hm else 0

    if "послезавтра" in lowered:
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=2)
    if "завтра" in lowered:
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=1)
    if "сегодня" in lowered:
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    dm = re.search(r"\b(\d{1,2})\s+([а-яa-z]+)", lowered)
    if not dm:
        return None
    day = int(dm.group(1))
    month_word = dm.group(2)
    month = None
    for key, value in RU_MONTHS.items():
        if month_word.startswith(key):
            month = value
            break
    if not month:
        return None
    year = now.year
    try:
        dt = datetime(year, month, day, hour, minute, 0)
        if dt < now:
            dt = datetime(year + 1, month, day, hour, minute, 0)
        return dt
    except ValueError:
        return None


def _extract_date_for_slots(text: str) -> str | None:
    dt = _extract_datetime_from_text(text)
    if dt:
        return dt.date().isoformat()
    lowered = text.lower()
    if "сегодня" in lowered:
        return datetime.now().date().isoformat()
    if "завтра" in lowered:
        return (datetime.now().date() + timedelta(days=1)).isoformat()
    return None


def _looks_like_send_to_chat(text: str) -> bool:
    lowered = text.lower()
    return ("в чат" in lowered or "мне в чат" in lowered) and any(
        x in lowered for x in ["файл", "пришли", "скинь", "отправь"]
    )


def _looks_like_click_instruction(text: str) -> bool:
    lowered = text.lower()
    return any(x in lowered for x in ["нажми", "кликни", "click", "press"])


def _proactive_topics_path(workdir: Path) -> Path:
    return workdir / "proactive_topics.json"


def _save_proactive_topics(workdir: Path, topics: list[str]):
    path = _proactive_topics_path(workdir)
    path.write_text(json.dumps({"topics": topics}, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_facts_to_sheet(cfg, user_id: int, chat_id: int, facts: list[dict]):
    if not facts:
        return
    if not getattr(cfg, "use_google_sheets_memory", False):
        return
    sheet_id = getattr(cfg, "google_memory_sheet_id", "").strip()
    if not sheet_id:
        return
    sheets = GoogleSheetsService(cfg.google_credentials_path, sheet_id)
    for fact in facts:
        sheets.append_memory_fact(
            user_id=user_id,
            chat_id=chat_id,
            category=fact.get("category", ""),
            key=fact.get("key", ""),
            value=fact.get("value", ""),
            source="auto_memory",
        )


async def _send_file_to_chat(update: Update, query: str, tokens: list[str], cfg) -> bool:
    results = _search_by_variants(find_files, query, tokens, max_results=10)
    if not results:
        await update.message.reply_text("File for chat was not found.")
        return False
    first = Path(results[0])
    if not first.exists():
        await update.message.reply_text("File path was found but file no longer exists.")
        return False
    await update.message.reply_document(first.open("rb"), filename=first.name)
    await update.message.reply_text(_render_paths("Matches", results))
    return True


async def _send_file_to_email(
    update: Update,
    cfg,
    file_query: str,
    file_tokens: list[str],
    email_to: str,
    body: str,
) -> tuple[bool, str]:
    matches = _search_by_variants(find_files, file_query, file_tokens, max_results=5)
    attachments = matches[:3] if matches else None
    svc = EmailService(cfg.email_smtp_server, cfg.email_smtp_port, cfg.email_address, cfg.email_password)
    ok, msg = svc.send_email(email_to, "File from OpenClaw", body, files=attachments)
    return ok, msg


def _calendar_service(cfg):
    if cfg.use_google_calendar:
        return GoogleCalendarService(cfg.google_credentials_path), True
    return CalendarService(cfg.calendar_dir), False


async def _create_calendar_flow(
    update: Update,
    cfg,
    memory: ChatMemory,
    user_id: int,
    chat_id: int,
    text: str,
    title: str | None = None,
):
    calendar, is_google = _calendar_service(cfg)
    event_dt = _extract_datetime_from_text(text)
    event_title = (title or text).strip()[:90] or "Event"

    if is_google:
        ok, msg = calendar.add_event(
            title=event_title,
            description=text,
            start_time=event_dt.isoformat() if event_dt else None,
        )
    else:
        ok, msg = calendar.add_event(
            title=event_title,
            description=text,
            date_str=event_dt.isoformat() if event_dt else None,
        )
    await update.message.reply_text(msg)
    if not ok:
        return ok

    memory.remember_fact(
        user_id=user_id,
        chat_id=chat_id,
        category="plans",
        key="latest_calendar_event",
        value=f"{event_title} | {event_dt.isoformat() if event_dt else 'no_time'}",
        source="calendar",
    )

    tips = suggest_for_event(text)
    await update.message.reply_text("Preparation tips:\n" + "\n".join(f"- {t}" for t in tips))

    if is_google:
        slot_date = event_dt.date().isoformat() if event_dt else None
        slot_ok, slot_msg, _slots = calendar.find_free_slots(slot_date, duration_minutes=60)
        if slot_ok:
            await update.message.reply_text(slot_msg)

    places_ok, places = await suggest_places_for_event(text)
    if places_ok:
        await _send_text_or_file(update, cfg, f"Place ideas:\n{places}", "place_ideas.txt")

    brief_ok, brief = await build_meeting_brief(
        event_title=event_title,
        event_description=text,
        event_start_iso=event_dt.isoformat() if event_dt else None,
        memory_summary=memory.summarize_profile(user_id, chat_id),
    )
    if brief_ok:
        await _send_text_or_file(update, cfg, f"Meeting brief:\n{brief}", "meeting_brief.txt")
    return True


async def _handle_awaiting(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    cfg = ctx.bot_data["cfg"]
    memory = get_memory()
    user_id, chat_id = _who(update)

    if ctx.user_data.pop("awaiting_file_search", False):
        query, tokens = _normalize_find_query(text)
        results = _search_by_variants(find_files, query, tokens)
        await _send_text_or_file(update, cfg, _render_paths("File search", results), "find_results.txt")
        return True

    if ctx.user_data.pop("awaiting_doc_search", False):
        query, tokens = _normalize_find_query(text)
        results = _search_by_variants(find_documents, query, tokens)
        await _send_text_or_file(update, cfg, _render_paths("Document search", results), "documents.txt")
        return True

    if ctx.user_data.pop("awaiting_photo_search", None):
        query, tokens = _normalize_find_query(text)
        results = _search_by_variants(find_photos, query, tokens)
        await _send_text_or_file(update, cfg, _render_paths("Photo search", results), "photos.txt")
        return True

    if ctx.user_data.pop("awaiting_open_app", False):
        app_name = text.lower().strip()
        for keyword in ["открой", "открыть", "запусти", "run", "open"]:
            app_name = app_name.replace(keyword, "").strip()
        if not app_name:
            await update.message.reply_text("App name is missing.")
            return True
        ok, msg = open_application(app_name)
        await update.message.reply_text(msg)
        if ok:
            shot = make_screenshot(cfg.workdir / "screens")
            await update.message.reply_document(shot.open("rb"), filename=shot.name)
        return True

    if ctx.user_data.pop("awaiting_email", False):
        to_addr = _extract_email(text)
        if not to_addr:
            await update.message.reply_text("Email address is missing.")
            return True
        query, tokens = _normalize_find_query(text)
        ok, msg = await _send_file_to_email(update, cfg, query, tokens, to_addr, text[:600])
        await update.message.reply_text(msg)
        return True

    if ctx.user_data.pop("awaiting_calendar", False):
        ok = await _create_calendar_flow(update, cfg, memory, user_id, chat_id, text)
        return ok

    if ctx.user_data.pop("awaiting_note", False):
        if cfg.use_google_notes:
            from src.tools.google_services import GoogleNotesService

            notes = GoogleNotesService(cfg.google_credentials_path)
            ok, msg = notes.create_note(text[:80], text)
        else:
            notes = NotesService(cfg.notes_dir)
            ok, msg = notes.create_note(text[:80], text)
        await update.message.reply_text(msg)
        if ok:
            stored = memory.remember_fact(user_id, chat_id, "notes", "latest_note", text[:220], "note")
            if stored:
                _append_facts_to_sheet(
                    cfg,
                    user_id,
                    chat_id,
                    [{"category": "notes", "key": "latest_note", "value": text[:220]}],
                )
        return True

    if ctx.user_data.pop("awaiting_ask", False):
        ok, answer = await ask_ollama(text)
        await _send_text_or_file(update, cfg, answer, "ask_response.txt")
        return True

    if ctx.user_data.pop("awaiting_research", False):
        ok, answer = await research_topic(text, depth="deep")
        await _send_text_or_file(update, cfg, answer, "research.txt")
        return True

    return False


async def handle_smart_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = ctx.bot_data.get("cfg")
    sec = ctx.bot_data.get("sec")
    db = ctx.bot_data.get("db")
    nlu = ctx.bot_data.get("nlu")
    memory = get_memory()

    if not all([cfg, sec, db]):
        await update.message.reply_text("System is not initialized")
        return

    user_id, chat_id = _who(update)
    if not sec.is_allowed(user_id, chat_id):
        await update.message.reply_text("Access denied.")
        return

    active_chats = ctx.bot_data.setdefault("active_chats", set())
    active_chats.add(chat_id)

    if update.message.voice:
        if not is_speech_recognition_available():
            await update.message.reply_text("SpeechRecognition is unavailable.")
            return
        waiting = await update.message.reply_text("Transcribing voice...")
        try:
            voice_file = await ctx.bot.get_file(update.message.voice.file_id)
            voice_path = cfg.workdir / f"voice_{user_id}_{chat_id}.ogg"
            await voice_file.download_to_drive(voice_path)
            ok, text = await transcribe_voice(voice_path)
            await waiting.delete()
            if not ok:
                await update.message.reply_text(text)
                db.log(user_id, chat_id, "voice_transcribe", False, text)
                return
            await update.message.reply_text(f"Recognized: {text}")
        except Exception as exc:
            await waiting.delete()
            await update.message.reply_text(f"Voice error: {exc}")
            db.log(user_id, chat_id, "voice_transcribe", False, str(exc))
            return
    elif update.message.text:
        text = update.message.text.strip()
    else:
        return

    memory.add_message(user_id, chat_id, "user", text)
    auto_facts = memory.auto_extract_and_store(user_id, chat_id, text, source="message")
    _append_facts_to_sheet(cfg, user_id, chat_id, auto_facts)

    if await _handle_awaiting(update, ctx, text):
        db.log(user_id, chat_id, "smart_awaiting", True, text[:200])
        return

    try:
        analyzed = await nlu.analyze(text, use_ollama=True) if nlu else None
        intent_name = analyzed.intent if analyzed else "ask"
        entities = analyzed.entities if analyzed else {}
        lowered = text.lower()

        if intent_name == "status":
            await update.message.reply_text(get_status())
            db.log(user_id, chat_id, "smart_status", True, None)
            return

        if intent_name == "screenshot":
            path = make_screenshot(cfg.workdir / "screens")
            await update.message.reply_document(path.open("rb"), filename=path.name)
            db.log(user_id, chat_id, "smart_screenshot", True, str(path))
            return

        if intent_name == "open_app":
            app_name = entities.get("app_name", "")
            if not app_name and "стим" in lowered:
                app_name = "steam"
            if not app_name and "браузер" in lowered:
                app_name = "chrome"
            if not app_name and "проводник" in lowered:
                app_name = "explorer"
            if not app_name:
                await update.message.reply_text("Specify app: steam/chrome/explorer/pycharm/vscode")
                return
            ok, msg = open_application(app_name)
            await update.message.reply_text(msg)
            if ok:
                shot = make_screenshot(cfg.workdir / "screens")
                await update.message.reply_document(shot.open("rb"), filename=shot.name)
            db.log(user_id, chat_id, "smart_open_app", ok, app_name)
            return

        if intent_name == "calendar_add":
            title = entities.get("description", text[:90])
            ok = await _create_calendar_flow(update, cfg, memory, user_id, chat_id, text, title=title)
            db.log(user_id, chat_id, "smart_calendar_add", ok, title)
            return

        if intent_name == "calendar_free":
            calendar, is_google = _calendar_service(cfg)
            if not is_google:
                await update.message.reply_text("Free-slot analysis works with Google Calendar mode.")
                return
            date_str = _extract_date_for_slots(entities.get("date_query", text))
            ok, msg, _slots = calendar.find_free_slots(date_str, duration_minutes=60)
            await update.message.reply_text(msg)
            db.log(user_id, chat_id, "smart_calendar_free", ok, date_str or "today")
            return

        if intent_name == "meeting_brief":
            calendar, is_google = _calendar_service(cfg)
            if is_google:
                ok_events, events = calendar.list_events_raw(days_ahead=14)
                if ok_events and isinstance(events, list) and events:
                    ev = events[0]
                    title = ev.get("summary", "Upcoming meeting")
                    start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", ""))
                    desc = ev.get("description", entities.get("event_hint", text))
                    ok, brief = await build_meeting_brief(
                        event_title=title,
                        event_description=desc,
                        event_start_iso=start,
                        memory_summary=memory.summarize_profile(user_id, chat_id),
                    )
                    await _send_text_or_file(update, cfg, brief, "meeting_brief.txt")
                    db.log(user_id, chat_id, "smart_meeting_brief", ok, title)
                    return
            ok, brief = await build_meeting_brief(
                event_title="Meeting",
                event_description=entities.get("event_hint", text),
                event_start_iso=None,
                memory_summary=memory.summarize_profile(user_id, chat_id),
            )
            await _send_text_or_file(update, cfg, brief, "meeting_brief.txt")
            db.log(user_id, chat_id, "smart_meeting_brief", ok, "manual")
            return

        if intent_name == "note_create":
            if cfg.use_google_notes:
                from src.tools.google_services import GoogleNotesService

                notes = GoogleNotesService(cfg.google_credentials_path)
                ok, msg = notes.create_note(text[:80], text)
            else:
                notes = NotesService(cfg.notes_dir)
                ok, msg = notes.create_note(text[:80], text)
            await update.message.reply_text(msg)
            db.log(user_id, chat_id, "smart_note", ok, text[:120])
            return

        if intent_name == "memory_set":
            payload = entities.get("memory_text", text).strip()
            key = f"user_note_{int(datetime.now().timestamp())}"
            stored = memory.remember_fact(
                user_id=user_id,
                chat_id=chat_id,
                category="user_notes",
                key=key,
                value=payload[:300],
                source="explicit_memory",
            )
            if stored:
                _append_facts_to_sheet(
                    cfg,
                    user_id,
                    chat_id,
                    [{"category": "user_notes", "key": key, "value": payload[:300]}],
                )
            await update.message.reply_text("Saved to memory.")
            db.log(user_id, chat_id, "smart_memory_set", True, payload[:120])
            return

        if intent_name == "memory_get":
            summary = memory.summarize_profile(user_id, chat_id, max_lines=12)
            reports = memory.list_recent_reports(limit=3)
            if reports:
                summary += "\n\nRecent autonomous research:"
                for item in reports:
                    summary += f"\n- {item.get('topic', '')}: {item.get('summary', '')[:120]}"
            await _send_text_or_file(update, cfg, summary, "memory_summary.txt")
            db.log(user_id, chat_id, "smart_memory_get", True, None)
            return

        if intent_name == "proactive_research_config":
            topics = entities.get("topics") or []
            if not topics:
                await update.message.reply_text("Specify topics after phrase like: 'следи за AI, fintech, horeca'.")
                return
            ctx.bot_data["proactive_topics"] = topics
            _save_proactive_topics(cfg.workdir, topics)
            memory.remember_fact(
                user_id=user_id,
                chat_id=chat_id,
                category="automation",
                key="proactive_topics",
                value=", ".join(topics),
                source="explicit_memory",
            )
            await update.message.reply_text(
                "Configured proactive topics:\n" + "\n".join(f"- {topic}" for topic in topics)
            )
            db.log(user_id, chat_id, "smart_proactive_topics", True, ",".join(topics)[:200])
            return

        if intent_name == "email_send":
            to_addr = entities.get("email") or _extract_email(text)
            if not to_addr:
                await update.message.reply_text("Email not found in message.")
                return
            query, tokens = _normalize_find_query(entities.get("filename", text))
            ok, msg = await _send_file_to_email(update, cfg, query, tokens, to_addr, text[:600])
            await update.message.reply_text(msg)
            db.log(user_id, chat_id, "smart_email_send", ok, to_addr)
            return

        if intent_name == "file_to_chat" or _looks_like_send_to_chat(text):
            query, tokens = _normalize_find_query(entities.get("filename", text))
            ok = await _send_file_to_chat(update, query, tokens, cfg)
            db.log(user_id, chat_id, "smart_send_file_chat", ok, query)
            return

        if intent_name == "click_ui" or _looks_like_click_instruction(text):
            target = entities.get("target") or text
            before = make_screenshot(cfg.workdir / "screens")
            await update.message.reply_document(before.open("rb"), filename=before.name)
            ok, msg = click_on_screen_target(before, target)
            await update.message.reply_text(msg)
            after = make_screenshot(cfg.workdir / "screens")
            await update.message.reply_document(after.open("rb"), filename=after.name)
            db.log(user_id, chat_id, "smart_click_ui", ok, target[:120])
            return

        starts_find = lowered.startswith(tuple(RU_FIND_VERBS))
        if intent_name == "find" or starts_find:
            query, tokens = _normalize_find_query(entities.get("filename", text))
            if _is_photo_query(text):
                results = _search_by_variants(find_photos, query, tokens)
                await _send_text_or_file(update, cfg, _render_paths("Photo search", results), "photos.txt")
            elif _is_document_query(text):
                results = _search_by_variants(find_documents, query, tokens)
                await _send_text_or_file(update, cfg, _render_paths("Document search", results), "documents.txt")
            else:
                results = _search_by_variants(find_files, query, tokens)
                await _send_text_or_file(update, cfg, _render_paths("File search", results), "find_results.txt")
            db.log(user_id, chat_id, "smart_find", True, query)
            return

        if intent_name == "research":
            depth = "deep" if any(x in lowered for x in ["глуб", "детал", "deep"]) else "medium"
            ok, answer = await research_topic(entities.get("topic", text), depth=depth, include_web=True)
            await _send_text_or_file(update, cfg, answer, "research.txt")
            db.log(user_id, chat_id, "smart_research", ok, text[:120])
            return

        if test_ollama_available():
            prompt = f"{memory.get_context_summary(user_id, chat_id)}\n\nUser: {text}"
            ok, answer = await ask_ollama(prompt)
            await _send_text_or_file(update, cfg, answer, "answer.txt")
            memory.add_message(user_id, chat_id, "bot", answer[:500])
            db.log(user_id, chat_id, "smart_fallback", ok, text[:120])
            return

        await update.message.reply_text("Unknown task. Try: find/open app/calendar/email/research/memory.")
        db.log(user_id, chat_id, "smart_unknown", False, text[:120])
    except Exception as exc:
        await update.message.reply_text(f"Error: {exc}")
        db.log(user_id, chat_id, "smart_error", False, str(exc))

