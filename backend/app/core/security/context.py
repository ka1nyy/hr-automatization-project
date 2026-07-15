"""Async-safe authenticated principal context."""

from __future__ import annotations

from contextvars import ContextVar, Token

from app.core.security.identity import Principal

_principal: ContextVar[Principal | None] = ContextVar("principal", default=None)


def current_principal() -> Principal | None:
    return _principal.get()


def bind_principal(principal: Principal | None) -> Token[Principal | None]:
    return _principal.set(principal)


def reset_principal(token: Token[Principal | None]) -> None:
    _principal.reset(token)
