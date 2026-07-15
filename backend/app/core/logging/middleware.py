"""Pure ASGI request correlation and access logging middleware."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, MutableMapping
from time import perf_counter
from typing import Any

from app.core.logging.context import bind_request_id, normalize_request_id, reset_request_id

ASGIMessage = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[ASGIMessage]]
Send = Callable[[ASGIMessage], Awaitable[None]]
ASGIApp = Callable[[MutableMapping[str, Any], Receive, Send], Awaitable[None]]


class RequestContextMiddleware:
    """Bind a validated request UUID and echo it in every HTTP response."""

    header_name = b"x-request-id"

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("spk.http")

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Receive,
        send: Send,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        incoming = next(
            (
                value.decode("ascii", errors="ignore")
                for key, value in scope.get("headers", [])
                if key.lower() == self.header_name
            ),
            None,
        )
        request_id = normalize_request_id(incoming)
        token = bind_request_id(request_id)
        started = perf_counter()
        status_code = 500

        async def send_with_request_id(message: ASGIMessage) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
                headers = list(message.get("headers", []))
                headers.append((self.header_name, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            self.logger.info(
                "request_completed",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "statusCode": status_code,
                    "durationMs": round((perf_counter() - started) * 1000, 2),
                },
            )
            reset_request_id(token)
