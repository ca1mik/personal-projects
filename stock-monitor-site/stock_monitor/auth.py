from __future__ import annotations

import secrets
from threading import Lock


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}
        self._lock = Lock()

    def create(self, username: str) -> str:
        session_id = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[session_id] = username
        return session_id

    def get(self, session_id: str | None) -> str | None:
        if not session_id:
            return None
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)
