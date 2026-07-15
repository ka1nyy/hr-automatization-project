"""FastAPI identity dependencies."""

from __future__ import annotations

from fastapi import Request

from app.core.errors import ApplicationError, UnauthenticatedError
from app.core.security.identity import Principal


def get_optional_principal(request: Request) -> Principal | None:
    """Return the authenticated principal when the endpoint permits anonymous access."""

    error = getattr(request.state, "authentication_error", None)
    if isinstance(error, ApplicationError):
        raise error
    principal = getattr(request.state, "principal", None)
    return principal if isinstance(principal, Principal) else None


def get_current_principal(request: Request) -> Principal:
    """Require an authenticated caller."""

    principal = get_optional_principal(request)
    if principal is None:
        raise UnauthenticatedError()
    return principal
