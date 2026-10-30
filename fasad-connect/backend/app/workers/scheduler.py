"""Channel poll scheduler.

Repeat-enqueue instead of rq-scheduler: a small loop wakes every
``CHANNEL_SCHEDULER_TICK_SECONDS``, finds accounts whose ``next_poll_at`` is due,
and pushes a poll job onto the default RQ queue. Per-account intervals live in
the account config, so operators change them from the admin UI with no restart.

Run as its own process: ``python -m app.workers.scheduler``.
"""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable
from datetime import UTC, datetime
from types import FrameType

from sqlalchemy.orm import Session

# Worker processes do not build the FastAPI app, so nothing else imports every
# model module. Without the registry SQLAlchemy cannot resolve relationships
# declared by string name ("User") and every mapper fails to initialize.
import app.db.base  # noqa: F401
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.modules.messaging.channel_config import schedule_next_poll
from app.modules.messaging.email_service import EmailChannelService

logger = logging.getLogger(__name__)

_shutdown = False


def _handle_signal(signum: int, _frame: FrameType | None) -> None:
    global _shutdown
    logger.info("Scheduler received signal %s, shutting down", signum)
    _shutdown = True


def _default_enqueue(account_id: str) -> None:
    """Hand the poll to RQ, or run it here when inline mode is configured.

    Inline mode exists because rq imports a fork-only multiprocessing context
    and cannot even be imported on Windows, where local dev happens. A shop with
    one mailbox does not need a worker process at all.
    """
    # Imported lazily for the same reason.
    from app.workers.email_poller import enqueue_email_poll, poll_email_account

    if get_settings().channel_poll_inline:
        poll_email_account(account_id)
        return
    enqueue_email_poll(account_id)


def tick(
    db: Session,
    *,
    now: datetime | None = None,
    enqueue: Callable[[str], None] | None = None,
) -> list[str]:
    """Enqueue a poll job for every due account. Returns the account ids enqueued.

    ``next_poll_at`` is advanced here rather than in the job, so a slow or dead
    worker cannot cause the same account to be enqueued on every tick.
    """
    dispatch = enqueue or _default_enqueue
    moment = now or datetime.now(UTC)
    enqueued: list[str] = []

    for account in EmailChannelService.list_pollable_accounts(db):
        due_at = account.next_poll_at
        if due_at is not None:
            # SQLite hands back naive datetimes; treat stored values as UTC.
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=UTC)
            if due_at > moment:
                continue
        schedule_next_poll(account, from_time=moment)
        enqueued.append(str(account.id))

    if enqueued:
        db.commit()
        for account_id in enqueued:
            try:
                dispatch(account_id)
            except Exception:  # noqa: BLE001 - a Redis blip must not kill the loop
                logger.exception("Failed to enqueue email poll for account %s", account_id)
    return enqueued


def run_scheduler() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        "Channel scheduler started, tick=%ss, mode=%s",
        settings.channel_scheduler_tick_seconds,
        "inline" if settings.channel_poll_inline else "rq",
    )
    while not _shutdown:
        try:
            with SessionLocal() as db:
                enqueued = tick(db)
            if enqueued:
                logger.info("Enqueued %s channel poll job(s)", len(enqueued))
        except Exception:  # noqa: BLE001 - the loop must outlive any single failure
            logger.exception("Scheduler tick failed")
        time.sleep(settings.channel_scheduler_tick_seconds)

    logger.info("Channel scheduler stopped")


if __name__ == "__main__":
    run_scheduler()
