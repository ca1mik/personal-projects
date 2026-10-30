from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

try:
    import celery  # noqa: F401
except ModuleNotFoundError:
    fake_celery_module = types.ModuleType("celery")
    fake_schedules_module = types.ModuleType("celery.schedules")

    class FakeCelery:
        def __init__(self, *args, **kwargs) -> None:
            self.conf = SimpleNamespace()

        def task(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def autodiscover_tasks(self, *args, **kwargs) -> None:
            return None

    def fake_crontab(*args, **kwargs):
        return {"args": args, "kwargs": kwargs}

    fake_celery_module.Celery = FakeCelery
    fake_schedules_module.crontab = fake_crontab
    sys.modules["celery"] = fake_celery_module
    sys.modules["celery.schedules"] = fake_schedules_module

from src.models import Platform, User
from src.repositories import DiaryRepository, UserPreferenceRepository
from src.scheduler import tasks
from src.services.utils import utcnow


class SchedulerLLMStub:
    async def summarize(self, *, current_summary, messages):
        return "Краткая недельная сводка"


def _scheduler_container(*, settings, session_factory, notifications):
    return SimpleNamespace(
        settings=settings,
        session_factory=session_factory,
        notifications=notifications,
        llm=SchedulerLLMStub(),
    )


@pytest.mark.asyncio
async def test_daily_checkin_is_sent_only_with_consent(
    db_session_factory,
    test_settings,
    recording_notifications,
    monkeypatch,
) -> None:
    async with db_session_factory() as session:
        user_ok = User(
            platform=Platform.TELEGRAM,
            platform_user_id="101",
            username="ok",
            first_name="O",
        )
        user_skip = User(
            platform=Platform.TELEGRAM,
            platform_user_id="102",
            username="skip",
            first_name="S",
        )
        session.add_all([user_ok, user_skip])
        await session.flush()

        preferences = UserPreferenceRepository(session)
        pref_ok = await preferences.get_or_create(user_ok.id)
        pref_ok.daily_checkin_enabled = True
        pref_ok.checkin_consent_answered = True
        pref_ok.checkin_hour_utc = utcnow().hour

        pref_skip = await preferences.get_or_create(user_skip.id)
        pref_skip.daily_checkin_enabled = True
        pref_skip.checkin_consent_answered = False
        pref_skip.checkin_hour_utc = utcnow().hour
        await session.commit()

    monkeypatch.setattr(
        tasks,
        "get_scheduler_container",
        lambda: _scheduler_container(
            settings=test_settings,
            session_factory=db_session_factory,
            notifications=recording_notifications,
        ),
    )

    sent = await tasks._send_daily_checkins()

    assert sent == 1
    assert len(recording_notifications.user_messages) == 1
    assert (
        recording_notifications.user_messages[0][1]
        == test_settings.daily_checkin_message
    )


@pytest.mark.asyncio
async def test_weekly_diary_summary_sends_message(
    db_session_factory,
    test_settings,
    recording_notifications,
    monkeypatch,
) -> None:
    async with db_session_factory() as session:
        user = User(
            platform=Platform.TELEGRAM,
            platform_user_id="201",
            username="mom",
            first_name="A",
        )
        session.add(user)
        await session.flush()

        diary_repo = DiaryRepository(session)
        await diary_repo.create_entry(user.id, "Сегодня я благодарна за помощь подруги")
        await session.commit()

    monkeypatch.setattr(
        tasks,
        "get_scheduler_container",
        lambda: _scheduler_container(
            settings=test_settings,
            session_factory=db_session_factory,
            notifications=recording_notifications,
        ),
    )

    sent = await tasks._send_weekly_diary_summaries()

    assert sent == 1
    assert recording_notifications.user_messages
    assert (
        "Твоя недельная сводка дневника" in recording_notifications.user_messages[0][1]
    )


@pytest.mark.asyncio
async def test_scheduled_jobs_do_not_fail_without_users(
    db_session_factory,
    test_settings,
    recording_notifications,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        tasks,
        "get_scheduler_container",
        lambda: _scheduler_container(
            settings=test_settings,
            session_factory=db_session_factory,
            notifications=recording_notifications,
        ),
    )

    daily_sent = await tasks._send_daily_checkins()
    weekly_sent = await tasks._send_weekly_diary_summaries()

    assert daily_sent == 0
    assert weekly_sent == 0
    assert recording_notifications.user_messages == []


@pytest.mark.asyncio
async def test_daily_checkin_respects_global_env_switch(
    db_session_factory,
    test_settings,
    recording_notifications,
    monkeypatch,
) -> None:
    disabled_settings = test_settings.model_copy(update={"checkin_enabled": False})
    monkeypatch.setattr(
        tasks,
        "get_scheduler_container",
        lambda: _scheduler_container(
            settings=disabled_settings,
            session_factory=db_session_factory,
            notifications=recording_notifications,
        ),
    )

    sent = await tasks._send_daily_checkins()

    assert sent == 0
