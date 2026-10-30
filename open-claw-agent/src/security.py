import secrets
import time
from dataclasses import dataclass

@dataclass
class PendingConfirm:
    code: str
    expires_at: float
    payload: dict

class Security:
    def __init__(self, allowed_user_ids: set[int], allowed_chat_ids: set[int], confirm_ttl: int):
        self.allowed_user_ids = allowed_user_ids
        self.allowed_chat_ids = allowed_chat_ids
        self.confirm_ttl = confirm_ttl
        self.pending: dict[tuple[int, int], PendingConfirm] = {}

    def is_allowed(self, user_id: int, chat_id: int) -> bool:
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            return False
        if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            return False
        return True

    def create_confirm(self, user_id: int, chat_id: int, payload: dict) -> str:
        code = secrets.token_urlsafe(6)  # короткий код
        self.pending[(user_id, chat_id)] = PendingConfirm(
            code=code,
            expires_at=time.time() + self.confirm_ttl,
            payload=payload,
        )
        return code

    def consume_confirm(self, user_id: int, chat_id: int, code: str) -> dict | None:
        key = (user_id, chat_id)
        item = self.pending.get(key)
        if not item:
            return None
        if time.time() > item.expires_at:
            self.pending.pop(key, None)
            return None
        if item.code != code:
            return None
        self.pending.pop(key, None)
        return item.payload
