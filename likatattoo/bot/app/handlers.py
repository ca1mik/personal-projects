from __future__ import annotations

import json
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    FSInputFile,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaLivePhoto,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    PreCheckoutQuery,
    SuccessfulPayment,
    User,
)

from .catalog import build_empty_portfolio_hint, get_portfolio_previews
from .config import Config
from .db import Database
from .keyboards import (
    booking_contact_keyboard,
    chatgpt_entry_keyboard,
    chatgpt_ready_keyboard,
    contacts_keyboard,
    lead_notify_keyboard,
    main_keyboard,
    packs_keyboard,
    payment_link_keyboard,
    service_offers_keyboard,
)
from .openai_service import SketchBriefError, SketchGenerationError, TattooSketchService
from .payments import (
    find_pack,
    find_service_offer,
    pack_prices,
    service_offer_checkout_description,
    service_prices,
)
from .robokassa import ReceiptItem, build_payment_link, build_receipt
from .start_routes import extract_start_argument, resolve_start_action
from .texts import (
    booking_contact_prompt_text,
    booking_date_prompt_text,
    booking_fallback_contact,
    booking_intro_text,
    booking_placement_prompt_text,
    booking_size_prompt_text,
    booking_success_text,
    buy_text,
    chatgpt_fallback_text,
    chatgpt_prompt_intro_text,
    chatgpt_prompt_ready_text,
    generate_prompt_text,
    help_text,
    openai_not_ready_text,
    payment_menu_text,
    payment_support_text,
    portfolio_promo_text,
    price_text,
    service_payment_success_text,
    service_payments_unavailable_text,
    terms_text,
    welcome_text,
)


class SketchStates(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_chatgpt_prompt = State()
    waiting_for_booking_idea = State()
    waiting_for_booking_size = State()
    waiting_for_booking_placement = State()
    waiting_for_booking_date = State()
    waiting_for_booking_contact = State()


def build_router(cfg: Config, db: Database, sketch_service: TattooSketchService) -> Router:
    router = Router(name="likatattoo")

    def require_user(message: Message) -> User:
        user = message.from_user
        if user is None:
            raise RuntimeError("Telegram update does not include from_user.")
        return user

    def require_successful_payment(message: Message) -> SuccessfulPayment:
        payment = message.successful_payment
        if payment is None:
            raise RuntimeError("Successful payment payload is missing.")
        return payment

    async def notify_admin(message: str, bot_message: Message, *, reply_markup: object = None) -> None:
        if cfg.admin_chat_id:
            bot = bot_message.bot
            if bot is None:
                return
            try:
                await bot.send_message(
                    cfg.admin_chat_id,
                    message,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            except Exception:  # noqa: BLE001
                return

    async def notify_admin_photo(
        caption: str,
        image_bytes: bytes,
        filename: str,
        bot_message: Message,
    ) -> None:
        if cfg.admin_chat_id:
            bot = bot_message.bot
            if bot is None:
                return
            try:
                await bot.send_photo(
                    cfg.admin_chat_id,
                    photo=BufferedInputFile(image_bytes, filename=filename),
                    caption=caption,
                    parse_mode="HTML",
                )
            except Exception:  # noqa: BLE001
                return

    async def ensure_telegram_user(user: User | None) -> None:
        if user:
            await db.upsert_user(
                user_id=user.id,
                username=user.username,
                full_name=user.full_name,
                starter_credits=cfg.free_generations_on_start,
            )

    async def ensure_user(message: Message) -> None:
        await ensure_telegram_user(message.from_user)

    async def ensure_callback_user(callback: CallbackQuery) -> None:
        await ensure_telegram_user(callback.from_user)

    def payable_service_offers() -> tuple:
        return tuple(offer for offer in cfg.service_offers if offer.code != "portfolio")

    def contact_details(payment: SuccessfulPayment) -> str:
        order_info = getattr(payment, "order_info", None)
        if order_info is None:
            return ""
        lines: list[str] = []
        name = getattr(order_info, "name", None)
        phone_number = getattr(order_info, "phone_number", None)
        email = getattr(order_info, "email", None)
        if name:
            lines.append(f"Имя: {name}")
        if phone_number:
            lines.append(f"Телефон: {phone_number}")
        if email:
            lines.append(f"Email: {email}")
        return ("\n" + "\n".join(lines)) if lines else ""

    async def send_service_invoice(message: Message, offer_code: str) -> None:
        offer = find_service_offer(cfg, offer_code)
        if offer is None:
            await message.answer("Этот платежный сценарий не найден.", reply_markup=main_keyboard())
            return
        if offer.code == "portfolio":
            await message.answer(
                (
                    "Стоимость расходников для портфолио считается отдельно под каждую татуировку.\n\n"
                    "Пришли идею и референсы мастеру напрямую или оставь заявку в боте."
                ),
                reply_markup=contacts_keyboard(cfg),
            )
            return
        if not cfg.session_deposit_enabled:
            await message.answer(
                service_payments_unavailable_text(cfg),
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
            return
        await message.answer_invoice(
            title=offer.title,
            description=offer.description,
            payload=offer.payload,
            currency="RUB",
            prices=service_prices(offer),
            provider_token=cfg.payments_provider_token,
            need_name=True,
            need_phone_number=True,
            send_phone_number_to_provider=True,
            need_email=False,
            send_email_to_provider=False,
        )

    async def send_robokassa_payment_link(message: Message, offer_code: str) -> None:
        offer = find_service_offer(cfg, offer_code)
        if offer is None:
            await message.answer("Этот платежный сценарий не найден.", reply_markup=main_keyboard())
            return
        if offer.code == "portfolio":
            await message.answer(
                (
                    "Стоимость расходников для портфолио считается отдельно под каждую татуировку.\n\n"
                    "Пришли идею и референсы мастеру напрямую или оставь заявку в боте."
                ),
                reply_markup=contacts_keyboard(cfg),
            )
            return
        if not cfg.robokassa_enabled:
            await message.answer(
                service_payments_unavailable_text(cfg),
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
            return

        user = require_user(message)
        amount_text = f"{offer.amount_rub:.2f}"
        description = service_offer_checkout_description(offer)
        invoice_id = await db.create_robokassa_invoice_draft(
            user_id=user.id,
            offer_code=offer.code,
            offer_title=offer.title,
            description=description,
            amount_rub=offer.amount_rub,
            amount_text=amount_text,
        )
        receipt = build_receipt(
            items=[
                ReceiptItem(
                    name=description,
                    quantity=1,
                    sum_rub=amount_text,
                    payment_method="prepayment",
                    payment_object="service",
                    tax="none",
                )
            ]
        )
        payment_link = build_payment_link(
            cfg.robokassa,
            out_sum=amount_text,
            invoice_id=invoice_id,
            description=description,
            receipt=receipt,
            shp={
                "user_id": str(user.id),
                "offer_code": offer.code,
            },
        )
        await db.finalize_robokassa_invoice(
            invoice_id=invoice_id,
            receipt_json=receipt,
            payment_url=payment_link.url,
            signature_value=payment_link.signature,
            shp_json=json.dumps(
                {
                    key: value
                    for key, value in payment_link.params.items()
                    if key.startswith("Shp_")
                },
                ensure_ascii=False,
            ),
        )
        await message.answer(
            (
                f"<b>{offer.title}</b>\n\n"
                f"Сумма: <b>{offer.amount_rub} ₽</b>\n"
                f"Счет Robokassa: <code>{invoice_id}</code>\n\n"
                "Оплата откроется на защищенной странице Robokassa. "
                "После успешной оплаты бот и мастер получат подтверждение автоматически."
            ),
            parse_mode="HTML",
            reply_markup=payment_link_keyboard(payment_link.url),
        )
        await message.answer(
            "Если после оплаты что-то пойдет не так, напиши /paysupport и приложи номер счета.",
            reply_markup=main_keyboard(),
        )

    async def send_payment_menu(message: Message) -> None:
        offers = payable_service_offers()
        if not cfg.service_payments_enabled or not offers:
            await message.answer(
                service_payments_unavailable_text(cfg),
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
            return
        await message.answer(
            payment_menu_text(cfg),
            parse_mode="HTML",
            reply_markup=service_offers_keyboard(offers),
        )

    async def send_examples(message: Message) -> None:
        previews = get_portfolio_previews(cfg.portfolio_root)
        has_any = any(preview.files for preview in previews)
        if not has_any:
            await message.answer(
                build_empty_portfolio_hint(cfg.portfolio_root),
                parse_mode="HTML",
            )
            return

        for preview in previews:
            if not preview.files:
                continue
            media: list[
                InputMediaAudio
                | InputMediaDocument
                | InputMediaLivePhoto
                | InputMediaPhoto
                | InputMediaVideo
            ] = []
            for index, file_path in enumerate(preview.files):
                caption = (
                    f"<b>{preview.category.title}</b>"
                    if index == 0
                    else None
                )
                media.append(
                    InputMediaPhoto(
                        media=FSInputFile(file_path),
                        caption=caption,
                        parse_mode="HTML",
                    )
                )
            await message.answer_media_group(media=media)

    async def send_home(message: Message) -> None:
        await message.answer(
            welcome_text(cfg),
            reply_markup=main_keyboard(),
        )

    async def open_chatgpt_flow(message: Message, state: FSMContext) -> None:
        await ensure_user(message)
        await state.set_state(SketchStates.waiting_for_chatgpt_prompt)
        await message.answer(
            chatgpt_prompt_intro_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

    async def open_portfolio_flow(message: Message) -> None:
        await ensure_user(message)
        await message.answer(
            portfolio_promo_text(cfg),
            parse_mode="HTML",
            reply_markup=contacts_keyboard(cfg),
        )

    async def open_contacts_flow(message: Message) -> None:
        await message.answer(
            "Выбирай удобный способ связи:",
            reply_markup=contacts_keyboard(cfg),
        )

    async def send_myid(message: Message) -> None:
        user = require_user(message)
        setup_line = (
            "Сейчас <code>ADMIN_CHAT_ID</code> уже настроен. "
            "Если хочешь получать уведомления о заявках в другой чат, замени это значение в <code>bot/.env</code>."
            if cfg.admin_chat_id
            else "Сейчас <code>ADMIN_CHAT_ID</code> пустой. "
            "Скопируй число ниже и вставь его в <code>bot/.env</code> как <code>ADMIN_CHAT_ID</code>, "
            "чтобы бот присылал мастеру уведомления о новых заявках и оплатах."
        )
        await message.answer(
            (
                "<b>Твой Telegram ID</b>\n\n"
                f"<code>{user.id}</code>\n\n"
                f"{setup_line}"
            ),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

    async def open_booking_flow(message: Message, state: FSMContext, *, user: User | None = None) -> None:
        if user is not None:
            await ensure_telegram_user(user)
        else:
            await ensure_user(message)
        await state.set_state(SketchStates.waiting_for_booking_idea)
        await state.set_data({})
        await message.answer(
            booking_intro_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

    async def submit_booking_request(message: Message, state: FSMContext, contact_value: str) -> None:
        user = require_user(message)
        data = await state.get_data()
        request = await db.create_booking_request(
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            idea=str(data.get("booking_idea", "")).strip(),
            size=str(data.get("booking_size", "")).strip(),
            placement=str(data.get("booking_placement", "")).strip(),
            preferred_date=str(data.get("booking_date", "")).strip(),
            contact=contact_value.strip(),
        )
        await message.answer(
            booking_success_text(request.request_id),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )
        await notify_admin(
            (
                "<b>Новая заявка на запись</b>\n"
                f"Заявка: <b>#{request.request_id}</b>\n"
                f"Клиент: <a href=\"tg://user?id={user.id}\">{escape(user.full_name)}</a>\n"
                f"Username: {escape('@' + user.username) if user.username else 'не указан'}\n"
                f"Идея: {escape(str(data.get('booking_idea', '')))}\n"
                f"Размер: {escape(str(data.get('booking_size', '')))}\n"
                f"Зона: {escape(str(data.get('booking_placement', '')))}\n"
                f"Когда удобно: {escape(str(data.get('booking_date', '')))}\n"
                f"Контакт: {escape(contact_value)}"
            ),
            message,
            reply_markup=lead_notify_keyboard(request.request_id, user_id=user.id),
        )
        await state.clear()

    async def open_generate_flow(message: Message, state: FSMContext) -> None:
        await ensure_user(message)
        if not cfg.openai_key_ready:
            await message.answer(openai_not_ready_text(), reply_markup=main_keyboard())
            await message.answer(
                chatgpt_fallback_text(),
                reply_markup=chatgpt_entry_keyboard(cfg),
            )
            return

        user = require_user(message)
        balance = await db.get_balance(user.id)
        if balance <= 0:
            await message.answer(
                "На балансе нет генераций.\n\nСначала купи пакет через кнопку ниже.",
                reply_markup=packs_keyboard(cfg.generation_packs),
            )
            await message.answer(
                "Если не хочешь покупать пакет прямо сейчас, можно собрать prompt для ChatGPT и продолжить там.",
                reply_markup=chatgpt_entry_keyboard(cfg),
            )
            return

        await state.set_state(SketchStates.waiting_for_prompt)
        await message.answer(
            generate_prompt_text(balance),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

    async def dispatch_start_action(message: Message, state: FSMContext) -> None:
        action = resolve_start_action(extract_start_argument(message.text))
        if action == "booking":
            await open_booking_flow(message, state)
            return
        if action == "generate":
            await open_generate_flow(message, state)
            return
        if action == "chatgpt":
            await open_chatgpt_flow(message, state)
            return
        if action == "deposit":
            await send_payment_menu(message)
            return
        if action == "portfolio":
            await open_portfolio_flow(message)
            return
        if action == "examples":
            await send_examples(message)
            return
        if action == "contacts":
            await open_contacts_flow(message)
            return
        await send_home(message)

    @router.message(CommandStart())
    @router.message(F.text == "🏠 Главное меню")
    async def handle_start(message: Message, state: FSMContext) -> None:
        await ensure_user(message)
        await state.clear()
        await dispatch_start_action(message, state)

    @router.message(Command("help"))
    @router.message(F.text == "❓ Помощь")
    async def handle_help(message: Message) -> None:
        await message.answer(help_text(), reply_markup=main_keyboard())

    @router.message(Command("myid"))
    @router.message(Command("chatid"))
    async def handle_myid(message: Message) -> None:
        await send_myid(message)

    @router.message(Command("booking"))
    @router.message(F.text == "📝 Оставить заявку")
    async def handle_booking(message: Message, state: FSMContext) -> None:
        await open_booking_flow(message, state)

    @router.message(Command("paysupport"))
    @router.message(Command("support"))
    async def handle_payment_support(message: Message) -> None:
        await message.answer(
            payment_support_text(cfg),
            parse_mode="HTML",
            reply_markup=contacts_keyboard(cfg),
        )

    @router.message(Command("terms"))
    async def handle_terms(message: Message) -> None:
        await message.answer(
            terms_text(cfg),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

    @router.message(Command("chatgpt"))
    @router.message(F.text == "🧠 Prompt для ChatGPT")
    async def handle_chatgpt_start(message: Message, state: FSMContext) -> None:
        await open_chatgpt_flow(message, state)

    @router.message(Command("prices"))
    @router.message(F.text == "💰 Прайс")
    async def handle_prices(message: Message) -> None:
        await message.answer(price_text(cfg), reply_markup=main_keyboard(), parse_mode="HTML")

    @router.message(Command("portfolio"))
    @router.message(F.text == "🔥 Портфолио-акция")
    async def handle_portfolio(message: Message) -> None:
        await open_portfolio_flow(message)

    @router.message(Command("examples"))
    @router.message(F.text == "🖼 Примеры работ")
    async def handle_examples(message: Message) -> None:
        await send_examples(message)

    @router.message(Command("contacts"))
    @router.message(F.text == "📞 Связаться с мастером")
    async def handle_contacts(message: Message) -> None:
        await open_contacts_flow(message)

    @router.message(Command("leads"))
    async def handle_leads(message: Message) -> None:
        """\u041fоследние 10 заявок (только для админа)."""
        user = message.from_user
        if user is None or user.id != cfg.admin_chat_id:
            await message.answer("Эта команда доступна только мастеру.")
            return
        requests = await db.list_booking_requests(limit=10)
        counts = await db.count_booking_requests_by_status()
        total = sum(counts.values())
        if not requests:
            await message.answer("Заявок пока нет.", reply_markup=main_keyboard())
            return
        status_labels = {
            "new": "Новая", "contacted": "Связались",
            "consultation": "Консультация", "waiting_reply": "Ждём ответа",
            "confirmed": "Подтверждена", "deposit": "Предоплата",
            "done": "Сделано", "archive": "Архив",
        }
        lines = [f"<b>Заявки ({total} всего)</b>"]
        for req in requests:
            name = req.full_name or req.username or f"user {req.user_id}"
            slabel = status_labels.get(req.status, req.status)
            lines.append(
                f"\n<b>#{req.request_id}</b> • {escape(slabel)}\n"
                f"👤 {escape(name)}\n"
                f"💡 {escape(req.idea[:60])}{'...' if len(req.idea) > 60 else ''}\n"
                f"📞 {escape(req.contact)}\n"
                f"📅 {req.created_at[:10]}"
            )
        await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=main_keyboard())

    @router.message(Command("payments"))
    async def handle_payments(message: Message) -> None:
        """\u041fоследние 10 платежей (только для админа)."""
        user = message.from_user
        if user is None or user.id != cfg.admin_chat_id:
            await message.answer("Эта команда доступна только мастеру.")
            return
        payments = await db.list_payments_for_crm(limit=10)
        if not payments:
            await message.answer("Платежей пока нет.", reply_markup=main_keyboard())
            return
        total_paid = sum(p.amount_rub for p in payments if p.status == "paid")
        channel_labels = {"robokassa": "Robokassa", "telegram-stars": "Telegram Stars"}
        lines = [f"<b>Платежи</b> (сумма оплаченных: <b>{total_paid:,} ₽</b>)"]
        for p in payments:
            ch = channel_labels.get(p.channel, p.channel)
            status_icon = "✅" if p.status == "paid" else ("⏳" if p.status == "created" else "❌")
            lines.append(
                f"\n{status_icon} <b>{p.amount_rub:,} ₽</b> • {escape(p.offer_title)}\n"
                f"💳 {ch} • #{p.payment_id}\n"
                f"📅 {p.paid_at[:10] if p.paid_at else p.created_at[:10]}"
            )
        await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=main_keyboard())

    @router.callback_query(F.data.startswith("lead_status:"))
    async def handle_lead_status_callback(callback: CallbackQuery) -> None:
        """\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0430 inline-\u043a\u043d\u043e\u043f\u043e\u043a \u0441\u043c\u0435\u043d\u044b \u0441\u0442\u0430\u0442\u0443\u0441\u0430 \u0437\u0430\u044f\u0432\u043a\u0438."""
        callback_data = callback.data or ""
        parts = callback_data.split(":")
        if len(parts) != 3:
            await callback.answer("Неверный формат команды.", show_alert=True)
            return
        try:
            request_id = int(parts[1])
        except ValueError:
            await callback.answer("Неверный ID заявки.", show_alert=True)
            return
        new_status = parts[2]
        updated = await db.update_booking_request_status(request_id, new_status)
        status_labels = {
            "contacted": "Связались", "deposit": "Предоплата",
            "archive": "Архив", "done": "Сделано",
        }
        if updated:
            label = status_labels.get(new_status, new_status)
            await callback.answer(f"Статус заявки #{request_id} → {label}", show_alert=False)
            if isinstance(callback.message, Message):
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:  # noqa: BLE001
                    pass
        else:
            await callback.answer(f"Заявка #{request_id} не найдена.", show_alert=True)

    @router.message(Command("balance"))
    @router.message(F.text == "👛 Мой баланс")
    async def handle_balance(message: Message) -> None:
        await ensure_user(message)
        user = require_user(message)
        balance = await db.get_balance(user.id)
        await message.answer(
            f"На балансе сейчас <b>{balance}</b> генераций.",
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

    @router.message(Command("buy"))
    @router.message(F.text == "🛒 Купить генерации")
    async def handle_buy(message: Message) -> None:
        await ensure_user(message)
        await message.answer(
            buy_text(cfg),
            parse_mode="HTML",
            reply_markup=packs_keyboard(cfg.generation_packs),
        )

    @router.callback_query(F.data.startswith("buy:"))
    async def handle_buy_callback(callback: CallbackQuery) -> None:
        callback_data = callback.data
        callback_message = callback.message
        if callback_data is None or not isinstance(callback_message, Message):
            await callback.answer("Не удалось обработать кнопку. Попробуй еще раз.", show_alert=True)
            return

        pack_code = callback_data.split(":", 1)[1]
        pack = find_pack(cfg, pack_code)
        if not pack:
            await callback.answer("Пакет не найден.", show_alert=True)
            return

        await callback_message.answer_invoice(
            title=f"Lika Tattoo • {pack.title}",
            description=f"Пакет генераций эскизов: {pack.credits} шт.",
            payload=pack.payload,
            currency="XTR",
            prices=pack_prices(pack),
            provider_token="",
        )
        await callback.answer()

    @router.callback_query(F.data == "mode:chatgpt")
    async def handle_chatgpt_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await ensure_callback_user(callback)
        await state.set_state(SketchStates.waiting_for_chatgpt_prompt)
        if isinstance(callback.message, Message):
            await callback.message.answer(
                chatgpt_prompt_intro_text(),
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
        await callback.answer()

    @router.callback_query(F.data == "flow:booking")
    async def handle_booking_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await ensure_callback_user(callback)
        if isinstance(callback.message, Message):
            await open_booking_flow(callback.message, state, user=callback.from_user)
        await callback.answer()

    @router.message(Command("deposit"))
    @router.message(F.text == "💳 Оплата и бронь")
    @router.message(F.text == "💳 Предоплата сеанса")
    async def handle_deposit(message: Message) -> None:
        await ensure_user(message)
        await send_payment_menu(message)

    @router.callback_query(F.data.startswith("payservice:"))
    async def handle_service_payment_callback(callback: CallbackQuery) -> None:
        callback_data = callback.data
        callback_message = callback.message
        if callback_data is None or not isinstance(callback_message, Message):
            await callback.answer("Не удалось открыть оплату. Попробуй еще раз.", show_alert=True)
            return
        offer_code = callback_data.split(":", 1)[1]
        offer = find_service_offer(cfg, offer_code)
        if offer is None:
            await callback.answer("Этот вариант оплаты не найден.", show_alert=True)
            return
        if offer.code == "portfolio":
            await callback.answer("Для портфолио фиксированной цены нет.", show_alert=True)
            await callback_message.answer(
                (
                    "Стоимость расходников для портфолио считается отдельно под каждую татуировку.\n\n"
                    "Пришли идею и референсы мастеру напрямую или оставь заявку в боте."
                ),
                reply_markup=contacts_keyboard(cfg),
            )
            return
        if cfg.session_deposit_enabled:
            await send_service_invoice(callback_message, offer.code)
            await callback.answer()
            return
        if cfg.robokassa_enabled:
            await send_robokassa_payment_link(callback_message, offer.code)
            await callback.answer()
            return
        if not cfg.service_payments_enabled:
            await callback.answer("Платежный провайдер еще не подключен.", show_alert=True)
            await callback_message.answer(
                service_payments_unavailable_text(cfg),
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
            return

    @router.pre_checkout_query()
    async def handle_pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
        payload = pre_checkout_query.invoice_payload
        is_pack = payload.startswith("pack:")
        is_service_offer = payload.startswith("service:")
        await pre_checkout_query.answer(ok=is_pack or is_service_offer)

    @router.message(F.successful_payment)
    async def handle_successful_payment(message: Message) -> None:
        await ensure_user(message)
        user = require_user(message)
        payment = require_successful_payment(message)
        payload = payment.invoice_payload
        telegram_charge_id = getattr(payment, "telegram_payment_charge_id", None)
        provider_charge_id = getattr(payment, "provider_payment_charge_id", None)

        if payload.startswith("pack:"):
            pack = find_pack(cfg, payload.split(":", 1)[1])
            if not pack:
                await message.answer("Оплата прошла, но пакет не найден. Напиши администратору.")
                return

            pack_result = await db.apply_pack_payment(
                user_id=user.id,
                payload=payload,
                amount=payment.total_amount,
                currency=payment.currency,
                credits_added=pack.credits,
                provider_charge_id=provider_charge_id,
                telegram_charge_id=telegram_charge_id,
                raw=payment.model_dump(mode="json"),
            )
            if not pack_result.applied:
                await message.answer(
                    "Эта оплата уже была обработана раньше. Баланс оставлен без повторного пополнения.\n\n"
                    f"Сейчас на балансе: <b>{pack_result.balance}</b>.",
                    parse_mode="HTML",
                    reply_markup=main_keyboard(),
                )
                return
            await message.answer(
                f"Оплата принята.\n\nБаланс пополнен на <b>{pack.credits}</b> генераций.\n"
                f"Сейчас на балансе: <b>{pack_result.balance}</b>.",
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
            await notify_admin(
                f"Новая покупка генераций\nПользователь: {user.id}\nПакет: {pack.title}\nБаланс: {pack_result.balance}",
                message,
            )
            return

        if payload.startswith("service:"):
            offer = find_service_offer(cfg, payload.split(":", 1)[1])
            if offer is None:
                await message.answer("Оплата прошла, но платежный сценарий не найден. Напиши мастеру.")
                return
            deposit_result = await db.record_deposit_payment(
                user_id=user.id,
                payload=payload,
                offer_code=offer.code,
                offer_title=offer.title,
                amount=payment.total_amount,
                currency=payment.currency,
                amount_rub=offer.amount_rub,
                status="paid",
                telegram_charge_id=telegram_charge_id,
                provider_charge_id=provider_charge_id,
                raw=payment.model_dump(mode="json"),
            )
            if not deposit_result.applied:
                await message.answer(
                    "Эта предоплата уже была обработана раньше. Повторно ничего не списываем.",
                    reply_markup=main_keyboard(),
                )
                return
            await message.answer(
                service_payment_success_text(offer.code),
                reply_markup=main_keyboard(),
            )
            await notify_admin(
                f"Новая сервисная оплата\n"
                f"Пользователь: {user.id} ({user.full_name})\n"
                f"Сценарий: {offer.title}\n"
                f"Сумма: {offer.amount_rub} ₽"
                f"{contact_details(payment)}",
                message,
            )
            await message.answer(
                "Если потребуется помощь по платежу или подтверждению, напиши /paysupport.",
                reply_markup=main_keyboard(),
            )

    @router.message(Command("generate"))
    @router.message(F.text == "🎨 Сгенерировать эскиз")
    async def handle_generate_start(message: Message, state: FSMContext) -> None:
        await open_generate_flow(message, state)

    @router.message(Command("cancel"))
    async def handle_cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Текущий шаг отменен.", reply_markup=main_keyboard())

    @router.message(SketchStates.waiting_for_booking_idea, F.text)
    async def handle_booking_idea(message: Message, state: FSMContext) -> None:
        idea = (message.text or "").strip()
        if not idea:
            await message.answer(
                "Идея получилась пустой. Напиши, что хочешь сделать, одним сообщением.",
                reply_markup=main_keyboard(),
            )
            return
        await state.update_data(booking_idea=idea)
        await state.set_state(SketchStates.waiting_for_booking_size)
        await message.answer(
            booking_size_prompt_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

    @router.message(SketchStates.waiting_for_booking_size, F.text)
    async def handle_booking_size(message: Message, state: FSMContext) -> None:
        size = (message.text or "").strip()
        if not size:
            await message.answer(
                "Размер не распознался. Напиши его текстом, например: 5 см или 8-10 см.",
                reply_markup=main_keyboard(),
            )
            return
        await state.update_data(booking_size=size)
        await state.set_state(SketchStates.waiting_for_booking_placement)
        await message.answer(
            booking_placement_prompt_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

    @router.message(SketchStates.waiting_for_booking_placement, F.text)
    async def handle_booking_placement(message: Message, state: FSMContext) -> None:
        placement = (message.text or "").strip()
        if not placement:
            await message.answer(
                "Напиши зону текстом: например предплечье, ключица или ребра.",
                reply_markup=main_keyboard(),
            )
            return
        await state.update_data(booking_placement=placement)
        await state.set_state(SketchStates.waiting_for_booking_date)
        await message.answer(
            booking_date_prompt_text(),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

    @router.message(SketchStates.waiting_for_booking_date, F.text)
    async def handle_booking_date(message: Message, state: FSMContext) -> None:
        preferred_date = (message.text or "").strip()
        if not preferred_date:
            await message.answer(
                "Напиши, когда примерно удобно, даже если без точной даты.",
                reply_markup=main_keyboard(),
            )
            return
        await state.update_data(booking_date=preferred_date)
        await state.set_state(SketchStates.waiting_for_booking_contact)
        await message.answer(
            booking_contact_prompt_text(),
            parse_mode="HTML",
            reply_markup=booking_contact_keyboard(),
        )

    @router.message(SketchStates.waiting_for_booking_contact, F.contact)
    async def handle_booking_contact_shared(message: Message, state: FSMContext) -> None:
        if message.contact is None:
            await message.answer(
                "Не удалось прочитать контакт. Попробуй еще раз кнопкой или напиши его вручную.",
                reply_markup=booking_contact_keyboard(),
            )
            return
        await submit_booking_request(message, state, message.contact.phone_number)

    @router.message(SketchStates.waiting_for_booking_contact, F.text)
    async def handle_booking_contact_text(message: Message, state: FSMContext) -> None:
        user = require_user(message)
        text = (message.text or "").strip()
        if not text:
            await message.answer(
                "Напиши контакт вручную или используй кнопку отправки номера.",
                reply_markup=booking_contact_keyboard(),
            )
            return
        if text.lower() == "пропустить":
            text = booking_fallback_contact(user.username, user.id)
        await submit_booking_request(message, state, text)

    @router.message(SketchStates.waiting_for_chatgpt_prompt, F.text)
    async def handle_chatgpt_prompt(message: Message, state: FSMContext) -> None:
        await ensure_user(message)
        brief = (message.text or "").strip()
        if not brief:
            await message.answer(
                "Описание получилось пустым. Пришли идею одним сообщением: объект, стиль, настроение, цвет, место.",
                reply_markup=main_keyboard(),
            )
            return

        try:
            prompt = sketch_service.build_chatgpt_prompt(brief)
        except SketchBriefError as error:
            await message.answer(
                f"С таким описанием пока не могу собрать prompt: <b>{error}</b>\n\n"
                "Попробуй короче и конкретнее: объект, стиль, цвет, детали, место нанесения.",
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
            return

        await message.answer(
            chatgpt_prompt_ready_text(prompt),
            parse_mode="HTML",
            reply_markup=chatgpt_ready_keyboard(cfg),
        )
        await state.clear()

    @router.message(SketchStates.waiting_for_prompt, F.text)
    async def handle_generate_prompt(message: Message, state: FSMContext) -> None:
        await ensure_user(message)
        user = require_user(message)
        brief = (message.text or "").strip()
        if not brief:
            await message.answer(
                "Описание получилось пустым. Пришли идею одним сообщением: стиль, объект, настроение, цвет, место.",
                reply_markup=main_keyboard(),
            )
            return
        balance = await db.get_balance(user.id)
        if balance <= 0:
            await state.clear()
            await message.answer(
                "Баланс генераций закончился. Купи новый пакет, и можно продолжать.",
                reply_markup=packs_keyboard(cfg.generation_packs),
            )
            return

        status_message = await message.answer("Генерирую эскиз, это может занять до минуты...")
        try:
            result = await sketch_service.generate(user.id, brief)
            balance_after = await db.consume_credit(user.id)
            await db.log_generation(
                user_id=user.id,
                user_prompt=brief,
                final_prompt=result.final_prompt,
                image_path=result.image_path,
                model=result.model,
            )

            image_bytes = result.image_path.read_bytes()
            await message.answer_photo(
                photo=BufferedInputFile(image_bytes, filename=result.image_path.name),
                caption=(
                    "Эскиз готов.\n\n"
                    f"Осталось генераций: <b>{balance_after}</b>\n"
                    "Если хочешь еще вариант, снова нажми «Сгенерировать эскиз»."
                ),
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
            await notify_admin_photo(
                (
                    "Новая генерация эскиза\n"
                    f"Пользователь: <a href=\"tg://user?id={user.id}\">{escape(user.full_name)}</a>\n"
                    f"Username: {escape('@' + user.username) if user.username else 'не указан'}\n"
                    f"Запрос: {escape(brief)}"
                ),
                image_bytes,
                result.image_path.name,
                message,
            )
        except SketchBriefError as error:
            await message.answer(
                f"С эскизом пока не могу помочь: <b>{error}</b>\n\n"
                "Попробуй короче и конкретнее: объект, стиль, цвет, детали, место нанесения.",
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
        except SketchGenerationError as error:
            detail = str(error)
            if "billing hard limit" in detail.lower():
                await message.answer(
                    "Встроенная генерация через API сейчас временно недоступна из-за лимита биллинга OpenAI.\n\n"
                    "Ниже есть обходной сценарий через обычный ChatGPT.",
                    reply_markup=main_keyboard(),
                )
            else:
                await message.answer(
                    "OpenAI отклонил запрос на генерацию.\n\n"
                    f"Причина: <code>{error}</code>",
                    parse_mode="HTML",
                    reply_markup=main_keyboard(),
                )
            await message.answer(
                chatgpt_fallback_text(),
                reply_markup=chatgpt_entry_keyboard(cfg),
            )
        except Exception as error:  # noqa: BLE001
            await message.answer(
                "Не удалось сгенерировать эскиз. Проверь OpenAI API key и попробуй еще раз.\n\n"
                f"Техническая ошибка: <code>{type(error).__name__}</code>",
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
            await message.answer(
                chatgpt_fallback_text(),
                reply_markup=chatgpt_entry_keyboard(cfg),
            )
        finally:
            try:
                await status_message.delete()
            except Exception:  # noqa: BLE001
                pass
            await state.clear()

    @router.message()
    async def handle_fallback(message: Message) -> None:
        await message.answer(
            "Не понял команду. Нажми кнопку в меню или отправь /help.",
            reply_markup=main_keyboard(),
        )

    return router
