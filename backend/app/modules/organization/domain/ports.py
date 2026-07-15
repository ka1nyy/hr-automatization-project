"""Repository, transaction, authorization, and integration ports."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, Self
from uuid import UUID

from app.modules.organization.domain.entities import (
    Organization,
    OrganizationPolicy,
    OrganizationRelationship,
    OrganizationRelationshipType,
    OrganizationStructureVersion,
    OrganizationUnit,
    OrganizationUnitType,
    PositionDefinition,
    StaffingSlot,
    StructureReviewRequest,
)
from app.modules.organization.domain.enums import StaffingSlotStatus, StructureVersionStatus
from app.modules.organization.domain.validation import ValidationIssue


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: UUID
    organization_id: UUID | None
    permissions: frozenset[str] = frozenset()
    scoped_unit_ids: frozenset[UUID] = frozenset()
    request_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AuditRecord:
    id: UUID
    organization_id: UUID
    actor_id: UUID
    action: str
    entity_type: str
    entity_id: UUID
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str | None
    request_id: UUID | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    id: UUID
    organization_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    payload: dict[str, Any]
    occurred_at: datetime


class OrganizationRepository(Protocol):
    async def get(self, organization_id: UUID) -> Organization | None: ...

    async def list(self) -> Sequence[Organization]: ...

    async def add(self, organization: Organization) -> None: ...


class StructureVersionRepository(Protocol):
    async def get(self, version_id: UUID) -> OrganizationStructureVersion | None: ...

    async def list(
        self,
        organization_id: UUID,
        *,
        status: StructureVersionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
        sort: str = "-versionNumber",
    ) -> Sequence[OrganizationStructureVersion]: ...

    async def count(
        self, organization_id: UUID, *, status: StructureVersionStatus | None = None
    ) -> int: ...

    async def get_active(
        self, organization_id: UUID, *, on_date: date
    ) -> OrganizationStructureVersion | None: ...

    async def next_version_number(self, organization_id: UUID) -> int: ...

    async def add(self, version: OrganizationStructureVersion) -> None: ...

    async def save(
        self, version: OrganizationStructureVersion, *, expected_revision: int
    ) -> None: ...


class UnitTypeRepository(Protocol):
    async def get(self, type_id: UUID) -> OrganizationUnitType | None: ...

    async def list(
        self, organization_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationUnitType]: ...

    async def add(self, unit_type: OrganizationUnitType) -> None: ...

    async def save(self, unit_type: OrganizationUnitType, *, expected_revision: int) -> None: ...


class RelationshipTypeRepository(Protocol):
    async def get(self, type_id: UUID) -> OrganizationRelationshipType | None: ...

    async def list(
        self, organization_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationRelationshipType]: ...

    async def add(self, relationship_type: OrganizationRelationshipType) -> None: ...

    async def save(
        self, relationship_type: OrganizationRelationshipType, *, expected_revision: int
    ) -> None: ...


class PolicyRepository(Protocol):
    async def get_for_version(self, version_id: UUID) -> OrganizationPolicy | None: ...

    async def get_default(self, organization_id: UUID) -> OrganizationPolicy | None: ...

    async def add(self, policy: OrganizationPolicy) -> None: ...

    async def save(self, policy: OrganizationPolicy, *, expected_revision: int) -> None: ...


class ReviewRequestRepository(Protocol):
    async def get(self, review_request_id: UUID) -> StructureReviewRequest | None: ...

    async def get_pending_for_version(self, version_id: UUID) -> StructureReviewRequest | None: ...

    async def list_for_version(self, version_id: UUID) -> Sequence[StructureReviewRequest]: ...

    async def add(self, review_request: StructureReviewRequest) -> None: ...

    async def save(
        self, review_request: StructureReviewRequest, *, expected_revision: int
    ) -> None: ...


class UnitRepository(Protocol):
    async def get(self, unit_id: UUID) -> OrganizationUnit | None: ...

    async def list_by_version(
        self, version_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationUnit]: ...

    async def add(self, unit: OrganizationUnit) -> None: ...

    async def save(self, unit: OrganizationUnit, *, expected_revision: int) -> None: ...


class RelationshipRepository(Protocol):
    async def get(self, relationship_id: UUID) -> OrganizationRelationship | None: ...

    async def list_by_version(
        self, version_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationRelationship]: ...

    async def add(self, relationship: OrganizationRelationship) -> None: ...

    async def save(
        self, relationship: OrganizationRelationship, *, expected_revision: int
    ) -> None: ...


class PositionRepository(Protocol):
    async def get(self, position_id: UUID) -> PositionDefinition | None: ...

    async def list(
        self,
        organization_id: UUID,
        *,
        include_inactive: bool = False,
        offset: int = 0,
        limit: int = 100,
        sort: str = "name",
    ) -> Sequence[PositionDefinition]: ...

    async def count(self, organization_id: UUID, *, include_inactive: bool = False) -> int: ...

    async def add(self, position: PositionDefinition) -> None: ...

    async def save(self, position: PositionDefinition, *, expected_revision: int) -> None: ...


class StaffingRepository(Protocol):
    async def get(self, slot_id: UUID) -> StaffingSlot | None: ...

    async def list(
        self,
        organization_id: UUID,
        *,
        version_id: UUID | None = None,
        unit_id: UUID | None = None,
        status: StaffingSlotStatus | None = None,
        offset: int = 0,
        limit: int = 100,
        sort: str = "organizationUnitId",
    ) -> Sequence[StaffingSlot]: ...

    async def count(
        self,
        organization_id: UUID,
        *,
        version_id: UUID | None = None,
        unit_id: UUID | None = None,
        status: StaffingSlotStatus | None = None,
    ) -> int: ...

    async def list_by_version(self, version_id: UUID) -> Sequence[StaffingSlot]: ...

    async def add(self, slot: StaffingSlot) -> None: ...

    async def save(self, slot: StaffingSlot, *, expected_revision: int) -> None: ...


class AuditRepository(Protocol):
    async def add(self, record: AuditRecord) -> None: ...


class OutboxRepository(Protocol):
    async def add(self, record: OutboxRecord) -> None: ...


class OrganizationUnitOfWork(Protocol):
    organizations: OrganizationRepository
    versions: StructureVersionRepository
    unit_types: UnitTypeRepository
    relationship_types: RelationshipTypeRepository
    policies: PolicyRepository
    review_requests: ReviewRequestRepository
    units: UnitRepository
    relationships: RelationshipRepository
    positions: PositionRepository
    staffing: StaffingRepository
    audit: AuditRepository
    outbox: OutboxRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None: ...

    async def flush(self) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class OrganizationUnitOfWorkFactory(Protocol):
    def __call__(self) -> OrganizationUnitOfWork: ...


class OrganizationAuthorizationPort(Protocol):
    async def require(
        self,
        actor: Actor,
        permission: str,
        organization_id: UUID,
        *,
        unit_id: UUID | None = None,
    ) -> None: ...


class ExternalStructureValidationPort(Protocol):
    """Lets employee/delegation modules contribute publication validation issues."""

    async def validate_structure_version(
        self, version_id: UUID, *, effective_from: date | None = None
    ) -> Sequence[ValidationIssue]: ...


class NullExternalStructureValidationPort:
    async def validate_structure_version(
        self, version_id: UUID, *, effective_from: date | None = None
    ) -> Sequence[ValidationIssue]:
        del version_id, effective_from
        return ()
