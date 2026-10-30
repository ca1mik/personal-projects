from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.leads.models import Lead
from app.modules.leads.service import LeadService
from app.modules.messaging.adapters import (
    normalize_email_payload,
    normalize_generic_payload,
    normalize_telegram_payload,
    normalize_whatsapp_payload,
)
from app.modules.messaging.inbox_service import InboxService
from app.modules.messaging.models import TelegramBotSession
from app.modules.messaging.schemas import (
    EmailPayload,
    GenericWebhookPayload,
    TelegramBotMenuButton,
    TelegramBotReply,
    TelegramBotWebhookResult,
    TelegramPayload,
    UnifiedLeadIn,
    WhatsAppPayload,
)
from app.modules.templates.catalog import CATALOG_PRODUCTS, get_catalog_definition
from app.modules.templates.schemas import CatalogEstimateRequest, CatalogLeadCreateRequest
from app.modules.templates.service import TemplateService

INT_RE = re.compile(r"^\d{2,5}$")


class MessagingService:
    @staticmethod
    def _intake_and_record(
        db: Session,
        payload: UnifiedLeadIn,
        acting_user_id: str | None = None,
    ) -> Lead:
        lead = LeadService.intake_lead(db, payload, acting_user_id)
        InboxService.record_inbound_lead(db, payload, lead, acting_user_id)
        return lead

    @staticmethod
    def intake_unified(
        db: Session, payload: UnifiedLeadIn, acting_user_id: str | None = None
    ) -> Lead:
        return MessagingService._intake_and_record(db, payload, acting_user_id)

    @staticmethod
    def intake_email(db: Session, payload: EmailPayload) -> Lead:
        return MessagingService._intake_and_record(db, normalize_email_payload(payload))

    @staticmethod
    def intake_telegram(db: Session, payload: TelegramPayload) -> Lead:
        return MessagingService._intake_and_record(db, normalize_telegram_payload(payload))

    @staticmethod
    def intake_whatsapp(db: Session, payload: WhatsAppPayload) -> Lead:
        return MessagingService._intake_and_record(db, normalize_whatsapp_payload(payload))

    @staticmethod
    def intake_generic_webhook(db: Session, payload: GenericWebhookPayload) -> Lead:
        return MessagingService._intake_and_record(db, normalize_generic_payload(payload))

    @staticmethod
    def _get_telegram_session(
        db: Session,
        chat_id: str,
        telegram_user_id: str | None,
    ) -> TelegramBotSession:
        session = db.scalar(select(TelegramBotSession).where(TelegramBotSession.chat_id == chat_id))
        if session:
            if telegram_user_id:
                session.telegram_user_id = telegram_user_id
            return session

        session = TelegramBotSession(
            chat_id=chat_id,
            telegram_user_id=telegram_user_id,
            current_step="choose_product",
            collected_data_json={},
        )
        db.add(session)
        db.flush()
        return session

    @staticmethod
    def _product_buttons() -> list[list[TelegramBotMenuButton]]:
        return [
            [TelegramBotMenuButton(text=item.bot_menu_label, callback_data=f"product:{item.code}")]
            for item in CATALOG_PRODUCTS
        ]

    @staticmethod
    def _material_buttons(product_code: str, db: Session) -> list[list[TelegramBotMenuButton]]:
        catalog_items = {item.code: item for item in TemplateService.list_catalog(db)}
        item = catalog_items.get(product_code)
        if item is None:
            return []
        return [
            [
                TelegramBotMenuButton(
                    text=material.name,
                    callback_data=f"material:{material.code}",
                )
            ]
            for material in item.available_materials
        ]

    @staticmethod
    def _reply(
        text: str,
        session_state: str,
        *,
        buttons: list[list[TelegramBotMenuButton]] | None = None,
        lead_id: str | None = None,
        estimated_total: Decimal | None = None,
        estimated_area_sqm: Decimal | None = None,
    ) -> TelegramBotWebhookResult:
        return TelegramBotWebhookResult(
            reply=TelegramBotReply(
                text=text,
                session_state=session_state,
                buttons=buttons or [],
                lead_id=lead_id,
                estimated_total=str(estimated_total) if estimated_total is not None else None,
                estimated_area_sqm=(
                    str(estimated_area_sqm) if estimated_area_sqm is not None else None
                ),
            )
        )

    @staticmethod
    def _reset_session(session: TelegramBotSession) -> None:
        session.current_step = "choose_product"
        session.selected_product_code = None
        session.collected_data_json = {}
        session.last_message_id = None

    @staticmethod
    def _extract_telegram_context(
        payload: TelegramPayload,
    ) -> tuple[str, str | None, str | None, str | None, str | None, str | None]:
        callback = payload.callback_query or {}
        if callback:
            message = callback.get("message", {})
            chat = message.get("chat", {})
            sender = callback.get("from", {})
            text = callback.get("data")
            phone = callback.get("contact", {}).get("phone_number")
            full_name = " ".join(
                filter(None, [sender.get("first_name"), sender.get("last_name")])
            ).strip()
            return (
                str(chat.get("id") or sender.get("id") or "telegram-demo"),
                str(sender.get("id") or "") or None,
                text,
                None,
                phone,
                full_name or None,
            )

        message = payload.message or {}
        chat = message.get("chat", {})
        sender = message.get("from", {})
        contact = message.get("contact", {})
        full_name = " ".join(
            filter(None, [sender.get("first_name"), sender.get("last_name")])
        ).strip()
        return (
            str(chat.get("id") or sender.get("id") or "telegram-demo"),
            str(sender.get("id") or "") or None,
            message.get("text") or message.get("caption"),
            str(message.get("message_id") or payload.update_id or "") or None,
            contact.get("phone_number"),
            full_name or None,
        )

    @staticmethod
    def _parse_size_value(text: str | None) -> int | None:
        if not text:
            return None
        normalized = text.strip()
        if not INT_RE.match(normalized):
            return None
        return int(normalized)

    @staticmethod
    def handle_telegram_bot_webhook(
        db: Session,
        payload: TelegramPayload,
    ) -> TelegramBotWebhookResult:
        chat_id, telegram_user_id, text, message_id, contact_phone, sender_name = (
            MessagingService._extract_telegram_context(payload)
        )
        session = MessagingService._get_telegram_session(db, chat_id, telegram_user_id)
        session.last_message_id = message_id
        text = (text or "").strip()

        if text in {"/start", "/menu", "menu"}:
            MessagingService._reset_session(session)
            db.commit()
            return MessagingService._reply(
                "Выберите изделие для примерного расчёта. Бот соберёт размеры, материал и создаст заявку в CRM.",
                session.current_step,
                buttons=MessagingService._product_buttons(),
            )

        if text in {"/cancel", "cancel"}:
            MessagingService._reset_session(session)
            db.commit()
            return MessagingService._reply(
                "Текущий сценарий сброшен. Можно выбрать новый тип изделия.",
                session.current_step,
                buttons=MessagingService._product_buttons(),
            )

        if text.startswith("product:"):
            product_code = text.split(":", 1)[1]
            product = get_catalog_definition(product_code)
            if product is None:
                raise AppError("Unknown catalog product in Telegram bot flow")
            session.selected_product_code = product_code
            session.current_step = "await_width"
            session.collected_data_json = {}
            db.commit()
            return MessagingService._reply(
                f"Вы выбрали: {product.name}. {product.bot_questions[0]}",
                session.current_step,
            )

        if not session.selected_product_code:
            db.commit()
            return MessagingService._reply(
                "Сначала выберите изделие из меню.",
                session.current_step,
                buttons=MessagingService._product_buttons(),
            )

        product = get_catalog_definition(session.selected_product_code)
        if product is None:
            raise AppError("Catalog product is missing")

        collected = dict(session.collected_data_json or {})

        if session.current_step == "await_width":
            width = MessagingService._parse_size_value(text)
            if width is None:
                raise AppError("Введите ширину числом в миллиметрах, например 1200")
            collected["width"] = width
            session.collected_data_json = collected
            session.current_step = "await_height"
            db.commit()
            return MessagingService._reply(product.bot_questions[1], session.current_step)

        if session.current_step == "await_height":
            height = MessagingService._parse_size_value(text)
            if height is None:
                raise AppError("Введите высоту числом в миллиметрах, например 2400")
            collected["height"] = height
            session.collected_data_json = collected
            session.current_step = "await_depth"
            db.commit()
            return MessagingService._reply(product.bot_questions[2], session.current_step)

        if session.current_step == "await_depth":
            depth = MessagingService._parse_size_value(text)
            if depth is None:
                raise AppError("Введите глубину числом в миллиметрах, например 600")
            collected["depth"] = depth
            session.collected_data_json = collected
            session.current_step = "await_material"
            db.commit()
            return MessagingService._reply(
                product.bot_questions[3],
                session.current_step,
                buttons=MessagingService._material_buttons(product.code, db),
            )

        if session.current_step == "await_material":
            if not text.startswith("material:"):
                raise AppError("Выберите материал кнопкой из меню Telegram")
            material_code = text.split(":", 1)[1]
            collected["material_code"] = material_code
            estimate = TemplateService.calculate_catalog_estimate(
                db,
                CatalogEstimateRequest(
                    product_code=product.code,
                    width=int(collected["width"]),
                    height=int(collected["height"]),
                    depth=int(collected["depth"]),
                    quantity=1,
                    material_code=material_code,
                ),
            )
            collected["estimate_total"] = str(estimate.final_amount)
            collected["estimate_area_sqm"] = str(estimate.area_sqm)
            session.collected_data_json = collected
            session.current_step = "await_name"
            db.commit()
            return MessagingService._reply(
                (
                    f"Предварительная оценка: {estimate.final_amount} {estimate.currency}.\n"
                    f"Площадь фасада/проёма: {estimate.area_sqm} м2.\n"
                    f"{product.bot_questions[4]}"
                ),
                session.current_step,
                estimated_total=estimate.final_amount,
                estimated_area_sqm=estimate.area_sqm,
            )

        if session.current_step == "await_name":
            if len(text) < 2:
                raise AppError("Укажите имя клиента")
            collected["client_name"] = text
            session.collected_data_json = collected
            session.current_step = "await_phone"
            db.commit()
            return MessagingService._reply(product.bot_questions[5], session.current_step)

        if session.current_step == "await_phone":
            phone = contact_phone or text
            if len(re.sub(r"\D", "", phone or "")) < 10:
                raise AppError("Укажите телефон в формате +79990001122")
            lead, estimate = TemplateService.create_catalog_lead(
                db,
                CatalogLeadCreateRequest(
                    product_code=product.code,
                    width=int(collected["width"]),
                    height=int(collected["height"]),
                    depth=int(collected["depth"]),
                    quantity=1,
                    material_code=str(collected["material_code"]),
                    client_name=str(collected["client_name"]),
                    phone=phone,
                    source_channel="telegram_bot",
                    comment=(
                        f"Telegram bot chat {chat_id}, telegram user {telegram_user_id}, sender {sender_name}"
                    ),
                ),
            )
            MessagingService._reset_session(session)
            db.commit()
            return MessagingService._reply(
                (
                    f"Заявка создана в CRM.\n"
                    f"Lead ID: {lead.id}\n"
                    f"Оценка: {estimate.final_amount} {estimate.currency}\n"
                    f"Менеджер свяжется с вами для уточнений."
                ),
                session.current_step,
                buttons=MessagingService._product_buttons(),
                lead_id=str(lead.id),
                estimated_total=estimate.final_amount,
                estimated_area_sqm=estimate.area_sqm,
            )

        db.commit()
        return MessagingService._reply(
            "Не удалось распознать текущий шаг. Нажмите /start для нового расчёта.",
            session.current_step,
            buttons=MessagingService._product_buttons(),
        )
