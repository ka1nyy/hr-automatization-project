"""ASGI authentication adapter that leaves authorization to route dependencies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from app.core.config import Settings
from app.core.errors import ApplicationError, UnauthenticatedError
from app.core.logging.context import bind_actor_id, reset_actor_id
from app.core.security.context import bind_principal, reset_principal
from app.core.security.dev import DevelopmentHeaderAuthenticator
from app.core.security.ports import AuthenticationPort

ASGIMessage = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[ASGIMessage]]
Send = Callable[[ASGIMessage], Awaitable[None]]
ASGIApp = Callable[[MutableMapping[str, Any], Receive, Send], Awaitable[None]]


def _headers(scope: MutableMapping[str, Any]) -> dict[str, str]:
    return {
        key.decode("latin-1").casefold(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


class AuthenticationMiddleware:
    """Resolve identity once per request and store failures for stable FastAPI handling."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: Settings,
        token_authenticator: AuthenticationPort | None = None,
    ) -> None:
        self.app = app
        self.token_authenticator = token_authenticator
        self.dev_authenticator = (
            DevelopmentHeaderAuthenticator(settings) if settings.dev_auth_enabled else None
        )

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Receive,
        send: Send,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        principal = None
        auth_error: ApplicationError | None = None
        authorization = headers.get("authorization")
        try:
            if authorization:
                scheme, separator, token = authorization.partition(" ")
                if scheme.casefold() != "bearer" or not separator or not token.strip():
                    raise UnauthenticatedError("A valid Bearer token is required.")
                if self.token_authenticator is None:
                    raise UnauthenticatedError("Bearer authentication is not configured.")
                principal = await self.token_authenticator.authenticate(token.strip())
            elif self.dev_authenticator is not None:
                principal = await self.dev_authenticator.authenticate(headers)
        except ApplicationError as exc:
            auth_error = exc

        state = scope.setdefault("state", {})
        state["principal"] = principal
        state["authentication_error"] = auth_error
        principal_token = bind_principal(principal)
        actor_token = bind_actor_id(principal.user_id if principal is not None else None)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_actor_id(actor_token)
            reset_principal(principal_token)
