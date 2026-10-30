from __future__ import annotations

import sys
from pathlib import Path

from rq import Connection, Worker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.app.queue import get_queue, get_redis_connection


def main() -> None:
    queue = get_queue()
    connection = get_redis_connection()
    with Connection(connection):
        worker = Worker([queue], connection=connection)
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
