"""Role, permission-catalog, and role-assignment use cases."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid5

from app.core.errors import (
    ConcurrencyConflictError,
    ConflictError,
    ResourceNotFoundError,
    ValidationError,
)
from app.modules.access_control.application.ports import (
    AccessChangeRecorder,
    AccessControlTransaction,
    NullAccessChangeRecorder,
)
from app.modules.access_control.domain.entities import (
    AccessScope,
    Permission,
    Role,
    ScopeType,
    UserRoleAssignment,
)
from app.modules.access_control.domain.permissions import PERMISSION_CATALOG


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateRoleCommand:
    code: str
    name: str
    permission_codes: frozenset[str]
    organization_id: UUID | None = None
    description: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AssignRoleCommand:
    user_id: UUID
    role_id: UUID
    scope_type: ScopeType
    effective_from: datetime
    organization_id: UUID | None = None
    unit_ids: frozenset[UUID] = frozenset()
    effective_to: datetime | None = None
    reason: str | None = None


class AccessControlService:
    def __init__(
        self,
        transaction_factory: Callable[[], AccessControlTransaction],
        change_recorder: AccessChangeRecorder | None = None,
    ) -> None:
        self._transaction_factory = transaction_factory
        self._changes = change_recorder or NullAccessChangeRecorder()

    async def list_roles(self, *, organization_id: UUID | None = None) -> Sequence[Role]:
        async with self._transaction_factory() as transaction:
            return await transaction.roles.list(organization_id=organization_id)

    async def list_permissions(self) -> Sequence[Permission]:
        async with self._transaction_factory() as transaction:
            return await transaction.permissions.list(active_only=True)

    async def get_role_assignment(self, assignment_id: UUID) -> UserRoleAssignment:
        async with self._transaction_factory() as transaction:
            assignment = await transaction.assignments.get(assignment_id)
        if assignment is None:
            raise ResourceNotFoundError("roleAssignment", assignment_id)
        return assignment

    async def synchronize_permission_catalog(self) -> None:
        namespace = UUID("de7a53f1-8d76-4a12-9cd8-b5f3d61655b2")
        catalog = tuple(
            Permission(
                id=uuid5(namespace, item.code),
                code=item.code,
                name=item.name,
                description=item.description,
            )
            for item in PERMISSION_CATALOG
        )
        async with self._transaction_factory() as transaction:
            await transaction.permissions.synchronize_catalog(catalog)

    async def create_role(self, command: CreateRoleCommand, *, actor_id: UUID) -> Role:
        role = Role(
            code=command.code,
            name=command.name,
            description=command.description,
            organization_id=command.organization_id,
            permission_codes=command.permission_codes,
        )
        async with self._transaction_factory() as transaction:
            existing = await transaction.roles.find_by_code(
                role.code,
                organization_id=role.organization_id,
            )
            if existing is not None:
                raise ConflictError("A role with this code already exists in the scope")
            permissions = await transaction.permissions.find_by_codes(set(command.permission_codes))
            found_codes = {permission.code for permission in permissions}
            missing = sorted(command.permission_codes - found_codes)
            if missing:
                raise ValidationError(
                    "One or more permission codes are unknown",
                    details={"unknownPermissionCodes": missing},
                )
            await transaction.roles.add(role)
            await transaction.roles.replace_permissions(
                role.id,
                {permission.id for permission in permissions},
                actor_id,
            )
            await self._changes.role_created(
                role=role,
                actor_id=actor_id,
                reason=command.reason,
            )
        return role

    async def assign_role(
        self, command: AssignRoleCommand, *, actor_id: UUID
    ) -> UserRoleAssignment:
        try:
            scope = AccessScope(
                scope_type=command.scope_type,
                organization_id=command.organization_id,
                unit_ids=command.unit_ids,
            )
            assignment = UserRoleAssignment(
                user_id=command.user_id,
                role_id=command.role_id,
                scope=scope,
                effective_from=command.effective_from,
                effective_to=command.effective_to,
                created_by=actor_id,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        async with self._transaction_factory() as transaction:
            role = await transaction.roles.get(command.role_id)
            if role is None or not role.active:
                raise ResourceNotFoundError("role", command.role_id)
            if role.organization_id is not None and role.organization_id != command.organization_id:
                raise ValidationError("Role and access scope belong to different organizations")
            if await transaction.assignments.has_overlapping_assignment(assignment):
                raise ConflictError("An overlapping role assignment already exists")
            await transaction.assignments.add(assignment)
            await self._changes.role_assignment_changed(
                assignment=assignment,
                actor_id=actor_id,
                action="created",
                reason=command.reason,
            )
        return assignment

    async def revoke_role_assignment(
        self,
        assignment_id: UUID,
        *,
        actor_id: UUID,
        reason: str,
        expected_revision: int,
    ) -> UserRoleAssignment:
        if not reason.strip():
            raise ValidationError("A revocation reason is required")
        async with self._transaction_factory() as transaction:
            current = await transaction.assignments.get(assignment_id)
            if current is None:
                raise ResourceNotFoundError("roleAssignment", assignment_id)
            if current.revision != expected_revision:
                raise ConcurrencyConflictError("Role assignment revision is stale")
            try:
                revoked = current.revoke(
                    actor_id=actor_id,
                    reason=reason,
                    at=datetime.now(UTC),
                )
            except ValueError as exc:
                raise ConflictError(str(exc)) from exc
            saved = await transaction.assignments.update(
                revoked,
                expected_revision=expected_revision,
            )
            if not saved:
                raise ConcurrencyConflictError("Role assignment was concurrently modified")
            await self._changes.role_assignment_changed(
                assignment=revoked,
                actor_id=actor_id,
                action="revoked",
                reason=reason,
            )
        return revoked
