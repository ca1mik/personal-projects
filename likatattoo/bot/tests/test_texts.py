from __future__ import annotations

from app.texts import help_text


def test_help_text_mentions_myid_command() -> None:
    assert "/myid - узнать свой Telegram ID" in help_text()
