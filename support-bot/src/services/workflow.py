from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.keyboards import (
    adult_confirmation_buttons,
    checkin_buttons,
    consent_buttons,
    legal_document_buttons,
    payment_link_buttons,
    pricing_buttons,
    start_buttons,
    subscription_buttons,
)
from src.models import MessageRole, Platform, SubscriptionPlan
from src.repositories import (
    AuditEventRepository,
    ConsentRepository,
    ConversationRepository,
    CrisisRepository,
    DeletionRequestRepository,
    DiaryRepository,
    SubscriptionRepository,
    UserPreferenceRepository,
    UserRepository,
)
from src.services.crisis import CrisisService
from src.services.documents import DocumentService
from src.services.llm import LLMMessage, LLMService
from src.services.notifications import NotificationService
from src.services.onboarding import OnboardingService, OnboardingStep
from src.services.payments import PaymentApplicationService
from src.services.platforms import IncomingEvent, OutgoingMessage
from src.services.subscriptions import SubscriptionService
from src.services.utils import utcnow

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WorkflowResult:
    messages: list[OutgoingMessage]


class SupportBotWorkflow:
    EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        documents: DocumentService,
        onboarding: OnboardingService,
        crisis: CrisisService,
        llm: LLMService,
        subscriptions: SubscriptionService,
        payments: PaymentApplicationService,
        notifications: NotificationService,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.documents = documents
        self.onboarding = onboarding
        self.crisis = crisis
        self.llm = llm
        self.subscriptions = subscriptions
        self.payments = payments
        self.notifications = notifications

    async def handle_event(self, event: IncomingEvent) -> WorkflowResult:
        async with self.session_factory() as session:
            users = UserRepository(session)
            consents = ConsentRepository(session)
            preferences = UserPreferenceRepository(session)
            subscriptions = SubscriptionRepository(session)
            conversations = ConversationRepository(session)
            crises = CrisisRepository(session)
            deletions = DeletionRequestRepository(session)
            diary = DiaryRepository(session)
            audits = AuditEventRepository(session)

            user = await users.get_or_create(
                platform=event.platform,
                platform_user_id=event.platform_user_id,
                username=event.username,
                first_name=event.first_name,
            )
            user.last_seen_at = utcnow()
            consent = await consents.get_for_user(user.id)
            preference = await preferences.get_or_create(user.id)

            if event.command == "/start" and not event.action:
                await session.commit()
                return WorkflowResult(messages=[self._start_message()])

            if event.action == "start:about":
                await session.commit()
                return WorkflowResult(
                    messages=[
                        OutgoingMessage(
                            text=self.documents.load_content("onboarding.md")
                        )
                    ]
                )

            if event.action == "start:legal":
                await session.commit()
                return WorkflowResult(messages=[self._legal_message()])

            if event.action and event.action.startswith("legal:show:"):
                slug = event.action.split(":")[-1]
                await session.commit()
                return WorkflowResult(messages=[self._legal_document_message(slug)])

            if event.action == "start:support":
                await session.commit()
                return WorkflowResult(
                    messages=[
                        OutgoingMessage(
                            text=f"Если нужна помощь по сервису, напиши: {self.settings.support_contact}"
                        )
                    ]
                )

            if event.action == "start:free":
                await session.commit()
                return WorkflowResult(messages=[self._adult_prompt()])

            if event.action == "adult:yes":
                user.is_adult_confirmed = True
                await audits.create(
                    user_id=user.id,
                    category="consents",
                    action="adult_confirmed",
                    payload={"platform": user.platform},
                )
                await session.commit()
                return WorkflowResult(messages=[self._consent_message("privacy")])

            if event.action == "adult:no":
                await session.commit()
                return WorkflowResult(
                    messages=[
                        OutgoingMessage(
                            text="Доступ к боту возможен только для пользователей 18+. Если это ошибка, вернись позже и подтверди возраст.",
                        )
                    ]
                )

            if event.action and event.action.startswith("consent:"):
                _, slug, decision = event.action.split(":")
                if decision == "decline":
                    await audits.create(
                        user_id=user.id, category="consents", action=f"{slug}_declined"
                    )
                    await session.commit()
                    return WorkflowResult(
                        messages=[
                            OutgoingMessage(
                                text="Без обязательных согласий я не могу продолжить работу. Если захочешь вернуться, нажми /start.",
                            )
                        ]
                    )

                document = self.documents.legal_documents[slug]
                accepted_at = utcnow()
                if slug == "privacy":
                    await consents.accept_privacy(
                        user.id, document.version, accepted_at
                    )
                elif slug == "offer":
                    await consents.accept_offer(user.id, document.version, accepted_at)
                elif slug == "disclaimer":
                    await consents.accept_disclaimer(
                        user.id, document.version, accepted_at
                    )
                await audits.create(
                    user_id=user.id,
                    category="consents",
                    action=f"{slug}_accepted",
                    payload={
                        "version": document.version,
                        "accepted_at": accepted_at.isoformat(),
                    },
                )
                await session.commit()
                next_step = self.onboarding.get_next_step(
                    user=user,
                    consent=await consents.get_for_user(user.id),
                    preference=preference,
                )
                return WorkflowResult(messages=[self._message_for_step(next_step)])

            if event.action == "checkin:yes":
                preference.daily_checkin_enabled = True
                preference.checkin_consent_answered = True
                preference.pending_action = "checkin_hour"
                preference.pending_context = None
                preference.checkin_hour_utc = (
                    preference.checkin_hour_utc or self.settings.checkin_hour_utc
                )
                await audits.create(
                    user_id=user.id, category="preferences", action="checkin_enabled"
                )
                await session.commit()
                return WorkflowResult(
                    messages=[
                        OutgoingMessage(
                            text=(
                                "Я могу отправлять ежедневный чек-ин.\n"
                                "Напиши удобный час от 0 до 23.\n"
                                "Например: 9, 14 или 21.\n"
                                f"Если не хочется выбирать, просто отправь {self.settings.checkin_hour_utc}."
                            )
                        )
                    ]
                )

            if event.action == "checkin:no":
                preference.daily_checkin_enabled = False
                preference.checkin_consent_answered = True
                preference.pending_action = None
                preference.pending_context = None
                await audits.create(
                    user_id=user.id, category="preferences", action="checkin_disabled"
                )
                await session.commit()
                return WorkflowResult(
                    messages=[OutgoingMessage(text=self._ready_text())]
                )

            if event.command == "/subscription" or event.action == "menu:subscription":
                subscription = await self.subscriptions.mark_expired_if_needed(
                    subscriptions, user.id
                )
                await session.commit()
                return WorkflowResult(
                    messages=[self._subscription_message(subscription)]
                )

            if event.action == "subscription:cancel_autorenew":
                subscription = await subscriptions.get_latest_for_user(user.id)
                changed = self.subscriptions.disable_auto_renew(subscription)
                if changed:
                    await audits.create(
                        user_id=user.id,
                        category="subscriptions",
                        action="auto_renew_disabled",
                    )
                await session.commit()
                return WorkflowResult(
                    messages=[
                        OutgoingMessage(
                            text=(
                                "Автопродление отключено."
                                if changed
                                else "Активная подписка не найдена."
                            )
                        )
                    ]
                )

            if event.action == "subscription:change_plan":
                await session.commit()
                return WorkflowResult(messages=[self._pricing_message(event.platform)])

            if event.action == "subscription:refund":
                await self.notifications.notify_admins(
                    f"Запрос на возврат от user_id={user.id}, platform={user.platform}"
                )
                await audits.create(
                    user_id=user.id, category="payments", action="refund_requested"
                )
                await session.commit()
                return WorkflowResult(
                    messages=[
                        OutgoingMessage(
                            text=f"Запрос на возврат принят. Напиши в поддержку: {self.settings.support_contact}, и мы свяжемся с тобой.",
                        )
                    ]
                )

            if event.action == "subscription:delete_data":
                request = await deletions.create_pending(user.id)
                await self.notifications.notify_admins(
                    f"Новый запрос на удаление данных: request_id={request.id}, user_id={user.id}, platform={user.platform}",
                )
                await audits.create(
                    user_id=user.id,
                    category="deletions",
                    action="deletion_requested",
                    payload={"request_id": request.id},
                )
                await session.commit()
                return WorkflowResult(
                    messages=[
                        OutgoingMessage(
                            text="Запрос на удаление данных создан. Администратор уже уведомлен."
                        )
                    ]
                )

            if event.action == "pricing:show":
                await session.commit()
                return WorkflowResult(messages=[self._pricing_message(event.platform)])

            if preference.pending_action == "checkin_hour" and event.text:
                return await self._handle_checkin_hour(
                    session, audits, preference, event.text
                )

            if preference.pending_action == "collect_receipt_email" and event.text:
                return await self._handle_receipt_email(
                    session, user, preference, audits, event.platform, event.text
                )

            if event.action and event.action.startswith("pay:mock:confirm:"):
                provider_payment_id = event.action.split(":")[-1]
                subscription = await self.payments.confirm_mock_payment(
                    session, provider_payment_id=provider_payment_id
                )
                await session.commit()
                if subscription is None:
                    return WorkflowResult(
                        messages=[
                            OutgoingMessage(
                                text="Демо-оплату не удалось подтвердить. Попробуй открыть тарифы ещё раз."
                            )
                        ]
                    )
                return WorkflowResult(
                    messages=[self._subscription_message(subscription)]
                )

            if event.action and event.action.startswith("pay:yookassa:"):
                plan_code = SubscriptionPlan(event.action.split(":")[-1])
                if self.settings.yookassa_enable_receipts and not (
                    user.email or self.settings.yookassa_receipt_default_email
                ):
                    preference.pending_action = "collect_receipt_email"
                    preference.pending_context = plan_code
                    await session.commit()
                    return WorkflowResult(
                        messages=[
                            OutgoingMessage(
                                text=(
                                    "Перед оплатой пришли, пожалуйста, email для электронного чека по 54-ФЗ. "
                                    "Мы используем его только для расчёта и чеков."
                                )
                            )
                        ]
                    )
                checkout = await self.payments.start_yookassa_checkout(
                    session,
                    user_id=user.id,
                    plan_code=plan_code,
                    customer_email=user.email,
                )
                await session.commit()
                return WorkflowResult(
                    messages=[
                        self._payment_message(
                            event.platform, checkout.payment_url, plan_code
                        )
                    ]
                )

            step = self.onboarding.get_next_step(
                user=user, consent=consent, preference=preference
            )
            if step != OnboardingStep.READY:
                await session.commit()
                return WorkflowResult(messages=[self._message_for_step(step)])

            subscription = await self.subscriptions.mark_expired_if_needed(
                subscriptions, user.id
            )

            if event.command == "/minute":
                await session.commit()
                return WorkflowResult(
                    messages=[OutgoingMessage(text=self._random_minute())]
                )

            if event.command == "/diary":
                diary_text = self._extract_command_payload(event.text or "")
                if diary_text:
                    await diary.create_entry(user.id, diary_text)
                    preference.pending_action = None
                    await audits.create(
                        user_id=user.id,
                        category="diary",
                        action="entry_created_via_command",
                    )
                    await session.commit()
                    return WorkflowResult(
                        messages=[
                            OutgoingMessage(
                                text="Запись в дневник сохранена. Спасибо, что поделилась."
                            )
                        ]
                    )

                preference.pending_action = "diary"
                await session.commit()
                return WorkflowResult(
                    messages=[
                        OutgoingMessage(
                            text="Напиши одну или несколько фраз благодарности, и я сохраню это в дневник."
                        )
                    ]
                )

            if preference.pending_action == "diary" and event.text:
                await diary.create_entry(user.id, event.text)
                preference.pending_action = None
                await audits.create(
                    user_id=user.id, category="diary", action="entry_created"
                )
                await session.commit()
                return WorkflowResult(
                    messages=[
                        OutgoingMessage(
                            text="Запись сохранена. Я добавила её в твой дневник благодарностей."
                        )
                    ]
                )

            if not event.text:
                await session.commit()
                return WorkflowResult(
                    messages=[OutgoingMessage(text="Напиши сообщение, и я отвечу.")]
                )

            is_active_subscription = self.subscriptions.is_active(subscription)
            if not is_active_subscription and (
                user.preview_exhausted
                or user.free_preview_messages_used
                >= self.settings.preview_user_messages
            ):
                await session.commit()
                return WorkflowResult(
                    messages=[
                        OutgoingMessage(
                            text="Бесплатное превью уже закончилось. Чтобы продолжить разговор, выбери подходящий тариф.",
                            buttons=pricing_buttons(
                                include_telegram_fallback=self._telegram_fallback_enabled(
                                    event.platform
                                )
                            ),
                        )
                    ]
                )

            detection = self.crisis.detect(event.text)
            if detection.is_crisis:
                incident = await crises.create(
                    user_id=user.id,
                    message=event.text,
                    detected_reason=detection.reason or "unknown",
                )
                incident.notified_admins_at = utcnow()
                await self.notifications.notify_admins(
                    f"Кризисный инцидент: incident_id={incident.id}, user_id={user.id}, reason={incident.detected_reason}",
                )
                await audits.create(
                    user_id=user.id,
                    category="crisis",
                    action="incident_detected",
                    payload={
                        "incident_id": incident.id,
                        "reason": incident.detected_reason,
                    },
                )
                await session.commit()
                return WorkflowResult(
                    messages=[OutgoingMessage(text=self.crisis.build_response())]
                )

            conversation = await conversations.get_or_create(user.id)
            recent_messages = await conversations.get_recent_messages(
                conversation.id, self.settings.rolling_window_messages
            )
            llm_messages = [
                LLMMessage(role=message.role, content=message.content)
                for message in recent_messages
            ]
            llm_messages.append(LLMMessage(role="user", content=event.text))

            await conversations.add_message(
                conversation.id, MessageRole.USER, event.text
            )
            reply = await self.llm.generate_reply(
                summary=conversation.summary, messages=llm_messages
            )
            await conversations.add_message(
                conversation.id, MessageRole.ASSISTANT, reply
            )

            total_messages = await conversations.count_messages(conversation.id)
            if (
                total_messages
                and total_messages % self.settings.summary_threshold_messages == 0
            ):
                latest_for_summary = await conversations.get_recent_messages(
                    conversation.id,
                    self.settings.rolling_window_messages * 2,
                )
                summary = await self.llm.summarize(
                    current_summary=conversation.summary,
                    messages=[
                        LLMMessage(role=message.role, content=message.content)
                        for message in latest_for_summary
                    ],
                )
                await conversations.update_summary(conversation, summary)

            responses = [OutgoingMessage(text=reply)]
            if not is_active_subscription:
                user.free_preview_messages_used += 1
                if (
                    user.free_preview_messages_used
                    >= self.settings.preview_user_messages
                ):
                    user.preview_exhausted = True
                    user.preview_completed_at = user.preview_completed_at or utcnow()
                    responses.append(
                        OutgoingMessage(
                            text="Это был последний бесплатный ответ. Если хочешь продолжить, оплата уже доступна ниже.",
                            buttons=pricing_buttons(
                                include_telegram_fallback=self._telegram_fallback_enabled(
                                    event.platform
                                )
                            ),
                        )
                    )
            await session.commit()
            return WorkflowResult(messages=responses)

    async def _handle_checkin_hour(
        self,
        session,
        audits: AuditEventRepository,
        preference,
        text: str,
    ) -> WorkflowResult:
        try:
            hour = int(text.strip())
        except ValueError:
            await session.commit()
            return WorkflowResult(
                messages=[
                    OutgoingMessage(text="Пожалуйста, пришли целое число от 0 до 23.")
                ]
            )
        if not 0 <= hour <= 23:
            await session.commit()
            return WorkflowResult(
                messages=[
                    OutgoingMessage(text="Час должен быть в диапазоне от 0 до 23.")
                ]
            )
        preference.checkin_hour_utc = hour
        preference.pending_action = None
        preference.pending_context = None
        await audits.create(
            user_id=preference.user_id,
            category="preferences",
            action="checkin_hour_set",
            payload={"hour_utc": hour},
        )
        await session.commit()
        return WorkflowResult(messages=[OutgoingMessage(text=self._ready_text())])

    async def _handle_receipt_email(
        self,
        session,
        user,
        preference,
        audits: AuditEventRepository,
        platform: Platform,
        text: str,
    ) -> WorkflowResult:
        email = text.strip()
        if not self.EMAIL_RE.match(email):
            await session.commit()
            return WorkflowResult(
                messages=[
                    OutgoingMessage(
                        text="Похоже, это не email. Пришли адрес в формате name@example.com."
                    )
                ]
            )
        user.email = email
        plan_code = SubscriptionPlan(
            preference.pending_context or SubscriptionPlan.MONTH
        )
        preference.pending_action = None
        preference.pending_context = None
        await audits.create(
            user_id=user.id,
            category="payments",
            action="receipt_email_saved",
            payload={"email": email},
        )
        checkout = await self.payments.start_yookassa_checkout(
            session,
            user_id=user.id,
            plan_code=plan_code,
            customer_email=user.email,
        )
        await session.commit()
        return WorkflowResult(
            messages=[self._payment_message(platform, checkout.payment_url, plan_code)]
        )

    def _start_message(self) -> OutgoingMessage:
        text = (
            f"{self.documents.load_content('onboarding.md')}\n\n"
            "Выбери, с чего начнём."
        )
        return OutgoingMessage(text=text, buttons=start_buttons())

    def _adult_prompt(self) -> OutgoingMessage:
        return OutgoingMessage(
            text="Подтверди, пожалуйста, что тебе исполнилось 18 лет.",
            buttons=adult_confirmation_buttons(),
        )

    def _legal_message(self) -> OutgoingMessage:
        docs = self.documents.legal_documents
        if not self._use_public_legal_urls():
            return OutgoingMessage(
                text="Ознакомься с документами. Нажми на нужный документ ниже, и я пришлю его прямо в чат.",
                buttons=legal_document_buttons(use_urls=False),
            )
        text = (
            "Ознакомься с документами:\n"
            f"1. Политика конфиденциальности: {docs['privacy'].public_url}\n"
            f"2. Оферта: {docs['offer'].public_url}\n"
            f"3. Дисклеймер: {docs['disclaimer'].public_url}"
        )
        return OutgoingMessage(text=text)

    def _consent_message(self, slug: str) -> OutgoingMessage:
        docs = self.documents.legal_documents
        titles = {
            "privacy": "Согласие на обработку персональных данных",
            "offer": "Согласие с офертой",
            "disclaimer": "Согласие с дисклеймером",
        }
        descriptions = {
            "privacy": "Перед началом диалога нужно принять политику конфиденциальности.",
            "offer": "Следующий обязательный шаг — принять оферту сервиса.",
            "disclaimer": "И последний обязательный шаг — принять дисклеймер.",
        }
        return OutgoingMessage(
            text=f"<b>{titles[slug]}</b>\n{descriptions[slug]}",
            buttons=consent_buttons(
                slug=slug,
                document_url=(
                    docs[slug].public_url if self._use_public_legal_urls() else None
                ),
                document_action=f"legal:show:{slug}",
            ),
        )

    def _legal_document_message(self, slug: str) -> OutgoingMessage:
        document = self.documents.legal_documents[slug]
        return OutgoingMessage(text=document.content, disable_link_preview=True)

    def _payment_message(
        self, platform: Platform, payment_url: str, plan_code: SubscriptionPlan | str
    ) -> OutgoingMessage:
        if payment_url.startswith("mock://payment/"):
            return OutgoingMessage(
                text=(
                    "Это локальная демо-оплата. Нажми кнопку ниже, и я сразу "
                    "активирую подписку без внешнего платёжного сервиса."
                ),
                buttons=payment_link_buttons(
                    payment_url,
                    include_telegram_fallback=self._telegram_fallback_enabled(platform),
                    plan_slug=str(plan_code),
                ),
            )
        return OutgoingMessage(
            text="Открой ссылку оплаты. После успешного платежа подписка активируется автоматически.",
            buttons=payment_link_buttons(
                payment_url,
                include_telegram_fallback=self._telegram_fallback_enabled(platform),
                plan_slug=str(plan_code),
            ),
        )

    def _checkin_prompt(self) -> OutgoingMessage:
        return OutgoingMessage(
            text="Хочешь, чтобы я присылала ежедневный чек-ин?\n\nПример:\nПривет.\nКак ты сегодня?\nЧто чувствуешь?",
            buttons=checkin_buttons(),
        )

    def _pricing_message(self, platform: Platform) -> OutgoingMessage:
        return OutgoingMessage(
            text=self.subscriptions.format_pricing_text(),
            buttons=pricing_buttons(
                include_telegram_fallback=self._telegram_fallback_enabled(platform)
            ),
        )

    def _subscription_message(self, subscription) -> OutgoingMessage:
        return OutgoingMessage(
            text=self.subscriptions.format_subscription(subscription),
            buttons=subscription_buttons(),
        )

    def _message_for_step(self, step: OnboardingStep) -> OutgoingMessage:
        if step == OnboardingStep.ADULT_CONFIRMATION:
            return self._adult_prompt()
        if step == OnboardingStep.PRIVACY:
            return self._consent_message("privacy")
        if step == OnboardingStep.OFFER:
            return self._consent_message("offer")
        if step == OnboardingStep.DISCLAIMER:
            return self._consent_message("disclaimer")
        if step == OnboardingStep.CHECKIN:
            return self._checkin_prompt()
        return self._start_message()

    def _ready_text(self) -> str:
        return "Все обязательные шаги завершены. Можешь написать мне первое сообщение. У тебя есть бесплатное превью на 3 ответа."

    def _random_minute(self) -> str:
        content = self.documents.load_content("messages.md")
        blocks = [
            block.strip()
            for block in content.split("\n\n")
            if block.strip()
            and not block.strip().lower().startswith("минутка для себя")
        ]
        return random.choice(blocks)

    def _telegram_fallback_enabled(self, platform: Platform) -> bool:
        return platform == Platform.TELEGRAM and self.settings.telegram_payments_enabled

    def _use_public_legal_urls(self) -> bool:
        privacy_url = self.documents.legal_documents["privacy"].public_url
        return privacy_url.startswith("http://") or privacy_url.startswith("https://")

    @staticmethod
    def _extract_command_payload(text: str) -> str:
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) == 2 else ""
