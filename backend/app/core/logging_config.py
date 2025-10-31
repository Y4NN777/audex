from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Any

from app.core.config import settings

_CONFIGURED = False


def configure_logging(force: bool = False) -> None:
    """
    Configure application wide logging.

    The configuration favours readable console output with timestamps and logger names,
    while still allowing overrides through environment variables (LOG_LEVEL / LOG_FORMAT).
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    log_level = settings.LOG_LEVEL.upper()
    log_format = (
        settings.LOG_FORMAT
        or "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    )
    date_format = settings.LOG_DATE_FORMAT or "%Y-%m-%d %H:%M:%S"
    handlers: dict[str, Any] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    }

    handler_names = ["console"]

    if settings.LOG_FILE:
        log_file_path = Path(settings.LOG_FILE).expanduser()
        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # noqa: BLE001 - avoid breaking startup if path invalid
            logging.getLogger(__name__).warning("Failed to prepare log directory for %s: %s", log_file_path, exc)
        else:
            handlers["file"] = {
                "class": "logging.FileHandler",
                "formatter": "standard",
                "filename": str(log_file_path),
                "encoding": "utf-8",
            }
            handler_names.append("file")

    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": log_format,
                "datefmt": date_format,
            }
        },
        "handlers": handlers,
        "loggers": {
            "": {
                "handlers": handler_names,
                "level": log_level,
            },
            # Harmonise uvicorn logs with the rest of the application.
            "uvicorn": {
                "handlers": handler_names,
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": handler_names,
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": handler_names,
                "level": log_level,
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(config)
    logging.getLogger(__name__).debug("Logging configured (level=%s)", log_level)
    _CONFIGURED = True
