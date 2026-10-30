"""Bound public intake request size and frequency before parsing JSON."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable


PUBLIC_INTAKE_PATHS = {
    "/api/v1/leads/intake",
    "/api/v1/messaging/email/intake",
    "/api/v1/messaging/telegram/webhook",
    "/api/v1/messaging/telegram/bot/webhook",
    "/api/v1/messaging/telegram/bot/telegram-api",
    "/api/v1/messaging/whatsapp/webhook",
    "/api/v1/messaging/webhook/intake",
}
MAX_BODY_BYTES = 20 * 1024 * 1024
MAX_REQUESTS_PER_MINUTE = 60
logger = logging.getLogger("app.intake_guard")


class IntakeGuard:
    def __init__(self, app: Callable[..., Any]) -> None:
        self.app = app
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()

    async def _reject(self, send: Callable[..., Any], status: int, message: str) -> None:
        body = json.dumps({"error": {"message": message}}, ensure_ascii=False).encode("utf-8")
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: dict, receive: Callable[..., Any], send: Callable[..., Any]) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path") not in PUBLIC_INTAKE_PATHS:
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        peer = scope.get("client") or ("unknown", 0)
        key = (str(peer[0]), path)
        now = time.monotonic()
        with self._lock:
            requests = self._requests[key]
            while requests and now - requests[0] >= 60:
                requests.popleft()
            if len(requests) >= MAX_REQUESTS_PER_MINUTE:
                status, message = 429, "Слишком много запросов; повторите через минуту"
            else:
                requests.append(now)
                status, message = 0, ""
        if status:
            logger.warning("intake_rejected peer=%s path=%s status=%s", peer[0], path, status)
            await self._reject(send, status, message)
            return
        chunks: list[bytes] = []
        size = 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            if event["type"] != "http.request":
                continue
            chunk = event.get("body", b"")
            size += len(chunk)
            if size > MAX_BODY_BYTES:
                logger.warning("intake_rejected peer=%s path=%s status=413", peer[0], path)
                await self._reject(send, 413, "Заявка превышает допустимый размер")
                return
            chunks.append(chunk)
            if not event.get("more_body", False):
                break
        body = b"".join(chunks)
        replayed = False

        async def replay() -> dict:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
