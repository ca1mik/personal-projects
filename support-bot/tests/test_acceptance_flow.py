from __future__ import annotations

from datetime import timedelta

import pytest

from src.models import Platform, SubscriptionPlan, User
from src.repositories import (
    ConsentRepository,
    DeletionRequestRepository,
    SubscriptionRepository,
    UserRepository,
)
from src.services.platforms import IncomingEvent
from src.services.utils import utcnow


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
async def test_start_creates_user_record(workflow, db_session_factory) -> None:
    result = await workflow.handle_event(_event(command="/start"))

    assert "эмоциональной поддержки" in result.messages[0].text

    async with db_session_factory() as session:
        user = await UserRepository(session).get_by_platform_user_id(
            Platform.TELEGRAM, "42"
        )

    assert user is not None
    assert user.first_name == "Anna"


@pytest.mark.asyncio
async def test_consents_saved_with_versions_and_timestamps(
    workflow, db_session_factory, test_settings
) -> None:
    await _complete_onboarding(workflow)

    async with db_session_factory() as session:
        user = await UserRepository(session).get_by_platform_user_id(
            Platform.TELEGRAM, "42"
        )
        consent = await ConsentRepository(session).get_for_user(user.id)

    assert consent is not None
    assert consent.user_id == user.id
    assert consent.privacy_accepted is True
    assert consent.offer_accepted is True
    assert consent.disclaimer_accepted is True
    assert consent.privacy_version == test_settings.privacy_policy_version
    assert consent.offer_version == test_settings.offer_version
    assert consent.disclaimer_version == test_settings.disclaimer_version
    assert consent.privacy_accepted_at is not None
    assert consent.offer_accepted_at is not None
    assert consent.disclaimer_accepted_at is not None


@pytest.mark.asyncio
async def test_preview_is_available_only_once_even_after_subscription_expires(
    workflow, db_session_factory
) -> None:
    await _complete_onboarding(workflow)

    for text in ("Первое", "Второе", "Третье"):
        await workflow.handle_event(_event(text=text))

    async with db_session_factory() as session:
        user = await session.get(User, 1)
        repository = SubscriptionRepository(session)
        subscription = await workflow.subscriptions.activate_from_payment(
            repository,
            user_id=user.id,
            plan_code=SubscriptionPlan.MONTH,
            payment_method_id="pm_saved",
        )
        subscription.expires_at = utcnow() - timedelta(minutes=1)
        await session.commit()

    result = await workflow.handle_event(_event(text="После истечения подписки"))

    assert "превью уже закончилось" in result.messages[0].text


@pytest.mark.asyncio
async def test_delete_data_creates_request_and_notifies_admins(
    workflow, db_session_factory
) -> None:
    await _complete_onboarding(workflow)

    result = await workflow.handle_event(_event(action="subscription:delete_data"))

    assert "Запрос на удаление данных создан" in result.messages[0].text
    assert workflow.notifications.admin_messages

    async with db_session_factory() as session:
        requests = await DeletionRequestRepository(session).list_recent(limit=10)

    assert len(requests) == 1
    assert requests[0].user_id == 1


@pytest.mark.asyncio
async def test_cancel_auto_renew_and_change_plan_actions(
    workflow, db_session_factory
) -> None:
    await _complete_onboarding(workflow)

    async with db_session_factory() as session:
        user = await session.get(User, 1)
        repository = SubscriptionRepository(session)
        await workflow.subscriptions.activate_from_payment(
            repository,
            user_id=user.id,
            plan_code=SubscriptionPlan.MONTH,
            payment_method_id="pm_saved",
        )
        await session.commit()

    cancel = await workflow.handle_event(_event(action="subscription:cancel_autorenew"))
    pricing = await workflow.handle_event(_event(action="subscription:change_plan"))

    assert "Автопродление отключено" in cancel.messages[0].text
    assert "Неделя поддержки" in pricing.messages[0].text
    assert "Месяц рядом" in pricing.messages[0].text


@pytest.mark.asyncio
async def test_local_mock_payment_activates_subscription(workflow) -> None:
    await _complete_onboarding(workflow)

    for text in ("Первое", "Второе", "Третье"):
        await workflow.handle_event(_event(text=text))

    checkout = await workflow.handle_event(_event(action="pay:yookassa:month"))
    action = checkout.messages[0].buttons[0][0].action
    assert action is not None
    assert action.startswith("pay:mock:confirm:")

    subscription = await workflow.handle_event(_event(action=action))

    assert "Статус" in subscription.messages[0].text
