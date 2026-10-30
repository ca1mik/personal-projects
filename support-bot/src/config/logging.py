from __future__ import annotations

import logging
import logging.config

try:  # pragma: no cover - optional dependency guard for local environments
    from pythonjsonlogger.jsonlogger import JsonFormatter
except (
    ModuleNotFoundError
):  # pragma: no cover - graceful fallback if package isn't installed locally
    JsonFormatter = None

from src.config.settings import Settings


def configure_logging(settings: Settings) -> None:
    formatter_name = "json" if settings.log_json and JsonFormatter else "default"
    formatters = {
        "default": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        }
    }
    if JsonFormatter:
        formatters["json"] = {
            "()": JsonFormatter,
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": formatters,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter_name,
                    "level": settings.log_level,
                },
            },
            "root": {
                "handlers": ["console"],
                "level": settings.log_level,
            },
        }
    )

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
