"""Structured single-line JSON logging with correlation and case ids (NFR-06)."""

import json
import logging
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from onboardx.config.redaction import (
    RedactionFilter,
    redact_text,
    redact_value,
)

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_request_scope: ContextVar[MutableMapping[str, Any] | None] = ContextVar(
    "request_scope", default=None
)

_RESERVED_KEYS = frozenset({"timestamp", "level", "correlation_id", "message", "case_id"})
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


def set_correlation_id(value: str) -> Token[str | None]:
    return _correlation_id.set(value)


def reset_correlation_id(token: Token[str | None]) -> None:
    _correlation_id.reset(token)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def bind_request_scope(scope: MutableMapping[str, Any]) -> Token[MutableMapping[str, Any] | None]:
    """Remember the ASGI scope so case_id can be read from its path parameters lazily."""
    return _request_scope.set(scope)


def reset_request_scope(token: Token[MutableMapping[str, Any] | None]) -> None:
    _request_scope.reset(token)


def current_case_id() -> str | None:
    """Return the case_id path parameter of the request being served, if any."""
    scope = _request_scope.get()
    if scope is None:
        return None
    value = scope.get("path_params", {}).get("case_id")
    return None if value is None else str(value)


class JsonFormatter(logging.Formatter):
    """Format every record as one JSON line; redacts PII defensively."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")
        payload: dict[str, Any] = {
            "timestamp": timestamp.replace("+00:00", "Z"),
            "level": record.levelname,
            "correlation_id": get_correlation_id(),
            "message": redact_text(record.getMessage()),
            "logger": record.name,
        }
        case_id = record.__dict__.get("case_id") or current_case_id()
        if case_id is not None:
            payload["case_id"] = case_id
        for key in set(record.__dict__) - _STANDARD_ATTRS - _RESERVED_KEYS:
            payload[key] = redact_value(key, record.__dict__[key])
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


class _StdoutHandler(logging.Handler):
    """Handler that always writes to the current sys.stdout."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stdout.write(self.format(record) + "\n")
            sys.stdout.flush()
        except Exception:
            self.handleError(record)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON handler on the root logger (idempotent)."""
    handler = _StdoutHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
