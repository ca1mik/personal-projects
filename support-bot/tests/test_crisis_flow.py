from __future__ import annotations

import pytest

from src.models import Platform
from src.repositories import CrisisRepository
from src.services.platforms import IncomingEvent


def _event(
    *,
    text: str | None = None,
    action: str | None = None,
    command: str | None = None,
    platform: Platform = Platform.TELEGRAM,
) -> IncomingEvent:
    return IncomingEvent(
        platform=platform,
        platform_user_id="42",
        chat_id="42",
        username="mom",
        first_name="Anna",
        text=text,
        action=action,
        command=command,
    )


async def _complete_onboarding(workflow) -> None:
    for event in (
        _event(command="/start"),
        _event(action="start:free"),
        _event(action="adult:yes"),
        _event(action="consent:privacy:accept"),
        _event(action="consent:offer:accept"),
        _event(action="consent:disclaimer:accept"),
        _event(action="checkin:no"),
    ):
        await workflow.handle_event(event)


@pytest.mark.parametrize(
    ("text", "expected_reason"),
    [
        ("Я не хочу жить", "suicide"),
        ("Мне хочется порезать себя", "self_harm"),
        ("Меня бьют дома", "violence"),
        ("Боюсь, что могу навредить ребенку", "child_harm"),
    ],
)
@pytest.mark.asyncio
async def test_crisis_flow_logs_incident_skips_llm_and_notifies_admins(
    workflow, db_session_factory, text: str, expected_reason: str
) -> None:
    await _complete_onboarding(workflow)

    provider = workflow.llm.provider
    before_calls = len(provider.generate_calls)
    result = await workflow.handle_event(_event(text=text))
    after_calls = len(provider.generate_calls)

    assert "112" in result.messages[0].text
    assert "8-800-2000-122" in result.messages[0].text
    assert "8-495-989-50-50" in result.messages[0].text
    assert after_calls == before_calls
    assert workflow.notifications.admin_messages

    async with db_session_factory() as session:
        incidents = await CrisisRepository(session).list_recent(limit=10)

    assert len(incidents) == 1
    assert incidents[0].detected_reason == expected_reason
    assert incidents[0].notified_admins_at is not None
