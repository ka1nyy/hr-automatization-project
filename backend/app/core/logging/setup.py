"""Standard-library JSON logging with sensitive-field redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.logging.context import get_actor_id, get_request_id

_STANDARD_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)
_SENSITIVE_FRAGMENTS = (
    "authorization",
    "password",
    "secret",
    "token",
    "iin",
    "cookie",
    "file_content",
)
_IIN_PATTERN = re.compile(r"(?<!\d)\d{12}(?!\d)")
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


def _safe_text(value: str) -> str:
    without_tokens = _BEARER_PATTERN.sub("Bearer [REDACTED]", value)
    return _IIN_PATTERN.sub("[REDACTED_IIN]", without_tokens)


def _safe_value(key: str, value: Any) -> Any:
    normalized = key.casefold().replace("-", "_")
    if any(fragment in normalized for fragment in _SENSITIVE_FRAGMENTS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(child_key): _safe_value(str(child_key), child) for child_key, child in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe_value(key, item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    """One JSON object per log line for container-friendly ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _safe_text(record.getMessage()),
            "requestId": get_request_id(),
        }
        actor_id = get_actor_id()
        if actor_id is not None:
            payload["actorId"] = actor_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = _safe_value(key, value)
        if record.exc_info:
            payload["exception"] = _safe_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    """Configure application logging once at process startup."""

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
