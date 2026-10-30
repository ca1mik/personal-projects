from __future__ import annotations

import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InaccessibleMessage, Message, PreCheckoutQuery

from src.keyboards.telegram import resolve_telegram_menu_input
from src.models import Platform
from src.repositories.subscriptions import SubscriptionRepository
from src.repositories.users import UserRepository
from src.services.payments import TelegramInvoiceService
from src.services.payments.service import PaymentApplicationService
from src.services.platforms import IncomingEvent
from src.services.workflow import SupportBotWorkflow

logger = logging.getLogger(__name__)


def _chat_id_from_callback_message(
    message: Message | InaccessibleMessage | None, fallback_user_id: int
) -> str:
    chat = getattr(message, "chat", None)
    if chat is None:
        return str(fallback_user_id)
    return str(chat.id)


def _text_from_callback_message(
    message: Message | InaccessibleMessage | None,
) -> str | None:
    text = getattr(message, "text", None)
    return text if isinstance(text, str) else None


def create_telegram_router(
    *,
    workflow: SupportBotWorkflow,
    gateway,
    payment_service: PaymentApplicationService,
    invoice_service: TelegramInvoiceService,
) -> Router:
    router = Router()

    async def dispatch_event(
        message: Message, *, action: str | None = None, command: str | None = None
    ) -> None:
        if message.from_user is None:
            logger.warning("telegram.dispatch_skipped reason=no_from_user")
            return
        event = IncomingEvent(
            platform=Platform.TELEGRAM,
            platform_user_id=str(message.from_user.id),
            chat_id=str(message.chat.id),
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            text=message.text,
            command=command,
            action=action,
        )
        try:
            result = await workflow.handle_event(event)
            for outgoing in result.messages:
                await gateway.send_message(
                    chat_id=str(message.chat.id),
                    user_id=str(message.from_user.id),
                    message=outgoing,
                )
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.exception(
                "telegram.dispatch_failed user_id=%s error=%s",
                message.from_user.id,
                exc,
            )
            await message.answer(
                "Сейчас не получилось обработать сообщение. Попробуй ещё раз чуть позже."
            )

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        await dispatch_event(message, command="/start")

    @router.message(Command("minute"))
    async def minute_handler(message: Message) -> None:
        await dispatch_event(message, command="/minute")

    @router.message(Command("diary"))
    async def diary_handler(message: Message) -> None:
        await dispatch_event(message, command="/diary")

    @router.message(Command("subscription"))
    async def subscription_handler(message: Message) -> None:
        await dispatch_event(message, command="/subscription")

    @router.callback_query()
    async def callback_handler(callback: CallbackQuery) -> None:
        if callback.data and callback.data.startswith("pay:telegram:"):
            if not invoice_service.is_configured():
                await callback.answer(
                    "Telegram-оплата сейчас недоступна", show_alert=True
                )
                return
            try:
                plan_code = callback.data.split(":")[-1]
                plan = workflow.subscriptions.get_plan(plan_code)
                invoice = invoice_service.build_invoice(plan)
                if not isinstance(callback.message, Message):
                    await callback.answer("Не удалось открыть invoice", show_alert=True)
                    return
                await callback.message.answer_invoice(**invoice)
                await callback.answer()
            except TelegramAPIError as exc:  # pragma: no cover - network branch
                logger.exception(
                    "telegram.invoice_failed user_id=%s error=%s",
                    callback.from_user.id,
                    exc,
                )
                await callback.answer(
                    "Не удалось открыть оплату в Telegram", show_alert=True
                )
            return

        event = IncomingEvent(
            platform=Platform.TELEGRAM,
            platform_user_id=str(callback.from_user.id),
            chat_id=_chat_id_from_callback_message(
                callback.message, callback.from_user.id
            ),
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            text=_text_from_callback_message(callback.message),
            action=callback.data,
        )
        try:
            result = await workflow.handle_event(event)
            for outgoing in result.messages:
                await gateway.send_message(
                    chat_id=_chat_id_from_callback_message(
                        callback.message, callback.from_user.id
                    ),
                    user_id=str(callback.from_user.id),
                    message=outgoing,
                )
            await callback.answer()
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.exception(
                "telegram.callback_failed user_id=%s error=%s",
                callback.from_user.id,
                exc,
            )
            await callback.answer(
                "Сейчас не получилось обработать действие", show_alert=True
            )

    @router.pre_checkout_query()
    async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery) -> None:
        await pre_checkout_query.answer(ok=True)

    @router.message(F.successful_payment)
    async def successful_payment_handler(message: Message) -> None:
        if message.from_user is None or message.successful_payment is None:
            logger.warning(
                "telegram.successful_payment_skipped reason=missing_user_or_payload"
            )
            return
        successful_payment = message.successful_payment
        amount_rub = Decimal(successful_payment.total_amount) / Decimal("100")
        try:
            plan_code = invoice_service.parse_payload(
                successful_payment.invoice_payload
            )
            subscription = None
            async with workflow.session_factory() as session:
                user = await UserRepository(session).get_by_platform_user_id(
                    Platform.TELEGRAM, str(message.from_user.id)
                )
                if user is None:
                    raise RuntimeError("Telegram payment received for unknown user")
                await payment_service.apply_telegram_success(
                    session,
                    user_id=user.id,
                    plan_code=plan_code,
                    provider_payment_id=successful_payment.telegram_payment_charge_id,
                    amount_rub=amount_rub,
                )
                subscription = await workflow.subscriptions.mark_expired_if_needed(
                    SubscriptionRepository(session), user.id
                )
                await session.commit()
            await gateway.send_message(
                chat_id=str(message.chat.id),
                user_id=str(message.from_user.id),
                message=workflow._subscription_message(subscription),
            )
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.exception(
                "telegram.successful_payment_failed user_id=%s error=%s",
                message.from_user.id,
                exc,
            )
            await message.answer(
                "Оплата получена, но активация подписки задерживается. Напиши в поддержку, пожалуйста."
            )

    @router.message(F.text)
    async def text_handler(message: Message) -> None:
        action, command = resolve_telegram_menu_input(message.text)
        await dispatch_event(message, action=action, command=command)

    return router
