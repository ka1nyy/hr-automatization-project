"""Authentication ports owned by the application, not an OIDC provider."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.core.security.identity import Principal


class AuthenticationPort(Protocol):
    """Authenticate a provider-issued bearer token."""

    async def authenticate(self, bearer_token: str) -> Principal: ...


class AuthorizationPort(Protocol):
    """Backend-authoritative permission and resource-scope decision."""

    async def require(
        self,
        *,
        principal: Principal,
        permission_code: str,
        organization_id: UUID | None = None,
        unit_id: UUID | None = None,
        subject_user_id: UUID | None = None,
    ) -> None: ...
