"""Fail-closed authorization composition dependency."""

from __future__ import annotations

from uuid import UUID

from app.core.errors import ForbiddenError
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort


class DenyAllAuthorization:
    """Safe default until composition installs the database-backed RBAC adapter."""

    async def require(
        self,
        *,
        principal: Principal,
        permission_code: str,
        organization_id: UUID | None = None,
        unit_id: UUID | None = None,
        subject_user_id: UUID | None = None,
    ) -> None:
        del principal, organization_id, unit_id, subject_user_id
        raise ForbiddenError(f"Permission {permission_code!r} is required.")


def get_authorization_port() -> AuthorizationPort:
    """Override in application composition with the access-control module adapter."""

    return DenyAllAuthorization()
