from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message

from lika_bot.app import AppContext
from lika_bot.keyboards.inline import build_categories_menu, build_main_menu, build_mood_menu
from lika_bot.utils.files import is_voice_file

logger = logging.getLogger(__name__)


def create_user_router(context: AppContext) -> Router:
    router = Router(name="user")

    async def ensure_authorized_message(message: Message) -> bool:
        if message.from_user is None:
            return False
        if context.services.access.can_use_gift(message.from_user.id):
            return True
        await message.answer(context.services.story.privacy_message())
        return False

    async def ensure_authorized_callback(callback: CallbackQuery) -> bool:
        if callback.from_user is None:
            return False
        if context.services.access.can_use_gift(callback.from_user.id):
            return True
        if isinstance(callback.message, Message):
            await callback.message.answer(context.services.story.privacy_message())
        await callback.answer()
        return False

    async def ensure_user(message: Message | CallbackQuery) -> int:
        telegram_user = message.from_user
        if telegram_user is None:
            raise RuntimeError("Telegram user is missing.")

        chat_id = telegram_user.id
        if isinstance(message, Message):
            chat_id = message.chat.id
        elif isinstance(message.message, Message):
            chat_id = message.message.chat.id

        user_record = await context.repositories.users.upsert_from_telegram(
            telegram_user,
            chat_id=chat_id,
            is_primary=telegram_user.id == context.settings.lika_chat_id,
        )
        await context.repositories.progress.ensure_row(user_record.id)
        await context.repositories.users.touch_last_interaction(user_record.id)
        return user_record.id

    async def safe_edit_text(target_message: Message, text: str, reply_markup: object | None) -> None:
        try:
            await target_message.edit_text(text, reply_markup=reply_markup)
        except TelegramBadRequest as error:
            if "message is not modified" in str(error).lower():
                return
            logger.warning("Failed to edit message: %s", error)
            await target_message.answer(text, reply_markup=reply_markup)

    async def show_main_menu(target_message: Message, user_id: int, edit: bool) -> None:
        snapshot = await context.services.progress.get_snapshot(user_id)
        unlock_state = context.services.progress.get_unlock_state(snapshot)
        text = context.services.story.build_menu_text(snapshot, unlock_state)
        markup = build_main_menu(unlock_state)

        if edit:
            await safe_edit_text(target_message, text, markup)
            return

        await target_message.answer(text, reply_markup=markup)

    async def send_video_selection(
        target_message: Message,
        user_id: int,
        selection_source: str,
        requested_category: str | None = None,
    ) -> None:
        if selection_source == "random":
            selection = await context.services.videos.select_random_video(user_id)
        elif selection_source == "special":
            selection = await context.services.videos.select_special_video(user_id)
        elif selection_source == "final":
            selection = await context.services.videos.select_final_video(user_id)
        else:
            if requested_category is None:
                raise ValueError("Category is required for category video selection.")
            selection = await context.services.videos.select_category_video(user_id, requested_category)

        if selection.status == "empty":
            if selection_source == "random":
                await target_message.answer(context.services.story.empty_random_text())
            elif selection_source == "special":
                await target_message.answer(context.services.story.special_empty_text())
            elif selection_source == "final":
                await target_message.answer(
                    "Даже без отдельного видео финал уже здесь. Его главный смысл всё равно остался в словах. 🌙"
                )
            else:
                title = context.services.story.category_title(requested_category or "")
                await target_message.answer(context.services.story.empty_category_text(title))
            return

        if selection.status == "exhausted":
            if selection_source == "random":
                await target_message.answer(context.services.story.exhausted_random_text())
            elif selection_source == "special":
                await target_message.answer(context.services.story.special_empty_text())
            elif selection_source == "final":
                await target_message.answer(
                    "Финальная часть уже раскрылась для тебя. Даже без повторного видео она остаётся здесь. 🌙"
                )
            else:
                title = context.services.story.category_title(requested_category or "")
                await target_message.answer(context.services.story.exhausted_category_text(title))
            return

        if selection.video is None:
            await target_message.answer("Кажется, этот сюрприз сейчас не нашёлся. Но всё остальное на месте. 🤍")
            return

        video_path = context.services.videos.absolute_path(selection.video.relative_path)
        if not video_path.exists():
            logger.warning("Video file is missing on disk: %s", video_path)
            await target_message.answer("Этот сюрприз сейчас не смог найтись на диске. Но можно открыть другой. ✨")
            return

        try:
            media_file = FSInputFile(video_path)
            caption = context.services.story.build_video_caption(selection.video.category)
            if is_voice_file(video_path):
                await target_message.answer_voice(media_file, caption=caption)
            else:
                await target_message.answer_video(media_file, caption=caption)
        except Exception:
            logger.exception("Failed to send video %s", video_path)
            await target_message.answer(
                "Этот сюрприз почему-то не открылся с первого раза. Можно попробовать ещё раз чуть позже."
            )
            return

        source_label = selection_source if selection_source != "category" else f"category:{requested_category}"
        await context.repositories.videos.mark_sent(user_id, selection.video.id, source_label)

        snapshot = await context.services.progress.get_snapshot(user_id)
        unlock_state = context.services.progress.get_unlock_state(snapshot)
        await target_message.answer(
            context.services.story.after_video_text(
                remaining=selection.remaining_after_send,
                total=selection.total_in_scope,
                snapshot=snapshot,
                unlock_state=unlock_state,
            )
        )

    async def open_special(target_message: Message, user_id: int) -> None:
        snapshot = await context.services.progress.get_snapshot(user_id)
        unlock_state = context.services.progress.get_unlock_state(snapshot)
        if not unlock_state.special_unlocked:
            await target_message.answer(context.services.story.special_locked_text(unlock_state))
            return

        state = await context.repositories.progress.get_state(user_id)
        first_open = not bool(state["special_opened_at"])
        await target_message.answer(context.services.story.special_opened_text(first_open))
        if first_open:
            await context.repositories.progress.mark_special_opened(user_id)

        await send_video_selection(target_message, user_id, selection_source="special")

    async def open_final(target_message: Message, user_id: int) -> None:
        snapshot = await context.services.progress.get_snapshot(user_id)
        unlock_state = context.services.progress.get_unlock_state(snapshot)
        if not unlock_state.final_unlocked:
            await target_message.answer(context.services.story.final_locked_text(unlock_state))
            return

        state = await context.repositories.progress.get_state(user_id)
        first_open = not bool(state["final_opened_at"])
        await target_message.answer(context.services.story.final_opened_text(first_open))
        if first_open:
            await context.repositories.progress.mark_final_opened(user_id)

        await send_video_selection(target_message, user_id, selection_source="final")

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        if not await ensure_authorized_message(message):
            return

        user_id = await ensure_user(message)
        user_record = await context.repositories.users.get_by_id(user_id)
        is_first_time = bool(user_record and not user_record.intro_completed)

        if is_first_time:
            await message.answer(context.services.story.main_greeting())
            await message.answer(context.services.story.first_time_scenario())
            await context.repositories.progress.mark_intro_seen(user_id)
            await context.repositories.users.mark_intro_completed(user_id)
        else:
            await message.answer(context.services.story.returning_greeting())

        await show_main_menu(message, user_id, edit=False)

    @router.callback_query(F.data == "nav:menu")
    async def back_to_menu(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        user_id = await ensure_user(callback)
        await callback.answer()
        if isinstance(callback.message, Message):
            await show_main_menu(callback.message, user_id, edit=True)

    @router.callback_query(F.data == "menu:random")
    async def random_video_handler(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        user_id = await ensure_user(callback)
        await callback.answer()
        if isinstance(callback.message, Message):
            await send_video_selection(callback.message, user_id, selection_source="random")
            await show_main_menu(callback.message, user_id, edit=True)

    @router.callback_query(F.data == "menu:categories")
    async def categories_handler(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        user_id = await ensure_user(callback)
        await callback.answer()
        if isinstance(callback.message, Message):
            categories = await context.services.videos.list_video_categories(user_id)
            await safe_edit_text(
                callback.message,
                context.services.story.category_menu_text(),
                build_categories_menu(categories),
            )

    @router.callback_query(F.data == "menu:moods")
    async def moods_handler(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        user_id = await ensure_user(callback)
        await callback.answer()
        if isinstance(callback.message, Message):
            await safe_edit_text(
                callback.message,
                context.services.story.mood_menu_text(),
                build_mood_menu(),
            )
            await context.repositories.users.touch_last_interaction(user_id)

    @router.callback_query(F.data.startswith("mood:"))
    async def mood_delivery_handler(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        user_id = await ensure_user(callback)
        await callback.answer()
        if isinstance(callback.message, Message):
            mood_key = callback.data.split(":", maxsplit=1)[1]
            await callback.message.answer(context.services.story.render_mood_delivery(mood_key))
            await show_main_menu(callback.message, user_id, edit=True)

    @router.callback_query(F.data.startswith("category:"))
    async def category_video_handler(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        user_id = await ensure_user(callback)
        await callback.answer()
        if isinstance(callback.message, Message):
            category = callback.data.split(":", maxsplit=1)[1]
            await send_video_selection(
                callback.message,
                user_id,
                selection_source="category",
                requested_category=category,
            )
            await show_main_menu(callback.message, user_id, edit=True)

    @router.callback_query(F.data == "menu:personal")
    async def personal_message_handler(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        user_id = await ensure_user(callback)
        delivery = await context.services.story.get_next_personal_message(user_id)
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.answer(context.services.story.render_personal_delivery(delivery))
            await show_main_menu(callback.message, user_id, edit=True)

    @router.callback_query(F.data == "menu:ai_message")
    async def ai_message_handler(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        await ensure_user(callback)
        await callback.answer("Собираю что-то живое...")
        if isinstance(callback.message, Message):
            status_message = await callback.message.answer("Сейчас попробую сказать это по-человечески...")
            try:
                generated_text = await context.services.ai_writer.generate_live_message()
            except Exception:
                logger.exception("Failed to generate a live AI message for the user.")
                await status_message.edit_text(
                    "Не получилось собрать новое живое сообщение с первого раза.\n"
                    "Нажми кнопку ещё раз чуть позже."
                )
                return

            await status_message.edit_text(
                "<b>Ещё одно от меня</b>\n\n"
                f"{html.escape(generated_text)}"
            )

    @router.callback_query(F.data == "menu:progress")
    async def progress_handler(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        user_id = await ensure_user(callback)
        await callback.answer()
        if isinstance(callback.message, Message):
            snapshot = await context.services.progress.get_snapshot(user_id)
            unlock_state = context.services.progress.get_unlock_state(snapshot)
            await safe_edit_text(
                callback.message,
                context.services.story.build_progress_text(snapshot, unlock_state),
                build_main_menu(unlock_state),
            )

    @router.callback_query(F.data == "menu:special")
    async def special_handler(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        user_id = await ensure_user(callback)
        await callback.answer()
        if isinstance(callback.message, Message):
            await open_special(callback.message, user_id)
            await show_main_menu(callback.message, user_id, edit=True)

    @router.callback_query(F.data == "menu:final")
    async def final_handler(callback: CallbackQuery) -> None:
        if not await ensure_authorized_callback(callback):
            return
        user_id = await ensure_user(callback)
        await callback.answer()
        if isinstance(callback.message, Message):
            await open_final(callback.message, user_id)
            await show_main_menu(callback.message, user_id, edit=True)

    @router.message()
    async def fallback_handler(message: Message) -> None:
        if not await ensure_authorized_message(message):
            return
        user_id = await ensure_user(message)
        await message.answer(context.services.story.fallback_message())
        await show_main_menu(message, user_id, edit=False)

    return router
