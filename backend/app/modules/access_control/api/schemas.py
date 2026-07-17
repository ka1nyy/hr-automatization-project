"""Camel-case access-control request and response DTOs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.modules.access_control.domain.entities import ScopeType
from app.shared.api.schemas import CamelModel


class RoleCreateRequest(CamelModel):
    code: str = Field(min_length=2, max_length=128, pattern=r"^[a-z][a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    organization_id: UUID | None = None
    permission_codes: set[str] = Field(default_factory=set)
    reason: str | None = Field(default=None, max_length=1000)


class RoleUpdateRequest(CamelModel):
    """Partial edit; omitted fields are left as they are.

    ``revision`` is the revision the caller read, so a concurrent edit is reported
    instead of being silently overwritten.
    """

    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    active: bool | None = None
    # Omit to leave grants untouched; send an empty list to clear them.
    permission_codes: set[str] | None = None
    reason: str | None = Field(default=None, max_length=1000)


class RoleDeleteRequest(CamelModel):
    reason: str | None = Field(default=None, max_length=1000)


class RoleResponse(CamelModel):
    id: UUID
    organization_id: UUID | None
    code: str
    name: str
    description: str | None
    permission_codes: frozenset[str]
    active: bool
    system: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class PermissionCreateRequest(CamelModel):
    code: str = Field(min_length=2, max_length=128, pattern=r"^[a-z][a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=4000)
    reason: str | None = Field(default=None, max_length=1000)


class PermissionUpdateRequest(CamelModel):
    """Partial edit. The code is immutable: it is what the application checks against."""

    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    active: bool | None = None
    reason: str | None = Field(default=None, max_length=1000)


class PermissionDeleteRequest(CamelModel):
    reason: str | None = Field(default=None, max_length=1000)


class PermissionResponse(CamelModel):
    id: UUID
    code: str
    name: str
    description: str
    active: bool
    system: bool
    revision: int


class AccessScopeRequest(CamelModel):
    type: ScopeType
    organization_id: UUID | None = None
    unit_ids: set[UUID] = Field(default_factory=set)


class AccessScopeResponse(CamelModel):
    id: UUID
    type: ScopeType
    organization_id: UUID | None
    unit_ids: frozenset[UUID]


class RoleAssignmentCreateRequest(CamelModel):
    user_id: UUID
    role_id: UUID
    scope: AccessScopeRequest
    effective_from: datetime
    effective_to: datetime | None = None
    reason: str | None = Field(default=None, max_length=1000)


class RoleAssignmentRevokeRequest(CamelModel):
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class RoleAssignmentResponse(CamelModel):
    id: UUID
    user_id: UUID
    role_id: UUID
    scope: AccessScopeResponse
    effective_from: datetime
    effective_to: datetime | None
    created_by: UUID | None
    created_at: datetime
    revoked_at: datetime | None
    revoked_by: UUID | None
    revocation_reason: str | None
    revision: int
