from __future__ import annotations

from rq import Worker

from app.workers.queue import get_redis_connection


def run_worker() -> None:
    connection = get_redis_connection()
    worker = Worker(["default"], connection=connection)
    worker.work()


if __name__ == "__main__":
    run_worker()
