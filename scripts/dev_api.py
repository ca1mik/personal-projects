from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.app.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "apps.api.app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=os.getenv("API_RELOAD", "0") == "1",
    )


if __name__ == "__main__":
    main()
