"""Request and actor correlation context."""

from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import UUID

from app.shared.identifiers import new_uuid

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_actor_id: ContextVar[str | None] = ContextVar("actor_id", default=None)


def get_request_id() -> str:
    """Return the current request ID, creating one for non-HTTP work if needed."""

    current = _request_id.get()
    if current is None:
        current = str(new_uuid())
        _request_id.set(current)
    return current


def normalize_request_id(value: str | None) -> str:
    """Accept canonical UUID request IDs and replace untrusted/invalid values."""

    if value is None:
        return str(new_uuid())
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        return str(new_uuid())


def bind_request_id(request_id: str) -> Token[str | None]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


def get_actor_id() -> str | None:
    return _actor_id.get()


def bind_actor_id(actor_id: object | None) -> Token[str | None]:
    return _actor_id.set(None if actor_id is None else str(actor_id))


def reset_actor_id(token: Token[str | None]) -> None:
    _actor_id.reset(token)
