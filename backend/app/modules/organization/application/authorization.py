"""Default permission-set authorization adapter.

Production can inject the access-control module's descendant-aware implementation.
"""

from uuid import UUID

from app.modules.organization.domain.errors import PermissionDeniedError
from app.modules.organization.domain.ports import Actor


class DenyAllOrganizationAuthorizer:
    """Fail-closed composition default; production must inject DB authorization."""

    async def require(
        self,
        actor: Actor,
        permission: str,
        organization_id: UUID,
        *,
        unit_id: UUID | None = None,
    ) -> None:
        raise PermissionDeniedError(permission, scope_violation=unit_id is not None)


class PermissionSetOrganizationAuthorizer:
    """Explicit test/dev adapter; never used by the production composition default."""

    async def require(
        self,
        actor: Actor,
        permission: str,
        organization_id: UUID,
        *,
        unit_id: UUID | None = None,
    ) -> None:
        if "*" not in actor.permissions and permission not in actor.permissions:
            raise PermissionDeniedError(permission)
        if actor.organization_id is not None and actor.organization_id != organization_id:
            raise PermissionDeniedError(permission, scope_violation=True)
        if unit_id is not None and unit_id not in actor.scoped_unit_ids:
            raise PermissionDeniedError(permission, scope_violation=True)
