"""Convenience wrappers over :class:`AuthorizationPort`.

Two ways to demand a permission, both fail-closed and both accepting either a
:class:`PermissionDefinition` from the registry or a bare code string.

In a route, declare the requirement as a dependency::

    from app.core.security.require import Requires
    from app.modules.access_control.domain.permissions import Permissions

    @router.get("/employees")
    async def list_employees(
        _: Annotated[None, Depends(Requires(Permissions.EMPLOYEES_READ))],
    ) -> ...:

The organization is taken from the caller's principal.  When the permission is scoped by
something in the request instead — a body field, a path parameter — resolve it there and
call :func:`authorize` directly, because a dependency cannot see the parsed body.

In a service, call the helper and pass the scope explicitly::

    from app.core.security.require import authorize

    await authorize(
        self._authorization, principal, Permissions.EMPLOYEES_READ, organization_id=org_id
    )
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends

from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort


class SupportsPermissionCode(Protocol):
    """A permission registry entry, or anything else that renders to its code."""

    @property
    def code(self) -> str: ...


PermissionLike = SupportsPermissionCode | str


def permission_code(permission: PermissionLike) -> str:
    """Normalise a registry entry or a bare string to a permission code."""

    return permission if isinstance(permission, str) else permission.code


async def authorize(
    authorization: AuthorizationPort,
    principal: Principal,
    permission: PermissionLike,
    *,
    organization_id: UUID | None = None,
    unit_id: UUID | None = None,
    subject_user_id: UUID | None = None,
) -> None:
    """Demand a permission, raising :class:`ForbiddenError` when it is not held.

    Thin by design: it exists so call sites read as one line and so permission handles
    can be passed instead of string literals, not to hide the scope arguments — those
    stay explicit, because getting them wrong is how a scoped check quietly becomes a
    global one.
    """

    await authorization.require(
        principal=principal,
        permission_code=permission_code(permission),
        organization_id=organization_id,
        unit_id=unit_id,
        subject_user_id=subject_user_id,
    )


def Requires(  # noqa: N802 - reads as a declaration at the call site, not a function
    permission: PermissionLike,
) -> Callable[[Principal, AuthorizationPort], Awaitable[None]]:
    """Build a FastAPI dependency demanding ``permission`` in the caller's organization.

    Returns nothing useful: it is declared for its side effect of refusing the request.
    """

    code = permission_code(permission)

    async def dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
        authorization: Annotated[AuthorizationPort, Depends(get_authorization_port)],
    ) -> None:
        await authorization.require(
            principal=principal,
            permission_code=code,
            organization_id=principal.organization_id,
        )

    return dependency
