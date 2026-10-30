from __future__ import annotations

import asyncio
import re
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from lika_bot.config.settings import Settings
from lika_bot.models.entities import StyleProfile

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+")
_URL_RE = re.compile(r"(https?://|t\.me/|@\w+)")
_DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")
_CASUAL_MARKERS = {
    "ваще",
    "скок",
    "щас",
    "ща",
    "бля",
    "ахах",
    "жоско",
    "жоский",
    "жоские",
    "ладно",
    "прям",
    "типа",
    "короче",
    "походу",
    "вроде",
    "чета",
    "че",
    "чё",
}
_AFFECTIVE_MARKERS = ("люб", "скуч", "неж", "дорог", "красив", "кошк")
_STOPWORDS = {
    "это",
    "как",
    "что",
    "когда",
    "только",
    "тебя",
    "тебе",
    "твой",
    "твоя",
    "твои",
    "твоё",
    "меня",
    "мне",
    "если",
    "она",
    "они",
    "или",
    "тут",
    "там",
    "про",
    "просто",
    "очень",
    "сегодня",
    "этот",
    "потом",
    "потому",
    "который",
    "которая",
    "которые",
    "чтобы",
    "тоже",
    "тогда",
    "здесь",
    "ещё",
    "еще",
    "уже",
    "для",
    "его",
    "её",
    "них",
    "моя",
    "мой",
    "мои",
    "есть",
    "было",
    "быть",
    "тобой",
    "блин",
}


@dataclass(slots=True, frozen=True)
class _ExportMessage:
    author_name: str
    text: str


class StyleProfileService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cached_profile: StyleProfile | None = None

    async def get_profile(self, force_refresh: bool = False) -> StyleProfile:
        if self._cached_profile is not None and not force_refresh:
            return self._cached_profile

        source_path = self._settings.style_export_path
        if source_path is None:
            raise FileNotFoundError("STYLE_EXPORT_PATH is not configured.")
        if not source_path.exists():
            raise FileNotFoundError(f"Style export file not found: {source_path}")

        profile = await asyncio.to_thread(self._build_profile, source_path)
        self._cached_profile = profile
        return profile

    def is_configured(self) -> bool:
        source_path = self._settings.style_export_path
        return source_path is not None and source_path.exists()

    def _build_profile(self, source_path: Path) -> StyleProfile:
        chat_title = ""
        messages: list[_ExportMessage] = []

        with zipfile.ZipFile(source_path) as archive:
            html_entries = sorted(
                (entry.filename for entry in archive.infolist() if _is_messages_page(entry.filename)),
                key=_messages_page_sort_key,
            )
            if not html_entries:
                raise ValueError("Telegram export does not contain messages*.html pages.")

            for entry_name in html_entries:
                with archive.open(entry_name) as handle:
                    html = handle.read().decode("utf-8", errors="replace")
                page_title, page_messages = _parse_messages_page(html)
                if page_title and not chat_title:
                    chat_title = page_title
                messages.extend(page_messages)

        if not messages:
            raise ValueError("No text messages were found in the Telegram export.")

        counts = Counter(message.author_name for message in messages)
        author_name = _resolve_author_name(
            counts=counts,
            chat_title=chat_title,
            preferred_author=self._settings.style_source_author,
        )
        author_messages = [message.text for message in messages if message.author_name == author_name]
        if not author_messages:
            raise ValueError(f"No messages found for selected author: {author_name}")

        common_words = _extract_common_words(author_messages)
        emoji_signatures = _extract_emoji_signatures(author_messages)
        filler_words = _extract_filler_words(author_messages)
        sample_messages = _select_sample_messages(
            author_messages,
            target_name=self._settings.style_target_name or chat_title,
        )
        avg_message_length = int(sum(len(message) for message in author_messages) / max(len(author_messages), 1))
        target_name = self._settings.style_target_name or (chat_title if chat_title != author_name else None)
        addressing_examples = _extract_addressing_examples(author_messages, target_name=target_name or chat_title)

        return StyleProfile(
            source_path=str(source_path),
            chat_title=chat_title,
            author_name=author_name,
            target_name=target_name,
            total_messages=len(messages),
            total_text_messages=len(author_messages),
            avg_message_length=avg_message_length,
            lowercase_opening_ratio=_extract_lowercase_opening_ratio(author_messages),
            question_ratio=_extract_question_ratio(author_messages),
            exclamation_ratio=_extract_exclamation_ratio(author_messages),
            filler_words=filler_words,
            addressing_examples=addressing_examples,
            common_words=common_words,
            emoji_signatures=emoji_signatures,
            sample_messages=sample_messages,
            author_messages=author_messages,
        )


def _is_messages_page(filename: str) -> bool:
    return bool(re.search(r"/messages(\d+)?\.html$", filename))


def _messages_page_sort_key(filename: str) -> tuple[int, int]:
    match = re.search(r"messages(\d+)?\.html$", filename)
    if match is None:
        return (999999, 999999)
    page_number = int(match.group(1) or "1")
    return (page_number, len(filename))


def _parse_messages_page(html: str) -> tuple[str, list[_ExportMessage]]:
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one(".page_header .text.bold")
    chat_title = _normalize_space(title_node.get_text(" ", strip=True)) if title_node is not None else ""

    parsed_messages: list[_ExportMessage] = []
    current_author: str | None = None

    for node in soup.select("div.message.default"):
        classes = set(node.get("class", []))
        if "service" in classes:
            continue

        body = _direct_child(node, "div", "body")
        if body is None:
            continue

        author_node = _direct_child(body, "div", "from_name")
        if author_node is not None:
            candidate_author = _normalize_space(author_node.get_text(" ", strip=True))
            if candidate_author:
                current_author = candidate_author

        if not current_author:
            continue

        text_node = _direct_child(body, "div", "text")
        if text_node is None:
            continue

        text = _normalize_message_text(text_node.get_text("\n", strip=True))
        if not text:
            continue
        parsed_messages.append(_ExportMessage(author_name=current_author, text=text))

    return chat_title, parsed_messages


def _direct_child(node: Tag, tag_name: str, class_name: str) -> Tag | None:
    for child in node.children:
        if not isinstance(child, Tag):
            continue
        if child.name == tag_name and class_name in child.get("class", []):
            return child
    return None


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _normalize_message_text(value: str) -> str:
    lines = [line.strip() for line in value.splitlines()]
    compact = "\n".join(line for line in lines if line)
    return compact.strip()


def _resolve_author_name(
    counts: Counter[str],
    chat_title: str,
    preferred_author: str | None,
) -> str:
    if preferred_author:
        for author_name in counts:
            if author_name.casefold() == preferred_author.casefold():
                return author_name
        raise ValueError(f"STYLE_SOURCE_AUTHOR '{preferred_author}' was not found in the export.")

    candidates = [
        name
        for name, _count in counts.most_common()
        if name != chat_title and not _DATE_RE.search(name)
    ]
    if not candidates:
        candidates = [name for name, _count in counts.most_common() if not _DATE_RE.search(name)]
    if not candidates:
        raise ValueError("Could not determine the source author from the Telegram export.")
    return candidates[0]


def _extract_common_words(messages: list[str], limit: int = 12) -> list[str]:
    counter: Counter[str] = Counter()
    for message in messages:
        for token in _WORD_RE.findall(message.lower()):
            if len(token) < 3 or token in _STOPWORDS:
                continue
            counter[token] += 1
    return [word for word, _count in counter.most_common(limit)]


def _extract_emoji_signatures(messages: list[str], limit: int = 6) -> list[str]:
    counter: Counter[str] = Counter()
    for message in messages:
        for char in message:
            if char.isspace():
                continue
            category = unicodedata.category(char)
            if category == "So":
                counter[char] += 1
    return [emoji for emoji, _count in counter.most_common(limit)]


def _extract_filler_words(messages: list[str], limit: int = 8) -> list[str]:
    counter: Counter[str] = Counter()
    for message in messages:
        for token in _WORD_RE.findall(message.lower()):
            if token in _CASUAL_MARKERS:
                counter[token] += 1
    return [word for word, _count in counter.most_common(limit)]


def _extract_addressing_examples(messages: list[str], target_name: str | None, limit: int = 10) -> list[str]:
    target_name_cf = target_name.casefold() if target_name else ""
    unique_messages = list(dict.fromkeys(_normalize_space(message) for message in messages if 4 <= len(message) <= 180))
    scored: list[tuple[int, int, str]] = []
    for index, message in enumerate(unique_messages):
        message_cf = message.casefold()
        score = 0

        if target_name_cf and target_name_cf in message_cf:
            score += 4
        if any(keyword in message_cf for keyword in ("ты", "тебе", "тебя")):
            score += 3
        if any(keyword in message_cf for keyword in _AFFECTIVE_MARKERS):
            score += 2
        if 4 <= len(message) <= 90:
            score += 2
        elif 91 <= len(message) <= 140:
            score += 1
        if "?" in message or "!" in message:
            score += 1
        if _starts_with_lowercase(message):
            score += 1
        if score >= 4:
            scored.append((score, index, message))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [message for _score, _index, message in scored[:limit]]


def _extract_lowercase_opening_ratio(messages: list[str]) -> float:
    leading_chars = [_leading_alpha_char(message) for message in messages]
    alpha_chars = [char for char in leading_chars if char is not None]
    if not alpha_chars:
        return 0.0
    return sum(char.islower() for char in alpha_chars) / len(alpha_chars)


def _extract_question_ratio(messages: list[str]) -> float:
    if not messages:
        return 0.0
    return sum("?" in message for message in messages) / len(messages)


def _extract_exclamation_ratio(messages: list[str]) -> float:
    if not messages:
        return 0.0
    return sum("!" in message for message in messages) / len(messages)


def _select_sample_messages(messages: list[str], target_name: str | None, limit: int = 60) -> list[str]:
    unique_messages = list(
        dict.fromkeys(_normalize_space(message) for message in messages if 3 <= len(message) <= 280)
    )
    if len(unique_messages) <= limit:
        return unique_messages

    target_name_cf = target_name.casefold() if target_name else ""
    scored: list[tuple[int, int, str]] = []
    for index, message in enumerate(unique_messages):
        score = _message_score(message, target_name_cf)
        scored.append((score, index, message))

    scored.sort(key=lambda item: (-item[0], item[1]))
    shortlisted = sorted(scored[: max(limit * 2, limit)], key=lambda item: item[1])
    step = len(shortlisted) / limit
    selected = [shortlisted[min(int(i * step), len(shortlisted) - 1)][2] for i in range(limit)]
    return list(dict.fromkeys(selected))


def _message_score(message: str, target_name_cf: str) -> int:
    message_cf = message.casefold()
    score = 0
    length = len(message)

    if 4 <= length <= 90:
        score += 5
    elif 91 <= length <= 160:
        score += 3
    elif 161 <= length <= 280:
        score += 1

    if any(keyword in message_cf for keyword in ("ты", "тебя", "тебе", "люб", "скуч", "неж", "кошк", "дорог")):
        score += 3
    if target_name_cf and target_name_cf in message_cf:
        score += 3
    if "?" in message:
        score += 2
    if any(char in message for char in "!…") or "\n" in message:
        score += 1
    if _starts_with_lowercase(message):
        score += 1
    if any(unicodedata.category(char) == "So" for char in message):
        score += 1
    if _URL_RE.search(message):
        score -= 3
    if message.isupper():
        score -= 2

    return score


def _leading_alpha_char(message: str) -> str | None:
    for char in message:
        if char.isalpha():
            return char
    return None


def _starts_with_lowercase(message: str) -> bool:
    leading_char = _leading_alpha_char(message)
    return leading_char is not None and leading_char.islower()
