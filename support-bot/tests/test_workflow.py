from __future__ import annotations

import pytest

from src.models import Platform, SubscriptionPlan, User
from src.repositories.subscriptions import SubscriptionRepository
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


@pytest.mark.asyncio
async def test_onboarding_flow_reaches_ready_state(workflow) -> None:
    start = await workflow.handle_event(_event(command="/start"))
    assert "эмоциональной поддержки" in start.messages[0].text

    adult = await workflow.handle_event(_event(action="start:free"))
    assert "18" in adult.messages[0].text

    privacy = await workflow.handle_event(_event(action="adult:yes"))
    assert "персональных данных" in privacy.messages[0].text

    offer = await workflow.handle_event(_event(action="consent:privacy:accept"))
    assert "офертой" in offer.messages[0].text

    disclaimer = await workflow.handle_event(_event(action="consent:offer:accept"))
    assert "дисклеймером" in disclaimer.messages[0].text

    checkin = await workflow.handle_event(
        _event(action="consent:disclaimer:accept")
    )
    assert "UTC" not in checkin.messages[0].text
    assert "ежедневный чек-ин" in checkin.messages[0].text

    ready = await workflow.handle_event(_event(action="checkin:no"))
    assert "бесплатное превью" in ready.messages[0].text


@pytest.mark.asyncio
async def test_consent_blocking_before_onboarding_complete(workflow) -> None:
    result = await workflow.handle_event(_event(text="Мне тяжело"))
    assert "18" in result.messages[0].text


@pytest.mark.asyncio
async def test_preview_limit_allows_only_three_responses(workflow) -> None:
    await _complete_onboarding(workflow)

    first = await workflow.handle_event(_event(text="Первое сообщение"))
    second = await workflow.handle_event(_event(text="Второе сообщение"))
    third = await workflow.handle_event(_event(text="Третье сообщение"))
    fourth = await workflow.handle_event(_event(text="Четвёртое сообщение"))

    assert first.messages[0].text == "reply"
    assert second.messages[0].text == "reply"
    assert third.messages[0].text == "reply"
    assert len(third.messages) == 2
    assert "последний бесплатный ответ" in third.messages[1].text
    assert "превью уже закончилось" in fourth.messages[0].text


@pytest.mark.asyncio
async def test_active_subscription_unlocks_full_dialog(
    workflow, db_session_factory
) -> None:
    await _complete_onboarding(workflow)

    async with db_session_factory() as session:
        user = await session.get(User, 1)
        repository = SubscriptionRepository(session)
        await workflow.subscriptions.activate_from_payment(
            repository, user_id=user.id, plan_code=SubscriptionPlan.MONTH
        )
        await session.commit()

    messages = []
    for idx in range(5):
        result = await workflow.handle_event(_event(text=f"Сообщение {idx}"))
        messages.append(result.messages[0].text)
    assert messages == ["reply"] * 5


@pytest.mark.asyncio
async def test_crisis_message_stops_normal_dialog(workflow) -> None:
    await _complete_onboarding(workflow)
    result = await workflow.handle_event(_event(text="Я не хочу жить"))
    assert "112" in result.messages[0].text
    assert "8-800-2000-122" in result.messages[0].text


@pytest.mark.asyncio
async def test_local_legal_flow_uses_callbacks_instead_of_relative_urls(
    workflow,
) -> None:
    legal = await workflow.handle_event(_event(action="start:legal"))
    adult = await workflow.handle_event(_event(action="adult:yes"))
    doc = await workflow.handle_event(_event(action="legal:show:privacy"))

    assert legal.messages[0].buttons[0][0].action == "legal:show:privacy"
    assert adult.messages[0].buttons[0][0].action == "legal:show:privacy"
    assert "Политика конфиденциальности" in doc.messages[0].text
