"""Framework-independent RBAC and organization-scope entities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{1,127}$")


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ScopeType(StrEnum):
    SELF = "self"
    OWN_UNIT = "own_unit"
    OWN_UNIT_AND_DESCENDANTS = "own_unit_and_descendants"
    SELECTED_UNITS = "selected_units"
    ORGANIZATION = "organization"


@dataclass(frozen=True, slots=True, kw_only=True)
class Role:
    code: str
    name: str
    id: UUID = field(default_factory=uuid4)
    description: str | None = None
    organization_id: UUID | None = None
    permission_codes: frozenset[str] = field(default_factory=frozenset)
    active: bool = True
    system: bool = False
    revision: int = 1
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not _CODE_PATTERN.fullmatch(self.code):
            raise ValueError("role code must be a stable lowercase identifier")
        if not self.name.strip():
            raise ValueError("role name must not be blank")
        if self.revision < 1:
            raise ValueError("revision must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class Permission:
    code: str
    name: str
    description: str
    id: UUID = field(default_factory=uuid4)
    active: bool = True
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not _CODE_PATTERN.fullmatch(self.code):
            raise ValueError("permission code must be a stable lowercase identifier")
        if not self.name.strip():
            raise ValueError("permission name must not be blank")


@dataclass(frozen=True, slots=True, kw_only=True)
class RolePermission:
    role_id: UUID
    permission_id: UUID
    granted_at: datetime = field(default_factory=_utc_now)
    granted_by: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessScope:
    scope_type: ScopeType
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID | None = None
    unit_ids: frozenset[UUID] = field(default_factory=frozenset)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if self.scope_type is ScopeType.SELECTED_UNITS and not self.unit_ids:
            raise ValueError("selected_units scope requires at least one unit")
        if self.scope_type is not ScopeType.SELECTED_UNITS and self.unit_ids:
            raise ValueError("only selected_units scope may contain explicit unit IDs")
        if self.organization_id is None:
            raise ValueError("organization_id is required for every access scope")


@dataclass(frozen=True, slots=True, kw_only=True)
class UserRoleAssignment:
    user_id: UUID
    role_id: UUID
    scope: AccessScope
    effective_from: datetime
    id: UUID = field(default_factory=uuid4)
    effective_to: datetime | None = None
    created_by: UUID | None = None
    created_at: datetime = field(default_factory=_utc_now)
    revoked_at: datetime | None = None
    revoked_by: UUID | None = None
    revocation_reason: str | None = None
    revision: int = 1

    def __post_init__(self) -> None:
        if self.effective_from.tzinfo is None:
            raise ValueError("effective_from must be timezone-aware")
        if self.effective_to is not None:
            if self.effective_to.tzinfo is None:
                raise ValueError("effective_to must be timezone-aware")
            if self.effective_to <= self.effective_from:
                raise ValueError("effective_to must be after effective_from")
        if self.revoked_at is not None and self.revoked_at.tzinfo is None:
            raise ValueError("revoked_at must be timezone-aware")
        if self.revision < 1:
            raise ValueError("revision must be positive")

    def is_effective_at(self, at: datetime) -> bool:
        return (
            self.revoked_at is None
            and self.effective_from <= at
            and (self.effective_to is None or at < self.effective_to)
        )

    def revoke(
        self,
        *,
        actor_id: UUID,
        reason: str,
        at: datetime | None = None,
    ) -> UserRoleAssignment:
        if self.revoked_at is not None:
            raise ValueError("role assignment is already revoked")
        if not reason.strip():
            raise ValueError("revocation reason is required")
        return replace(
            self,
            revoked_at=at or _utc_now(),
            revoked_by=actor_id,
            revocation_reason=reason.strip(),
            revision=self.revision + 1,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class PermissionGrant:
    """A resolved permission and scope used during authorization."""

    permission_code: str
    assignment_id: UUID
    scope: AccessScope
