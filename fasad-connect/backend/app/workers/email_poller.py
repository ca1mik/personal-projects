"""RQ job that polls one email channel account.

Enqueued by :mod:`app.workers.scheduler`, or directly for a manual "poll now".
Runs in a worker process, so it opens and closes its own DB session.
"""

from __future__ import annotations

import logging
import uuid

# Same reason as in app.workers.scheduler: an RQ worker never builds the
# FastAPI app, so the model registry must be imported explicitly or every
# mapper fails on the first query.
import app.db.base  # noqa: F401
from app.db.session import SessionLocal
from app.modules.messaging.email_service import EmailChannelService

logger = logging.getLogger(__name__)

EMAIL_POLL_JOB_TIMEOUT = 300


def poll_email_account(account_id: str) -> dict[str, object]:
    """Fetch new mail for one account and run it through intake."""
    with SessionLocal() as db:
        result = EmailChannelService.poll_account(db, uuid.UUID(account_id))
    if result.error:
        logger.warning(
            "Email poll for account %s finished with errors: %s", account_id, result.error
        )
    else:
        logger.info(
            "Email poll for account %s: fetched=%s created=%s skipped=%s",
            account_id,
            result.fetched,
            result.created,
            result.skipped,
        )
    return result.model_dump(mode="json")


def enqueue_email_poll(account_id: str) -> str:
    # Imported lazily: rq pulls in a fork-only multiprocessing context that
    # cannot be imported on Windows, where the test suite and dev shell run.
    from app.workers.queue import get_default_queue

    job = get_default_queue().enqueue(
        poll_email_account,
        account_id,
        job_timeout=EMAIL_POLL_JOB_TIMEOUT,
        job_id=f"email-poll:{account_id}",
    )
    return job.id
