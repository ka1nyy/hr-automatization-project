"""Role, permission-catalog, and role-assignment use cases."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid5

from app.core.errors import (
    ConcurrencyConflictError,
    ConflictError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.errors.codes import ErrorCode
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
class UpdateRoleCommand:
    role_id: UUID
    expected_revision: int
    name: str | None = None
    description: str | None = None
    active: bool | None = None
    # None leaves the grants untouched; an empty set clears them.
    permission_codes: frozenset[str] | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CreatePermissionCommand:
    code: str
    name: str
    description: str
    reason: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdatePermissionCommand:
    permission_id: UUID
    expected_revision: int
    name: str | None = None
    description: str | None = None
    active: bool | None = None
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

    async def get_role(self, role_id: UUID) -> Role:
        async with self._transaction_factory() as transaction:
            role = await transaction.roles.get(role_id)
        if role is None:
            raise ResourceNotFoundError("role", role_id)
        return role

    async def list_permissions(self, *, include_inactive: bool = False) -> Sequence[Permission]:
        """List permissions; administration screens need the deactivated ones too."""

        async with self._transaction_factory() as transaction:
            return await transaction.permissions.list(active_only=not include_inactive)

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
                raise ConflictError(
                    "A role with this code already exists in the scope",
                    code=ErrorCode.ROLE_CODE_ALREADY_EXISTS,
                )
            permissions = await self._resolve_permissions(transaction, command.permission_codes)
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

    async def update_role(self, command: UpdateRoleCommand, *, actor_id: UUID) -> Role:
        """Edit a role's wording, activity, or grants.

        A system role's grants and activity are fixed: the seeded roles are what make the
        application usable, and an administrator who empties one locks everybody out,
        including themselves. Renaming one stays allowed.
        """

        async with self._transaction_factory() as transaction:
            role = await transaction.roles.get(command.role_id)
            if role is None:
                raise ResourceNotFoundError("role", command.role_id)
            if role.system and (
                command.permission_codes is not None or command.active is not None
            ):
                raise ConflictError(
                    "A system role's permissions and activity cannot be changed; "
                    "copy it into a new role instead",
                    code=ErrorCode.ACCESS_ENTRY_PROTECTED,
                )

            permission_ids: set[UUID] | None = None
            if command.permission_codes is not None:
                permissions = await self._resolve_permissions(
                    transaction, command.permission_codes
                )
                permission_ids = {permission.id for permission in permissions}

            updated = replace(
                role,
                name=role.name if command.name is None else command.name,
                description=(
                    role.description if command.description is None else command.description
                ),
                active=role.active if command.active is None else command.active,
                permission_codes=(
                    role.permission_codes
                    if command.permission_codes is None
                    else command.permission_codes
                ),
                revision=role.revision + 1,
                updated_at=datetime.now(UTC),
            )
            applied = await transaction.roles.update(
                updated, expected_revision=command.expected_revision
            )
            if not applied:
                raise ConcurrencyConflictError(
                    details={
                        "roleId": str(command.role_id),
                        "expectedRevision": command.expected_revision,
                        "actualRevision": role.revision,
                    }
                )
            if permission_ids is not None:
                await transaction.roles.replace_permissions(role.id, permission_ids, actor_id)
            await self._changes.role_changed(
                role=updated, actor_id=actor_id, action="updated", reason=command.reason
            )
        return updated

    async def delete_role(self, role_id: UUID, *, actor_id: UUID, reason: str | None) -> None:
        """Remove a role outright.

        Refused for system roles, and for any role that has ever been assigned: a revoked
        assignment still names the role in its audit trail, and deleting it would strand
        that history. Deactivating is the way to retire an assigned role.
        """

        async with self._transaction_factory() as transaction:
            role = await transaction.roles.get(role_id)
            if role is None:
                raise ResourceNotFoundError("role", role_id)
            if role.system:
                raise ConflictError(
                    "A system role cannot be deleted; deactivate it instead",
                    code=ErrorCode.ACCESS_ENTRY_PROTECTED,
                )
            assignments = await transaction.roles.assignment_count(role_id)
            if assignments:
                raise ConflictError(
                    "This role has been assigned and cannot be deleted; deactivate it instead",
                    code=ErrorCode.ACCESS_ENTRY_IN_USE,
                    details={"assignmentCount": assignments},
                )
            await transaction.roles.delete(role_id)
            await self._changes.role_changed(
                role=role, actor_id=actor_id, action="deleted", reason=reason
            )

    async def create_permission(
        self, command: CreatePermissionCommand, *, actor_id: UUID
    ) -> Permission:
        """Add an administrator-defined permission.

        Never a system permission: nothing in the source tree checks a code that did not
        exist when it was written. It becomes useful once a workflow rule or a role grant
        references it.
        """

        permission = Permission(
            code=command.code,
            name=command.name,
            description=command.description,
            system=False,
        )
        async with self._transaction_factory() as transaction:
            existing = await transaction.permissions.find_by_codes({command.code})
            if existing:
                raise ConflictError(
                    "A permission with this code already exists",
                    code=ErrorCode.PERMISSION_CODE_ALREADY_EXISTS,
                )
            await transaction.permissions.add(permission)
            await self._changes.permission_changed(
                permission=permission,
                actor_id=actor_id,
                action="created",
                reason=command.reason,
            )
        return permission

    async def update_permission(
        self, command: UpdatePermissionCommand, *, actor_id: UUID
    ) -> Permission:
        """Reword a permission, or deactivate an administrator-defined one.

        A system permission's wording is editable — that is presentation. Its activity is
        not: deactivating it would disable the authorization check the source tree makes
        against its code, and the failure would look like a mis-assigned role.
        """

        async with self._transaction_factory() as transaction:
            permission = await transaction.permissions.get(command.permission_id)
            if permission is None:
                raise ResourceNotFoundError("permission", command.permission_id)
            if permission.system and command.active is not None:
                raise ConflictError(
                    "A system permission cannot be deactivated; it is checked by the "
                    "application itself",
                    code=ErrorCode.ACCESS_ENTRY_PROTECTED,
                    details={"permissionCode": permission.code},
                )

            updated = replace(
                permission,
                name=permission.name if command.name is None else command.name,
                description=(
                    permission.description
                    if command.description is None
                    else command.description
                ),
                active=permission.active if command.active is None else command.active,
                revision=permission.revision + 1,
                updated_at=datetime.now(UTC),
            )
            applied = await transaction.permissions.update(
                updated, expected_revision=command.expected_revision
            )
            if not applied:
                raise ConcurrencyConflictError(
                    details={
                        "permissionId": str(command.permission_id),
                        "expectedRevision": command.expected_revision,
                        "actualRevision": permission.revision,
                    }
                )
            await self._changes.permission_changed(
                permission=updated, actor_id=actor_id, action="updated", reason=command.reason
            )
        return updated

    async def delete_permission(
        self, permission_id: UUID, *, actor_id: UUID, reason: str | None
    ) -> None:
        """Remove an administrator-defined permission.

        Refused for system permissions, and for any permission still granted to a role:
        deleting it would silently strip that grant from everyone holding the role.
        """

        async with self._transaction_factory() as transaction:
            permission = await transaction.permissions.get(permission_id)
            if permission is None:
                raise ResourceNotFoundError("permission", permission_id)
            if permission.system:
                raise ConflictError(
                    "A system permission cannot be deleted; it is checked by the "
                    "application itself",
                    code=ErrorCode.ACCESS_ENTRY_PROTECTED,
                    details={"permissionCode": permission.code},
                )
            granting_roles = await transaction.permissions.granting_role_count(permission_id)
            if granting_roles:
                raise ConflictError(
                    "This permission is granted to one or more roles; revoke it there first",
                    code=ErrorCode.ACCESS_ENTRY_IN_USE,
                    details={"roleCount": granting_roles},
                )
            await transaction.permissions.delete(permission_id)
            await self._changes.permission_changed(
                permission=permission, actor_id=actor_id, action="deleted", reason=reason
            )

    async def _resolve_permissions(
        self, transaction: AccessControlTransaction, codes: frozenset[str]
    ) -> Sequence[Permission]:
        """Look codes up, reporting the unknown ones rather than silently dropping them."""

        permissions = await transaction.permissions.find_by_codes(set(codes))
        missing = sorted(codes - {permission.code for permission in permissions})
        if missing:
            raise ValidationError(
                "One or more permission codes are unknown",
                details={"unknownPermissionCodes": missing},
            )
        return permissions

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
