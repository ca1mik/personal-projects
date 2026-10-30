from __future__ import annotations

import html

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile, Message

from lika_bot.app import AppContext
from lika_bot.utils.files import is_voice_file


def create_admin_router(context: AppContext) -> Router:
    router = Router(name="admin")

    async def ensure_admin(message: Message) -> bool:
        if message.from_user is None:
            return False
        if context.services.access.is_admin(message.from_user.id):
            return True
        await message.answer("Эта дверь открывается только владельцу бота.")
        return False

    async def ensure_lika_user_id() -> int:
        user_record = await context.repositories.users.ensure_system_user(
            context.settings.lika_chat_id,
            first_name="Лика",
            is_primary=True,
        )
        await context.repositories.progress.ensure_row(user_record.id)
        return user_record.id

    @router.message(Command("sync"))
    async def sync_handler(message: Message) -> None:
        if not await ensure_admin(message):
            return
        summary = await context.services.content_sync.sync(
            notify_about_new=True,
            reason="manual_sync",
            bot=message.bot,
        )
        categories = ", ".join(summary.scanned_categories) if summary.scanned_categories else "пока ни одной"
        await message.answer(
            "<b>Синхронизация завершена.</b>\n\n"
            f"Новых видео: <b>{summary.new_videos}</b>\n"
            f"Возвращено в активные: <b>{summary.reactivated_videos}</b>\n"
            f"Скрыто как отсутствующие: <b>{summary.deactivated_videos}</b>\n"
            f"Активных видео сейчас: <b>{summary.active_videos}</b>\n"
            f"Категории: <b>{categories}</b>"
        )

    @router.message(Command("stats"))
    async def stats_handler(message: Message) -> None:
        if not await ensure_admin(message):
            return

        lika_user_id = await ensure_lika_user_id()
        snapshot = await context.services.progress.get_snapshot(lika_user_id)
        active_videos = await context.repositories.videos.count_active()
        users_count = await context.repositories.users.count_users()
        categories = await context.services.videos.list_video_categories(lika_user_id)
        jobs_count = context.scheduler.job_count if context.scheduler is not None else 0

        await message.answer(
            "<b>Статистика бота</b>\n\n"
            f"Пользователей в базе: <b>{users_count}</b>\n"
            f"Активных видео: <b>{active_videos}</b>\n"
            f"Категорий с видео: <b>{len(categories)}</b>\n"
            f"Открыто сюрпризов у Лики: <b>{snapshot.total_opened}</b>\n"
            f"Видео просмотрено: <b>{snapshot.videos_watched}</b>\n"
            f"Личных сообщений открыто: <b>{snapshot.personal_messages_opened}</b>\n"
            f"Отправлено сообщений по расписанию: <b>{snapshot.scheduled_messages_sent}</b>\n"
            f"Активных задач планировщика: <b>{jobs_count}</b>"
        )

    @router.message(Command("broadcast_test"))
    async def broadcast_test_handler(message: Message, command: CommandObject) -> None:
        if not await ensure_admin(message):
            return

        text = command.args or (
            "<b>Тестовое сообщение.</b>\n\n"
            "Проверка, как приходит ещё одно тёплое касание в течение дня. ✨"
        )
        await message.bot.send_message(context.settings.lika_chat_id, text)
        await message.answer("Тестовое сообщение отправлено Лике.")

    @router.message(Command("send_final_now"))
    async def send_final_now_handler(message: Message) -> None:
        if not await ensure_admin(message):
            return

        lika_user_id = await ensure_lika_user_id()
        state = await context.repositories.progress.get_state(lika_user_id)
        first_open = not bool(state["final_opened_at"])

        await message.bot.send_message(
            context.settings.lika_chat_id,
            context.services.story.final_opened_text(first_open),
        )
        if first_open:
            await context.repositories.progress.mark_final_opened(lika_user_id)

        selection = await context.services.videos.select_final_video(lika_user_id)
        if selection.status == "ready" and selection.video is not None:
            path = context.services.videos.absolute_path(selection.video.relative_path)
            if path.exists():
                media_file = FSInputFile(path)
                caption = context.services.story.build_video_caption(selection.video.category)
                if is_voice_file(path):
                    await message.bot.send_voice(
                        context.settings.lika_chat_id,
                        voice=media_file,
                        caption=caption,
                    )
                else:
                    await message.bot.send_video(
                        context.settings.lika_chat_id,
                        video=media_file,
                        caption=caption,
                    )
                await context.repositories.videos.mark_sent(lika_user_id, selection.video.id, "admin:final")

        await message.answer("Финал отправлен принудительно.")

    @router.message(Command("debug_progress"))
    async def debug_progress_handler(message: Message) -> None:
        if not await ensure_admin(message):
            return

        lika_user_id = await ensure_lika_user_id()
        state = await context.repositories.progress.get_state(lika_user_id)
        snapshot = await context.services.progress.get_snapshot(lika_user_id)
        unlock_state = context.services.progress.get_unlock_state(snapshot)

        await message.answer(
            "<b>Debug progress</b>\n\n"
            f"intro_seen_at: <code>{state['intro_seen_at']}</code>\n"
            f"special_opened_at: <code>{state['special_opened_at']}</code>\n"
            f"final_opened_at: <code>{state['final_opened_at']}</code>\n"
            f"videos_watched: <b>{snapshot.videos_watched}</b>\n"
            f"personal_messages_opened: <b>{snapshot.personal_messages_opened}</b>\n"
            f"scheduled_messages_sent: <b>{snapshot.scheduled_messages_sent}</b>\n"
            f"total_opened: <b>{snapshot.total_opened}</b>\n"
            f"special_unlocked: <b>{unlock_state.special_unlocked}</b>\n"
            f"final_unlocked: <b>{unlock_state.final_unlocked}</b>"
        )

    @router.message(Command("ai_style_info"))
    async def ai_style_info_handler(message: Message) -> None:
        if not await ensure_admin(message):
            return

        try:
            profile = await context.services.style_profile.get_profile()
        except Exception as error:
            await message.answer(
                "<b>Профиль стиля пока не собрался.</b>\n\n"
                f"<code>{error}</code>"
            )
            return

        common_words = ", ".join(profile.common_words[:8]) if profile.common_words else "пока не выделились"
        emojis = " ".join(profile.emoji_signatures[:6]) if profile.emoji_signatures else "без ярко выраженной эмодзи-подписи"

        await message.answer(
            "<b>Профиль стиля</b>\n\n"
            f"Источник: <code>{html.escape(profile.source_path)}</code>\n"
            f"Чат: <b>{html.escape(profile.chat_title or 'без названия')}</b>\n"
            f"Автор стиля: <b>{html.escape(profile.author_name)}</b>\n"
            f"Текстовых сообщений автора: <b>{profile.total_text_messages}</b>\n"
            f"Средняя длина: <b>{profile.avg_message_length}</b> символов\n"
            f"Выборка примеров для генератора: <b>{len(profile.sample_messages)}</b>\n"
            f"Частые слова: <b>{html.escape(common_words)}</b>\n"
            f"Эмодзи: <b>{html.escape(emojis)}</b>"
        )

    @router.message(Command("ai_test"))
    async def ai_test_handler(message: Message, command: CommandObject) -> None:
        if not await ensure_admin(message):
            return

        request = (command.args or "").strip() or (
            "Сделай 3 коротких тёплых варианта сообщения для Лики на день рождения. "
            "Пусть это будет нежно, живо и по-человечески."
        )

        try:
            draft = await context.services.ai_writer.generate_test_draft(request)
        except Exception as error:
            await message.answer(
                "<b>Тестовый генератор пока не смог ответить.</b>\n\n"
                f"<code>{error}</code>"
            )
            return

        await message.answer(
            "<b>AI test draft</b>\n\n"
            f"Модель: <code>{html.escape(draft.model)}</code>\n"
            f"Автор стиля: <b>{html.escape(draft.author_name)}</b>\n"
            f"Использовано примеров: <b>{draft.sample_count}</b>\n"
            f"Запрос: <i>{html.escape(draft.request)}</i>\n\n"
            f"{html.escape(draft.text)}"
        )

    @router.message(Command("reschedule"))
    async def reschedule_handler(message: Message) -> None:
        if not await ensure_admin(message):
            return
        if context.scheduler is None:
            await message.answer("Планировщик ещё не создан.")
            return

        jobs_count = await context.scheduler.reschedule_all()
        await message.answer(f"Планировщик пересобран. Активных задач сейчас: <b>{jobs_count}</b>.")

    return router
