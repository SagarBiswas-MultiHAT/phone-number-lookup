# file: phoneint/logging_config.py
"""
Logging configuration.

phoneint uses standard library logging. This module provides a small structured
logging option (JSON) for easier ingestion in CI or containers.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # Best-effort include extra fields.
        for k, v in record.__dict__.items():
            if k in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            }:
                continue
            if k.startswith("_"):
                continue
            payload[k] = v

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(*, level: str = "INFO", json_logging: bool = False) -> None:
    """
    Configure root logging for CLI/GUI use.
    """

    root = logging.getLogger()
    root.setLevel(level.upper())

    # Replace existing handlers to avoid duplicate logs (common in notebooks/GUI restarts).
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    if json_logging:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root.addHandler(handler)
