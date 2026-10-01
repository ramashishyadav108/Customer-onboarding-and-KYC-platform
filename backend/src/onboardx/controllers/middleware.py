"""Correlation-id middleware and request logging (NFR-06). Bodies and queries are never logged."""

import logging
import re
import time
import uuid
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from onboardx.config.constants import CORRELATION_HEADER, MAX_CORRELATION_ID_LENGTH
from onboardx.config.logging_setup import (
    bind_request_scope,
    reset_correlation_id,
    reset_request_scope,
    set_correlation_id,
)

logger = logging.getLogger("onboardx.request")
_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]+$")


def resolve_correlation_id(headers: Headers) -> str:
    """Use the inbound header when it is a safe token; otherwise generate a UUID4."""
    supplied = headers.get(CORRELATION_HEADER, "")
    if supplied and len(supplied) <= MAX_CORRELATION_ID_LENGTH and _SAFE_ID.match(supplied):
        return supplied
    return str(uuid.uuid4())


class CorrelationMiddleware:
    """Pure ASGI middleware: correlation id in, correlation id out, one log line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlation_id = resolve_correlation_id(Headers(scope=scope))
        id_token = set_correlation_id(correlation_id)
        scope_token = bind_request_scope(scope)
        outcome: dict[str, Any] = {"status": 500}

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                outcome["status"] = message["status"]
                MutableHeaders(scope=message)[CORRELATION_HEADER] = correlation_id
            await send(message)

        started = time.monotonic()
        try:
            await self.app(scope, receive, send_with_header)
        finally:
            logger.info(
                "request completed",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": outcome["status"],
                    "duration_ms": int((time.monotonic() - started) * 1000),
                },
            )
            reset_request_scope(scope_token)
            reset_correlation_id(id_token)
