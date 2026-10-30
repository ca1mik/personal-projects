from __future__ import annotations

from src.services.platforms import Button


def build_max_attachments(buttons: list[list[Button]]) -> list[dict] | None:
    if not buttons:
        return None

    payload_buttons: list[list[dict]] = []
    for row in buttons:
        rendered_row: list[dict] = []
        for button in row:
            if button.kind == "url" and button.url:
                rendered_row.append(
                    {"type": "link", "text": button.text, "url": button.url}
                )
            else:
                rendered_row.append(
                    {
                        "type": "callback",
                        "text": button.text,
                        "payload": button.action or "noop",
                    }
                )
        payload_buttons.append(rendered_row)

    return [{"type": "inline_keyboard", "payload": {"buttons": payload_buttons}}]
