"""Structured JSON logs with a redaction filter. OTP codes, cookies, passwords and tokens must never
reach a log line (Phase 4 exit criterion); the filter is the last line of defence, not the first."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

SENSITIVE_KEY = re.compile(
    r"pass(word)?|otp|cookie|token|secret|authorization|storage_state|dsn|session_id|csrf|master_key", re.I
)
SENSITIVE_INLINE = re.compile(
    r"(?i)\b(pass(?:word)?|otp|cookie|set-cookie|token|secret|authorization|csrf)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
REDACTED = "[redacted]"
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "taskName"}


def redact_value(key: str, value: Any) -> Any:
    if SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, dict):
        return {k: redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(key, v) for v in value]
    if isinstance(value, str):
        return SENSITIVE_INLINE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", value)
    return value


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": self.service,
            "logger": record.name,
            "msg": redact_value("msg", record.getMessage()),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD and not key.startswith("_"):
                payload[key] = redact_value(key, value)
        if record.exc_info:
            payload["exc"] = redact_value("exc", self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def setup_logging(service: str, level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel("WARNING")
