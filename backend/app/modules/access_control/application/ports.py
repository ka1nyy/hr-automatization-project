"""Access-control persistence and organization-boundary ports."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.access_control.domain.entities import (
    Permission,
    PermissionGrant,
    Role,
    UserRoleAssignment,
)


class RoleRepository(Protocol):
    async def list(self, *, organization_id: UUID | None = None) -> Sequence[Role]: ...

    async def get(self, role_id: UUID) -> Role | None: ...

    async def find_by_code(self, code: str, *, organization_id: UUID | None) -> Role | None: ...

    async def add(self, role: Role) -> None: ...

    async def replace_permissions(
        self, role_id: UUID, permission_ids: set[UUID], actor_id: UUID
    ) -> None: ...


class PermissionRepository(Protocol):
    async def list(self, *, active_only: bool = True) -> Sequence[Permission]: ...

    async def find_by_codes(self, codes: set[str]) -> Sequence[Permission]: ...

    async def synchronize_catalog(self, permissions: Sequence[Permission]) -> None: ...


class RoleAssignmentRepository(Protocol):
    async def list_for_user(
        self,
        user_id: UUID,
        *,
        effective_at: datetime | None = None,
    ) -> Sequence[UserRoleAssignment]: ...

    async def get(self, assignment_id: UUID) -> UserRoleAssignment | None: ...

    async def add(self, assignment: UserRoleAssignment) -> None: ...

    async def update(self, assignment: UserRoleAssignment, *, expected_revision: int) -> bool: ...

    async def active_grants(
        self,
        user_id: UUID,
        permission_code: str,
        *,
        effective_at: datetime,
    ) -> Sequence[PermissionGrant]: ...

    async def has_overlapping_assignment(self, assignment: UserRoleAssignment) -> bool: ...


class AccessControlTransaction(Protocol):
    async def __aenter__(self) -> AccessControlTransaction: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    @property
    def roles(self) -> RoleRepository: ...

    @property
    def permissions(self) -> PermissionRepository: ...

    @property
    def assignments(self) -> RoleAssignmentRepository: ...


class OrganizationScopeResolver(Protocol):
    """Resolves current organization membership without coupling to organization storage."""

    async def user_unit_ids(
        self,
        user_id: UUID,
        organization_id: UUID,
        *,
        effective_at: datetime,
    ) -> frozenset[UUID]: ...

    async def is_descendant_or_same(
        self,
        organization_id: UUID,
        ancestor_unit_id: UUID,
        candidate_unit_id: UUID,
        *,
        effective_at: datetime,
    ) -> bool: ...


class AccessChangeRecorder(Protocol):
    """Atomic audit/outbox recorder supplied by infrastructure."""

    async def role_created(self, *, role: Role, actor_id: UUID, reason: str | None) -> None: ...

    async def role_assignment_changed(
        self,
        *,
        assignment: UserRoleAssignment,
        actor_id: UUID,
        action: str,
        reason: str | None,
    ) -> None: ...


class NullAccessChangeRecorder:
    async def role_created(self, *, role: Role, actor_id: UUID, reason: str | None) -> None:
        return None

    async def role_assignment_changed(
        self,
        *,
        assignment: UserRoleAssignment,
        actor_id: UUID,
        action: str,
        reason: str | None,
    ) -> None:
        return None
