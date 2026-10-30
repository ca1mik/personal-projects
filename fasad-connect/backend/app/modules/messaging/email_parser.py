"""RFC 822 message -> :class:`EmailPayload`.

Deliberately built on the stdlib ``email`` package rather than on the IMAP
client, so parsing can be tested against raw bytes with no network or library
mocking. ``email_transport`` hands raw bytes here.
"""

from __future__ import annotations

import base64
import re
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser

from app.modules.messaging.schemas import EmailAttachmentPayload, EmailPayload

BLOCK_LEVEL_TAGS = {
    "address",
    "article",
    "blockquote",
    "br",
    "div",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "p",
    "pre",
    "section",
    "table",
    "tr",
}
SKIPPED_CONTENT_TAGS = {"script", "style", "head", "title"}
WHITESPACE_RUN_RE = re.compile(r"[ \t\r\f\v]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")
EMAIL_LOCAL_PART_RE = re.compile(r"[^@]+")
PLAUSIBLE_ADDRESS_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class _HtmlToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIPPED_CONTENT_TAGS:
            self._skip_depth += 1
        elif tag in BLOCK_LEVEL_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED_CONTENT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in BLOCK_LEVEL_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def html_to_text(html: str) -> str:
    parser = _HtmlToText()
    parser.feed(html)
    parser.close()
    text = parser.get_text()
    text = WHITESPACE_RUN_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return BLANK_LINES_RE.sub("\n\n", text).strip()


def decode_mime_header(raw: str | None) -> str:
    """Decode RFC 2047 encoded-words (``=?utf-8?B?...?=``) into plain text."""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except (UnicodeDecodeError, LookupError, ValueError):
        return raw.strip()


def _decode_part_payload(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _is_attachment(part: Message) -> bool:
    disposition = (part.get_content_disposition() or "").lower()
    if disposition == "attachment":
        return True
    # Inline parts still count as attachments when they carry a filename
    # (embedded photos of a sketch are exactly what clients send).
    return disposition == "inline" and bool(part.get_filename())


def _attachment_file_name(part: Message, index: int) -> str:
    raw_name = part.get_filename()
    name = decode_mime_header(raw_name) if raw_name else ""
    if not name:
        extension = (part.get_content_subtype() or "bin").split("+")[0]
        name = f"attachment-{index}.{extension}"
    # Strip any path component a malicious sender may have injected.
    return name.replace("\\", "/").split("/")[-1].strip() or f"attachment-{index}.bin"


def _extract_sender(message: Message) -> tuple[str | None, str | None]:
    raw_from = message.get("From", "")
    addresses = getaddresses([raw_from])
    if not addresses:
        return decode_mime_header(raw_from) or None, None
    name, address = addresses[0]
    display_name = decode_mime_header(name) or None
    email_address = (address or "").strip() or None
    # A malformed From: must not fail the whole poll — the raw header is kept
    # in raw_payload and the lead still lands without a structured address.
    if email_address and not PLAUSIBLE_ADDRESS_RE.match(email_address):
        email_address = None
    if display_name is None and email_address:
        local_part = EMAIL_LOCAL_PART_RE.match(email_address)
        display_name = local_part.group(0) if local_part else None
    return display_name, email_address


def parse_email_bytes(
    raw: bytes,
    *,
    fallback_message_id: str | None = None,
    max_attachment_bytes: int | None = None,
) -> EmailPayload:
    """Parse a raw RFC 822 message into the intake payload.

    ``fallback_message_id`` is used when the sender omitted a ``Message-ID``
    header; without a stable id the intake layer cannot deduplicate.
    Attachments above ``max_attachment_bytes`` are recorded by name and size
    only, with no content, so a huge file never blocks a lead from landing.
    """
    message = message_from_bytes(raw)

    message_id = (message.get("Message-ID") or "").strip() or fallback_message_id
    subject = decode_mime_header(message.get("Subject")) or None
    from_name, from_email = _extract_sender(message)

    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[EmailAttachmentPayload] = []

    for index, part in enumerate(message.walk()):
        if part.get_content_maintype() == "multipart":
            continue
        if _is_attachment(part):
            content = part.get_payload(decode=True) or b""
            size_bytes = len(content)
            oversized = max_attachment_bytes is not None and size_bytes > max_attachment_bytes
            attachments.append(
                EmailAttachmentPayload(
                    file_name=_attachment_file_name(part, index),
                    mime_type=part.get_content_type(),
                    size_bytes=size_bytes,
                    content_base64=(
                        None if oversized else base64.b64encode(content).decode("ascii")
                    ),
                )
            )
            continue
        if part.get_content_type() == "text/plain":
            text_parts.append(_decode_part_payload(part))
        elif part.get_content_type() == "text/html":
            html_parts.append(_decode_part_payload(part))

    body_text = "\n".join(chunk for chunk in text_parts if chunk.strip()).strip()
    if not body_text and html_parts:
        body_text = html_to_text("\n".join(html_parts))

    received_at: str | None = None
    if message.get("Date"):
        try:
            received_at = parsedate_to_datetime(message["Date"]).isoformat()
        except (TypeError, ValueError):
            received_at = message["Date"]

    return EmailPayload(
        message_id=message_id,
        subject=subject,
        from_name=from_name,
        from_email=from_email,
        body_text=body_text,
        attachments=attachments,
        raw_payload={
            "transport": "imap",
            "message_id": message_id,
            "subject": subject,
            "from": message.get("From"),
            "to": message.get("To"),
            "date": message.get("Date"),
            "received_at": received_at,
            "in_reply_to": message.get("In-Reply-To"),
            "references": message.get("References"),
            "attachment_names": [item.file_name for item in attachments],
        },
    )
