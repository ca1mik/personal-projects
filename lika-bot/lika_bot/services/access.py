from __future__ import annotations

from lika_bot.config.settings import Settings


class AccessService:
    """Gift bot is personal by default, but the data model stays multi-user ready."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id == self._settings.admin_id

    def is_primary_user(self, telegram_id: int) -> bool:
        return telegram_id == self._settings.lika_chat_id

    def can_use_gift(self, telegram_id: int) -> bool:
        if self._settings.allow_guests:
            return True
        return self.is_primary_user(telegram_id) or self.is_admin(telegram_id)
