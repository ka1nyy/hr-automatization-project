"""Authorized access-management use cases used by delivery adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from uuid import UUID

from app.core.errors import ForbiddenError, ScopeViolationError
from app.modules.access_control.application.authorization import (
    AuthorizationContext,
    AuthorizationService,
)
from app.modules.access_control.application.services import (
    AccessControlService,
    AssignRoleCommand,
    CreatePermissionCommand,
    CreateRoleCommand,
    UpdatePermissionCommand,
    UpdateRoleCommand,
)
from app.modules.access_control.domain.entities import (
    Permission,
    Role,
    ScopeType,
    UserRoleAssignment,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessActor:
    user_id: UUID
    organization_id: UUID | None


class AuthorizedAccessControlService:
    """Keeps permission and scope checks out of HTTP route functions."""

    def __init__(
        self,
        access: AccessControlService,
        authorization: AuthorizationService,
    ) -> None:
        self._access = access
        self._authorization = authorization

    async def list_roles(
        self,
        *,
        actor: AccessActor,
        organization_id: UUID | None,
    ) -> Sequence[Role]:
        target_organization = organization_id or actor.organization_id
        await self._require_manage(actor, target_organization)
        return await self._access.list_roles(organization_id=target_organization)

    async def list_permissions(
        self, *, actor: AccessActor, include_inactive: bool = False
    ) -> Sequence[Permission]:
        await self._require_manage(actor, actor.organization_id)
        return await self._access.list_permissions(include_inactive=include_inactive)

    async def create_role(
        self,
        command: CreateRoleCommand,
        *,
        actor: AccessActor,
    ) -> Role:
        target_organization = command.organization_id or actor.organization_id
        await self._require_manage(actor, target_organization)
        scoped_command = replace(command, organization_id=target_organization)
        return await self._access.create_role(scoped_command, actor_id=actor.user_id)

    async def update_role(self, command: UpdateRoleCommand, *, actor: AccessActor) -> Role:
        role = await self._access.get_role(command.role_id)
        await self._require_manage(actor, role.organization_id)
        return await self._access.update_role(command, actor_id=actor.user_id)

    async def delete_role(
        self, role_id: UUID, *, actor: AccessActor, reason: str | None
    ) -> None:
        role = await self._access.get_role(role_id)
        await self._require_manage(actor, role.organization_id)
        await self._access.delete_role(role_id, actor_id=actor.user_id, reason=reason)

    async def create_permission(
        self, command: CreatePermissionCommand, *, actor: AccessActor
    ) -> Permission:
        # Permissions are global rather than per-organization, so managing them is checked
        # against the actor's own organization scope.
        await self._require_manage(actor, actor.organization_id)
        return await self._access.create_permission(command, actor_id=actor.user_id)

    async def update_permission(
        self, command: UpdatePermissionCommand, *, actor: AccessActor
    ) -> Permission:
        await self._require_manage(actor, actor.organization_id)
        return await self._access.update_permission(command, actor_id=actor.user_id)

    async def delete_permission(
        self, permission_id: UUID, *, actor: AccessActor, reason: str | None
    ) -> None:
        await self._require_manage(actor, actor.organization_id)
        await self._access.delete_permission(
            permission_id, actor_id=actor.user_id, reason=reason
        )

    async def assign_role(
        self,
        command: AssignRoleCommand,
        *,
        actor: AccessActor,
    ) -> UserRoleAssignment:
        target_organization = command.organization_id or actor.organization_id
        await self._require_manage(actor, target_organization)
        if command.scope_type is ScopeType.SELF:
            if target_organization is None:
                raise ScopeViolationError("A SELF role assignment must belong to an organization")
            if not await self._authorization.is_organization_member(
                user_id=command.user_id,
                organization_id=target_organization,
            ):
                raise ScopeViolationError(
                    "The target user is outside the role assignment organization"
                )
            command = replace(command, organization_id=target_organization)
        return await self._access.assign_role(command, actor_id=actor.user_id)

    async def revoke_role_assignment(
        self,
        assignment_id: UUID,
        *,
        actor: AccessActor,
        reason: str,
        expected_revision: int,
    ) -> UserRoleAssignment:
        assignment = await self._access.get_role_assignment(assignment_id)
        target_organization = assignment.scope.organization_id
        if target_organization is None and assignment.scope.scope_type is ScopeType.SELF:
            await self._require_legacy_self_assignment_manage(
                actor=actor,
                target_user_id=assignment.user_id,
            )
        else:
            await self._require_manage(actor, target_organization)
        return await self._access.revoke_role_assignment(
            assignment_id,
            actor_id=actor.user_id,
            reason=reason,
            expected_revision=expected_revision,
        )

    async def _require_legacy_self_assignment_manage(
        self,
        *,
        actor: AccessActor,
        target_user_id: UUID,
    ) -> None:
        """Protect organization-less SELF rows created before scopes were bound."""

        local_scope_authorized = False
        if actor.organization_id is not None:
            try:
                await self._require_manage(actor, actor.organization_id)
            except ForbiddenError:
                pass
            else:
                local_scope_authorized = True
                if await self._authorization.is_organization_member(
                    user_id=target_user_id,
                    organization_id=actor.organization_id,
                ):
                    return

        try:
            await self._require_manage(actor, None)
        except ForbiddenError as exc:
            if local_scope_authorized:
                raise ScopeViolationError(
                    "The target user is outside the actor's organization"
                ) from exc
            raise

    async def _require_manage(
        self,
        actor: AccessActor,
        organization_id: UUID | None,
    ) -> None:
        await self._authorization.require(
            actor_user_id=actor.user_id,
            permission_code="roles.manage",
            context=AuthorizationContext(
                organization_id=organization_id,
            ),
        )
