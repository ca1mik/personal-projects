from __future__ import annotations

from collections import defaultdict

from lika_bot.config.settings import Settings
from lika_bot.models.entities import PersonalDelivery, ProgressSnapshot, StoryMoment, UnlockState
from lika_bot.repositories.progress import ProgressRepository
from lika_bot.texts.content import (
    CATEGORY_EMPTY_TEXT_TEMPLATE,
    CATEGORY_EXHAUSTED_TEXT_TEMPLATE,
    CATEGORY_MENU_TEXT,
    FALLBACK_MESSAGE,
    FINAL_OPENING_TEXT,
    FINAL_RETURNING_TEXT,
    FIRST_TIME_SCENARIO,
    MAIN_GREETING,
    MENU_TAGLINE,
    MOOD_MENU_TEXT,
    MOOD_MESSAGES,
    MOOD_TITLES,
    NEW_VIDEOS_NOTIFICATION_TEMPLATE,
    PERSONAL_MESSAGES,
    PRIVACY_TEXT,
    RANDOM_EMPTY_TEXT,
    RANDOM_EXHAUSTED_TEXT,
    RETURNING_GREETING,
    SPECIAL_EMPTY_TEXT,
    SPECIAL_OPENING_TEXT,
    SPECIAL_RETURNING_TEXT,
    STORY_MOMENTS,
    VIDEO_AFTERGLOW_TEMPLATE,
    pretty_category_title,
)


class StoryService:
    """Text composition and personal-message sequencing."""

    def __init__(self, settings: Settings, progress_repository: ProgressRepository) -> None:
        self._settings = settings
        self._progress_repository = progress_repository
        self._personal_messages = PERSONAL_MESSAGES
        self._story_moments = STORY_MOMENTS
        self._mood_messages = MOOD_MESSAGES
        self._mood_offsets: dict[str, int] = defaultdict(int)

    @property
    def story_moments(self) -> list[StoryMoment]:
        return self._story_moments

    def get_story_moment(self, key: str) -> StoryMoment:
        for moment in self._story_moments:
            if moment.key == key:
                return moment
        raise KeyError(f"Unknown story moment: {key}")

    def main_greeting(self) -> str:
        return MAIN_GREETING

    def first_time_scenario(self) -> str:
        return FIRST_TIME_SCENARIO

    def returning_greeting(self) -> str:
        return RETURNING_GREETING

    def category_title(self, category: str) -> str:
        return pretty_category_title(category)

    def category_menu_text(self) -> str:
        return CATEGORY_MENU_TEXT

    def mood_menu_text(self) -> str:
        return MOOD_MENU_TEXT

    def fallback_message(self) -> str:
        return FALLBACK_MESSAGE

    def privacy_message(self) -> str:
        return PRIVACY_TEXT

    def new_videos_notification(self, count: int) -> str:
        _ = count
        return NEW_VIDEOS_NOTIFICATION_TEMPLATE

    def build_menu_text(self, snapshot: ProgressSnapshot, unlock_state: UnlockState) -> str:
        lines = [
            "<b>19 мгновений для Лики</b>",
            "",
            f"Уже открыто <b>{snapshot.total_opened}</b> из <b>{self._settings.total_surprises}</b>.",
            f"Видео-сюрпризов увидено: <b>{snapshot.videos_watched}</b>",
            f"Личных тёплых слов открыто: <b>{snapshot.personal_messages_opened}</b>",
            f"Ещё ждут тебя: <b>{snapshot.remaining_surprises}</b>",
        ]

        if snapshot.scheduled_messages_sent:
            lines.append(
                f"За день тебе уже прилетело нежных напоминаний: <b>{snapshot.scheduled_messages_sent}</b>"
            )

        lines.extend(["", self._soft_hint(snapshot, unlock_state)])
        return "\n".join(lines)

    def build_progress_text(self, snapshot: ProgressSnapshot, unlock_state: UnlockState) -> str:
        lines = [
            "<b>Как сегодня раскрывается день</b>",
            "",
            f"Открыто сюрпризов: <b>{snapshot.total_opened}</b> из <b>{self._settings.total_surprises}</b>",
            f"Видео просмотрено: <b>{snapshot.videos_watched}</b>",
            f"Личных посланий открыто: <b>{snapshot.personal_messages_opened}</b>",
            f"Ещё ждут тебя: <b>{snapshot.remaining_surprises}</b>",
        ]

        if snapshot.scheduled_messages_sent:
            lines.append(
                f"И ещё в течение дня тебе уже пришло тёплых напоминаний: <b>{snapshot.scheduled_messages_sent}</b>"
            )

        if unlock_state.special_unlocked and not snapshot.special_opened:
            lines.extend(["", "Особенный сюрприз уже открылся для тебя. Он ждёт спокойно, без спешки. ✨"])
        elif unlock_state.special_videos_left > 0:
            lines.extend(
                [
                    "",
                    f"До особенного сюрприза осталось ещё <b>{unlock_state.special_videos_left}</b> видео.",
                ]
            )

        if unlock_state.final_unlocked and not snapshot.final_opened:
            lines.append("Финал дня уже рядом. Открой его тогда, когда захочется красиво поставить точку. 🌙")

        return "\n".join(lines)

    def build_video_caption(self, category: str) -> str:
        return f"Небольшой тёплый сюрприз из раздела «{self.category_title(category)}». 🎞"

    def after_video_text(
        self,
        remaining: int,
        total: int,
        snapshot: ProgressSnapshot,
        unlock_state: UnlockState,
    ) -> str:
        lines = [VIDEO_AFTERGLOW_TEMPLATE.format(remaining=remaining, total=total)]

        if remaining == 0:
            lines.append("Этот кусочек дня уже раскрылся целиком. Но в меню тебя всё ещё ждёт что-то ещё. 💞")

        if unlock_state.special_unlocked and not snapshot.special_opened:
            lines.append("И да... для тебя уже открылся особенный сюрприз. Он теперь в главном меню. ✨")
        elif unlock_state.special_videos_left == 1:
            lines.append("Ещё одно видео - и для тебя откроется кое-что совсем личное.")
        elif unlock_state.final_unlocked and not snapshot.final_opened:
            lines.append("А когда почувствуешь, что пора, в меню уже ждёт финал этого дня. 🌙")

        return "\n\n".join(lines)

    def empty_random_text(self) -> str:
        return RANDOM_EMPTY_TEXT

    def exhausted_random_text(self) -> str:
        return RANDOM_EXHAUSTED_TEXT

    def empty_category_text(self, title: str) -> str:
        return CATEGORY_EMPTY_TEXT_TEMPLATE.format(title=title)

    def exhausted_category_text(self, title: str) -> str:
        return CATEGORY_EXHAUSTED_TEXT_TEMPLATE.format(title=title)

    def special_locked_text(self, unlock_state: UnlockState) -> str:
        if not unlock_state.birthday_started:
            return "Этому сюрпризу ещё чуть-чуть рано. Он должен проснуться вместе с самим днём рождения. ✨"
        if unlock_state.special_videos_left > 0:
            return (
                "Этот кусочек дня уже близко.\n"
                f"Осталось открыть ещё <b>{unlock_state.special_videos_left}</b> видео, и он станет доступен."
            )
        return "Он уже совсем рядом."

    def special_opened_text(self, first_open: bool) -> str:
        return SPECIAL_OPENING_TEXT if first_open else SPECIAL_RETURNING_TEXT

    def special_empty_text(self) -> str:
        return SPECIAL_EMPTY_TEXT

    def final_locked_text(self, unlock_state: UnlockState) -> str:
        if not unlock_state.birthday_started:
            return "Финал дня ещё не пришёл. Ему нужно дождаться самого праздника. 🌙"
        if unlock_state.final_videos_left > 0 and unlock_state.final_total_left > 0:
            return (
                "Финал дня ещё бережно ждёт своего времени.\n"
                f"Ему нужно либо ещё <b>{unlock_state.final_videos_left}</b> видео, "
                f"либо добраться до <b>{unlock_state.final_unlock_at_label}</b>."
            )
        if unlock_state.final_videos_left > 0:
            return (
                "Финал уже почти здесь.\n"
                f"Можно дождаться <b>{unlock_state.final_unlock_at_label}</b> "
                "или открыть ещё немного сюрпризов до него."
            )
        return (
            "Финал дня пока ещё держит паузу.\n"
            f"Если захочешь, возвращайся к нему ближе к <b>{unlock_state.final_unlock_at_label}</b>."
        )

    def final_opened_text(self, first_open: bool) -> str:
        return FINAL_OPENING_TEXT if first_open else FINAL_RETURNING_TEXT

    async def get_next_personal_message(self, user_id: int) -> PersonalDelivery:
        current_cycle = await self._progress_repository.get_current_personal_cycle(user_id)
        seen_keys = await self._progress_repository.get_seen_personal_message_keys(user_id, current_cycle)
        recycled = False

        if len(seen_keys) >= len(self._personal_messages):
            current_cycle += 1
            seen_keys = set()
            recycled = True

        next_key, next_text = next(item for item in self._personal_messages if item[0] not in seen_keys)
        await self._progress_repository.record_personal_message(user_id, next_key, current_cycle)
        return PersonalDelivery(
            message_key=next_key,
            text=next_text,
            recycled=recycled,
            cycle=current_cycle,
        )

    def render_personal_delivery(self, delivery: PersonalDelivery) -> str:
        if delivery.recycled:
            intro = (
                "Я начну этот круг заново.\n"
                "Некоторые тёплые слова хочется не просто открыть однажды, а возвращать тебе снова."
            )
        else:
            intro = "Только для тебя. 🤍"
        return f"{intro}\n\n{delivery.text}"

    def render_mood_delivery(self, mood_key: str) -> str:
        if mood_key not in self._mood_messages:
            raise KeyError(f"Unknown mood key: {mood_key}")
        variants = self._mood_messages[mood_key]
        offset = self._mood_offsets[mood_key] % len(variants)
        self._mood_offsets[mood_key] += 1
        return f"<b>{MOOD_TITLES[mood_key]}</b>\n\n{variants[offset]}"

    def _soft_hint(self, snapshot: ProgressSnapshot, unlock_state: UnlockState) -> str:
        if unlock_state.final_unlocked and not snapshot.final_opened:
            return "Финал дня уже ждёт тебя в меню. Открой его тогда, когда почувствуешь: вот сейчас самое время. 🌙"
        if unlock_state.special_unlocked and not snapshot.special_opened:
            return "Для тебя уже открылся особенный сюрприз. Он лежит в меню тихо и очень по-личному. ✨"
        if unlock_state.special_videos_left == 1:
            return "Ещё одно видео - и для тебя откроется кое-что особенно личное."
        if unlock_state.special_videos_left > 1 and unlock_state.birthday_started:
            return (
                "Сегодня для тебя приготовлено ещё кое-что.\n"
                f"До особенного сюрприза осталось <b>{unlock_state.special_videos_left}</b> видео."
            )
        return MENU_TAGLINE
