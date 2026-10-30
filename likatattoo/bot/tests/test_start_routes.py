from __future__ import annotations

from app.start_routes import extract_start_argument, resolve_start_action


def test_extract_start_argument_reads_deep_link_payload() -> None:
    assert extract_start_argument("/start generate") == "generate"
    assert extract_start_argument(" /start   portfolio  ") == "portfolio"
    assert extract_start_argument("/help") == ""


def test_resolve_start_action_supports_aliases() -> None:
    assert resolve_start_action("book") == "booking"
    assert resolve_start_action("generate") == "generate"
    assert resolve_start_action("prompt") == "chatgpt"
    assert resolve_start_action("payment") == "deposit"
    assert resolve_start_action("materials") == "portfolio"
    assert resolve_start_action("gallery") == "examples"
    assert resolve_start_action("write") == "contacts"


def test_resolve_start_action_falls_back_to_home() -> None:
    assert resolve_start_action("") == "home"
    assert resolve_start_action("unknown-route") == "home"
