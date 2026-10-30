from __future__ import annotations

import json
import re

import aiohttp
from aiohttp import ClientTimeout
from aiohttp_socks import ProxyConnector

from lika_bot.config.settings import Settings
from lika_bot.models.entities import GeneratedDraft, StyleProfile
from lika_bot.services.style_profile import StyleProfileService

_REQUEST_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
_URL_RE = re.compile(r"(https?://|t\.me/|@\w+)")
_VARIANT_LABEL_RE = re.compile(r"(?im)^вариант\s+\d+\s*:\s*")
_REQUEST_STOPWORDS = {
    "сделай",
    "сделать",
    "напиши",
    "пожалуйста",
    "вариант",
    "варианта",
    "варианты",
    "короткий",
    "коротких",
    "сообщение",
    "сообщения",
    "текст",
    "текста",
    "нужно",
    "надо",
    "пусть",
    "будет",
    "это",
    "этот",
    "чтобы",
    "как",
    "для",
    "его",
    "ее",
    "её",
    "их",
    "она",
    "он",
    "под",
}
_AFFECTIVE_MARKERS = ("люб", "дорог", "кошк", "неж", "красив", "родн", "мила")
_LOGISTICAL_MARKERS = (
    "во сколько",
    "когда",
    "куда",
    "где",
    "освобод",
    "работаешь",
    "помогу",
    "на связи",
    "как там",
    "ты как",
    "ты сможешь?",
)


class AIWriterService:
    def __init__(self, settings: Settings, style_profile_service: StyleProfileService) -> None:
        self._settings = settings
        self._style_profile_service = style_profile_service

    @property
    def style_profile_service(self) -> StyleProfileService:
        return self._style_profile_service

    async def generate_test_draft(self, request: str) -> GeneratedDraft:
        if not self._settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        profile = await self._style_profile_service.get_profile()
        examples = _select_relevant_examples(profile, request, limit=36)
        response_text = await self._request_openai(
            profile=profile,
            request=request,
            examples=examples,
            mode="test",
        )
        if _needs_birthday_retry(request, response_text, mode="test"):
            response_text = await self._request_openai(
                profile=profile,
                request=(
                    f"{request.strip()}\n\n"
                    "Обязательная правка: в каждом варианте коротко и прямо упомяни день рождения "
                    "или 'с др', но не превращай текст в открытку."
                ),
                examples=examples,
                mode="test",
            )
        if _request_mentions_birthday(request):
            response_text = _ensure_birthday_shape(
                response_text,
                target_name=profile.target_name,
                mode="test",
            )
        return GeneratedDraft(
            model=self._settings.openai_model,
            request=request,
            text=response_text,
            author_name=profile.author_name,
            sample_count=len(examples),
        )

    async def generate_live_message(self, request: str | None = None) -> str:
        if not self._settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        prompt_request = request.strip() if request and request.strip() else (
            "Напиши одно короткое тёплое, нежное и живое сообщение Лике на день рождения. "
            "Это должно быть похоже на реальное сообщение Льва из обычного чата."
        )
        profile = await self._style_profile_service.get_profile()
        examples = _select_relevant_examples(profile, prompt_request, limit=28)
        response_text = await self._request_openai(
            profile=profile,
            request=prompt_request,
            examples=examples,
            mode="live",
        )
        if _needs_birthday_retry(prompt_request, response_text, mode="live"):
            response_text = await self._request_openai(
                profile=profile,
                request=(
                    f"{prompt_request.strip()}\n\n"
                    "Обязательная правка: коротко и прямо упомяни день рождения или 'с др', "
                    "но без открыточного тона."
                ),
                examples=examples,
                mode="live",
            )
        cleaned_text = _clean_live_message(response_text)
        if _request_mentions_birthday(prompt_request):
            cleaned_text = _ensure_birthday_shape(
                cleaned_text,
                target_name=profile.target_name,
                mode="live",
            )
        return cleaned_text

    async def _request_openai(
        self,
        profile: StyleProfile,
        request: str,
        examples: list[str],
        mode: str,
    ) -> str:
        proxy = self._settings.openai_proxy or self._settings.bot_proxy
        connector = None
        request_kwargs: dict[str, str] = {}

        if proxy:
            if proxy.startswith(("socks4://", "socks5://")):
                connector = ProxyConnector.from_url(proxy)
            else:
                request_kwargs["proxy"] = proxy

        payload = {
            "model": self._settings.openai_model,
            "input": [
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._build_developer_prompt(profile, mode=mode),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._build_user_prompt(
                                profile,
                                request=request,
                                examples=examples,
                                mode=mode,
                            ),
                        }
                    ],
                },
            ],
            "text": {"verbosity": "low"},
            "max_output_tokens": 600 if mode == "test" else 220,
        }

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=ClientTimeout(total=90),
        ) as session:
            async with session.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self._settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                **request_kwargs,
            ) as response:
                raw_text = await response.text()
                if response.status >= 400:
                    message = _extract_error_message(raw_text)
                    raise RuntimeError(f"OpenAI request failed: {message}")

        data = json.loads(raw_text)
        output_text = _extract_output_text(data)
        if not output_text:
            raise RuntimeError("OpenAI returned an empty response.")
        return output_text.strip()

    def _build_developer_prompt(self, profile: StyleProfile, mode: str) -> str:
        emoji_hint = ", ".join(profile.emoji_signatures) if profile.emoji_signatures else "без обязательных эмодзи"
        common_words = ", ".join(profile.common_words[:10]) if profile.common_words else "живой разговорный русский"
        filler_words = ", ".join(profile.filler_words[:8]) if profile.filler_words else "без ярких разговорных слов-маркеров"
        addressing_examples = " | ".join(profile.addressing_examples[:4]) if profile.addressing_examples else "нет коротких адресных примеров"
        lowercase_ratio = round(profile.lowercase_opening_ratio * 100)
        question_ratio = round(profile.question_ratio * 100)
        exclamation_ratio = round(profile.exclamation_ratio * 100)

        format_rules = (
            "- Сделай ровно 3 варианта.\n"
            "- Каждый вариант: 1-3 короткие реплики или предложения, до 220 символов.\n"
            "- Не используй заголовки кроме 'Вариант 1:', 'Вариант 2:' и 'Вариант 3:'."
            if mode == "test"
            else "- Верни один готовый текст без заголовка: 1-4 короткие реплики или предложения, до 240 символов."
        )

        return (
            "Ты не пишешь красивое поздравление. Ты продолжаешь реальную переписку конкретного человека.\n"
            "Нужно звучать так, будто Лев сам это отправил Лике в обычном чате.\n"
            "Приоритеты по важности:\n"
            "1. Реальная лексика и ритм автора.\n"
            "2. Ощущение живого телеграм-сообщения.\n"
            "3. Выполнение запроса.\n"
            "4. Красота текста.\n"
            "Правила:\n"
            "- Пиши только по-русски.\n"
            "- Не придумывай новые факты, воспоминания или обещания.\n"
            "- Не пиши как открытка, тост, письмо, афоризм или стих.\n"
            "- Не используй пафос, липкие клише и универсальные пожелания из серии 'пусть всё будет хорошо', 'побольше поводов улыбаться', 'рядом будут хорошие люди'.\n"
            "- Не делай длинные перечни качеств через запятую.\n"
            "- Если повод праздничный, вплети его легко. Не переодевай автора в поздравительную открытку.\n"
            "- Если запрос про день рождения, хороший ритм такой: первая короткая строка с 'с др/с днём рождения' и обращением, вторая — очень короткая тёплая опора вроде 'я за тебя' или 'ты сможешь'.\n"
            "- В birthday-сообщениях не уходи в организационные вопросы и сервисную помощь. Лучше опора и близость, чем 'ты как?', 'если надо помогу' или 'я на связи'.\n"
            "- Не комментируй задачу и сам процесс написания. Нельзя упоминать черновик, вариант, тест, запрос, стиль, ИИ, открытку или то, что ты сейчас что-то переписываешь.\n"
            "- Сохраняй живой чатовый ритм: короткие реплики, вопросы, бытовые слова, неровность, строчные буквы — если это естественно для автора.\n"
            f"{format_rules}\n\n"
            f"Автор стиля: {profile.author_name}\n"
            f"Цель сообщения: {profile.target_name or profile.chat_title or 'близкий человек'}\n"
            f"Средняя длина сообщения автора: {profile.avg_message_length} символов.\n"
            f"Со строчной начинается примерно {lowercase_ratio}% сообщений автора.\n"
            f"Вопросы встречаются примерно в {question_ratio}% сообщений, восклицания — в {exclamation_ratio}%.\n"
            f"Разговорные слова автора: {filler_words}.\n"
            f"Характерные обращения и короткие живые фразы: {addressing_examples}.\n"
            f"Частые слова автора: {common_words}.\n"
            f"Эмодзи-подпись автора: {emoji_hint}."
        )

    def _build_user_prompt(
        self,
        profile: StyleProfile,
        request: str,
        examples: list[str],
        mode: str,
    ) -> str:
        example_block = "\n".join(f"- {message}" for message in examples)
        birthday_note = (
            "Повод — день рождения. В реальных примерах нет открыточного регистра, "
            "поэтому добавь повод мягко и коротко, без официального поздравительного тона. "
            "Но сам повод терять нельзя: должно быть прямое, короткое упоминание дня рождения или 'с др'. "
            "Рабочая схема: коротко отметить день рождения в первой реплике, а дальше сразу вернуться в обычную манеру автора. "
            "Ориентир по удачной форме от автора: 'с днём рождения, кошка' / 'я за тебя, ты сможешь'. Не копируй дословно, но держи этот размер, теплоту и опору. "
            "Избегай формата 'ты как?' и 'если надо помогу' — это уводит в бытовую переписку, а нужен тёплый короткий birthday-заход.\n\n"
            if _request_mentions_birthday(request)
            else ""
        )
        mode_note = (
            "Нужно вернуть 3 разных сообщения для выбора, но каждое из них должно выглядеть как настоящее уже отправленное сообщение. "
            "Внутри самих сообщений нельзя говорить о выборе, тесте, вариантах или черновиках.\n\n"
            if mode == "test"
            else "Нужен один текст, который можно сразу отправить. Никаких комментариев о задаче или стиле.\n\n"
        )
        return (
            f"Запрос автора:\n{request.strip()}\n\n"
            f"{birthday_note}"
            f"{mode_note}"
            f"Короткая сводка по стилю:\n"
            f"- средняя длина сообщения: около {profile.avg_message_length} символов;\n"
            f"- автор часто пишет коротко и разговорно;\n"
            f"- естественны вопросы, обрывки фраз, бытовые формулировки;\n"
            f"- слова-маркеры: {', '.join(profile.filler_words[:6]) if profile.filler_words else 'ярких маркеров мало'}.\n\n"
            f"Релевантные реальные сообщения автора из экспорта ({profile.total_text_messages} текстовых сообщений в базе, ниже только точечная выборка под запрос):\n"
            f"{example_block}\n\n"
            "Сделай результат так, чтобы он ощущался как настоящее продолжение этой переписки."
        )


def _extract_error_message(raw_text: str) -> str:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text.strip() or "unknown error"

    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return raw_text.strip() or "unknown error"


def _extract_output_text(data: dict[str, object]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    pieces: list[str] = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    pieces.append(text.strip())
    return "\n".join(pieces).strip()


def _clean_live_message(text: str) -> str:
    matches = list(_VARIANT_LABEL_RE.finditer(text))
    if matches:
        first_start = matches[0].end()
        first_end = matches[1].start() if len(matches) > 1 else len(text)
        return text[first_start:first_end].strip()
    return text.strip()


def _request_mentions_birthday(request: str) -> bool:
    request_cf = request.casefold()
    return any(token in request_cf for token in ("день рождения", "днём рождения", "с др", "др", "днюх"))


def _response_mentions_birthday(text: str) -> bool:
    text_cf = text.casefold()
    return any(token in text_cf for token in ("день рождения", "днём рождения", "с др", "др "))


def _needs_birthday_retry(request: str, response_text: str, mode: str) -> bool:
    if not _request_mentions_birthday(request):
        return False
    if mode == "live":
        return not _response_mentions_birthday(response_text)

    sections = _split_variant_sections(response_text)
    if not sections:
        return not _response_mentions_birthday(response_text)
    return any(not _response_mentions_birthday(section) for section in sections)


def _select_relevant_examples(profile: StyleProfile, request: str, limit: int) -> list[str]:
    unique_messages = list(
        dict.fromkeys(message.strip() for message in profile.author_messages if 3 <= len(message.strip()) <= 240)
    )
    request_tokens = _extract_request_tokens(request)
    request_cf = request.casefold()
    birthday_request = _request_mentions_birthday(request)
    target_name_cf = profile.target_name.casefold() if profile.target_name else ""
    scored: list[tuple[int, int, str]] = []

    for index, message in enumerate(unique_messages):
        message_cf = message.casefold()
        score = 0
        length = len(message)

        if 4 <= length <= 80:
            score += 5
        elif 81 <= length <= 140:
            score += 3
        elif 141 <= length <= 220:
            score += 1

        overlap = sum(1 for token in request_tokens if token in message_cf)
        score += overlap * 4

        if target_name_cf and target_name_cf in message_cf:
            score += 3
        if any(token in message_cf for token in ("ты", "тебе", "тебя")):
            score += 2
        if any(marker in message_cf for marker in ("люб", "скуч", "неж", "дорог", "красив", "кошк")):
            score += 2
        if any(marker in message_cf for marker in profile.filler_words[:8]):
            score += 2
        if _request_wants_warmth(request_cf) and any(
            marker in message_cf for marker in ("неж", "дорог", "красив", "кошк", "ты", "тебе", "тебя")
        ):
            score += 2
        if birthday_request:
            if any(marker in message_cf for marker in _AFFECTIVE_MARKERS):
                score += 4
            if any(marker in message_cf for marker in ("я за тебя", "ты сможешь", "люблю тебя", "я тебя")):
                score += 4
            if any(marker in message_cf for marker in _LOGISTICAL_MARKERS):
                score -= 4
        if "?" in message:
            score += 2
        if _starts_with_lowercase(message):
            score += 1
        if "\n" in message:
            score += 1
        if _URL_RE.search(message):
            score -= 3

        scored.append((score, index, message))

    scored.sort(key=lambda item: (-item[0], item[1]))

    selected: list[str] = []
    short_quota = max(1, (limit * 2) // 3)
    for _score, _index, message in scored:
        if len(selected) >= short_quota:
            break
        if len(message) <= 90:
            selected.append(message)

    for example in profile.addressing_examples:
        if len(selected) >= limit:
            break
        if example not in selected:
            selected.append(example)

    for _score, _index, message in scored:
        if len(selected) >= limit:
            break
        if message not in selected:
            selected.append(message)

    return selected[:limit]


def _extract_request_tokens(request: str) -> list[str]:
    tokens: list[str] = []
    for token in _REQUEST_TOKEN_RE.findall(request.casefold()):
        if len(token) < 2:
            continue
        if token in _REQUEST_STOPWORDS:
            continue
        tokens.append(token)
    return list(dict.fromkeys(tokens))


def _request_wants_warmth(request_cf: str) -> bool:
    return any(token in request_cf for token in ("неж", "тепл", "жив", "по-человечес", "лич", "мяг"))


def _starts_with_lowercase(message: str) -> bool:
    for char in message:
        if char.isalpha():
            return char.islower()
    return False


def _split_variant_sections(text: str) -> list[str]:
    matches = list(_VARIANT_LABEL_RE.finditer(text))
    if not matches:
        return []

    sections: list[str] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end].strip()
        if section:
            sections.append(section)
    return sections


def _ensure_birthday_shape(text: str, target_name: str | None, mode: str) -> str:
    if mode == "live":
        return _repair_birthday_section(text, target_name=target_name, variant_index=0)

    matches = list(_VARIANT_LABEL_RE.finditer(text))
    if not matches:
        return _repair_birthday_section(text, target_name=target_name, variant_index=0)

    rebuilt: list[str] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        label = match.group(0).strip()
        section = text[start:end].strip()
        rebuilt.append(f"{label}\n{_repair_birthday_section(section, target_name=target_name, variant_index=index)}")
    return "\n\n".join(rebuilt).strip()


def _repair_birthday_section(section: str, target_name: str | None, variant_index: int) -> str:
    if _response_mentions_birthday(section):
        return section.strip()

    opening = _birthday_opening(section, target_name=target_name, variant_index=variant_index)
    body = _birthday_body(section, target_name=target_name)
    return f"{opening}\n{body}".strip()


def _birthday_opening(section: str, target_name: str | None, variant_index: int) -> str:
    section_cf = section.casefold()
    if "кошка" in section_cf:
        return "с днём рождения, кошка"
    if target_name and variant_index % 2 == 0:
        return f"с днём рождения, {target_name}"
    if target_name:
        return f"с др, {target_name}"
    return "с днём рождения"


def _birthday_body(section: str, target_name: str | None) -> str:
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    cleaned_lines: list[str] = []
    for index, line in enumerate(lines):
        if _response_mentions_birthday(line):
            continue
        candidate = line
        if index == 0:
            candidate = _strip_leading_address(candidate, target_name)
        if candidate:
            cleaned_lines.append(candidate)

    if not cleaned_lines:
        return "я за тебя, ты сможешь"

    body = " ".join(cleaned_lines).strip()
    body_cf = body.casefold()

    if "ты сможешь" in body_cf and "я за тебя" not in body_cf and "я в тебя верю" not in body_cf:
        body = f"я за тебя, {body[:1].lower()}{body[1:]}" if body else "я за тебя, ты сможешь"
    elif body_cf in {"я за тебя", "я рядом"}:
        body = "я за тебя, ты сможешь"
    elif "помогу" in body_cf or "на связи" in body_cf or "ты как" in body_cf:
        body = "я за тебя, ты сможешь"

    return body


def _strip_leading_address(text: str, target_name: str | None) -> str:
    candidate = text.strip()
    if target_name:
        pattern = re.compile(rf"^\s*{re.escape(target_name)}\s*[-,.: ]*\s*", re.IGNORECASE)
        candidate = pattern.sub("", candidate, count=1).strip()

    if candidate.casefold().startswith("кошка"):
        candidate = re.sub(r"^\s*кошка\s*[-,.: ]*\s*", "", candidate, count=1, flags=re.IGNORECASE).strip()
    return candidate
