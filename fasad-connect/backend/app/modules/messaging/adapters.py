from __future__ import annotations

from app.modules.messaging.schemas import (
    EmailPayload,
    GenericWebhookPayload,
    TelegramPayload,
    UnifiedAttachmentIn,
    UnifiedLeadIn,
    UnifiedSenderIn,
    WhatsAppPayload,
)


def normalize_email_payload(payload: EmailPayload) -> UnifiedLeadIn:
    return UnifiedLeadIn(
        source_channel="email",
        external_message_id=payload.message_id,
        subject=payload.subject,
        text=payload.body_text,
        sender=UnifiedSenderIn(
            full_name=payload.from_name,
            phone=payload.from_phone,
            email=payload.from_email,
        ),
        attachments=[
            UnifiedAttachmentIn(
                file_name=item.file_name,
                mime_type=item.mime_type,
                size_bytes=item.size_bytes,
                content_base64=item.content_base64,
            )
            for item in payload.attachments
        ],
        raw_payload=payload.raw_payload or payload.model_dump(mode="json"),
    )


def normalize_telegram_payload(payload: TelegramPayload) -> UnifiedLeadIn:
    message = payload.message or {}
    sender = message.get("from", {})
    file_attachments: list[UnifiedAttachmentIn] = []
    if message.get("photo"):
        file_attachments.append(
            UnifiedAttachmentIn(
                file_name=f"telegram-photo-{payload.update_id}.txt",
                mime_type="text/plain",
                size_bytes=0,
                external_url="telegram://photo/stub",
            )
        )
    if message.get("document"):
        file_attachments.append(
            UnifiedAttachmentIn(
                file_name=message["document"].get(
                    "file_name", f"telegram-doc-{payload.update_id}.bin"
                ),
                mime_type=message["document"].get("mime_type"),
                size_bytes=message["document"].get("file_size", 0),
                external_url="telegram://document/stub",
            )
        )
    full_name = " ".join(filter(None, [sender.get("first_name"), sender.get("last_name")])).strip()
    return UnifiedLeadIn(
        source_channel="telegram",
        external_message_id=str(message.get("message_id") or payload.update_id or ""),
        subject=None,
        text=message.get("text") or message.get("caption") or "",
        sender=UnifiedSenderIn(
            full_name=full_name or None, external_id=str(sender.get("id") or "")
        ),
        attachments=file_attachments,
        raw_payload=payload.model_dump(mode="json"),
    )


def normalize_whatsapp_payload(payload: WhatsAppPayload) -> UnifiedLeadIn:
    entry = payload.entry[0] if payload.entry else {}
    changes = entry.get("changes", [])
    value = changes[0].get("value", {}) if changes else {}
    messages = value.get("messages", [])
    contacts = value.get("contacts", [])
    message = messages[0] if messages else {}
    contact = contacts[0] if contacts else {}
    body = message.get("text", {}).get("body", "")
    attachments: list[UnifiedAttachmentIn] = []
    if message.get("image") or message.get("document"):
        attachments.append(
            UnifiedAttachmentIn(
                file_name=f"whatsapp-media-{message.get('id', 'unknown')}.txt",
                mime_type="text/plain",
                size_bytes=0,
                external_url="whatsapp://media/stub",
            )
        )
    return UnifiedLeadIn(
        source_channel="whatsapp",
        external_message_id=message.get("id"),
        text=body,
        sender=UnifiedSenderIn(
            full_name=contact.get("profile", {}).get("name"),
            phone=contact.get("wa_id"),
            external_id=contact.get("wa_id"),
        ),
        attachments=attachments,
        raw_payload=payload.raw_payload or payload.model_dump(mode="json"),
    )


def normalize_generic_payload(payload: GenericWebhookPayload) -> UnifiedLeadIn:
    return UnifiedLeadIn(
        source_channel="webhook",
        external_message_id=payload.external_message_id,
        subject=payload.subject,
        text=payload.text,
        sender=UnifiedSenderIn(
            full_name=payload.sender_name,
            phone=payload.sender_phone,
            email=payload.sender_email,
        ),
        attachments=payload.attachments,
        raw_payload=payload.raw_payload or payload.model_dump(mode="json"),
    )
