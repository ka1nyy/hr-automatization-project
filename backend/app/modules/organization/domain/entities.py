"""Pure dataclass entities and invariants for organization management."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.modules.organization.domain.enums import (
    EmploymentType,
    OrganizationStatus,
    ReviewRequestStatus,
    StaffingSlotStatus,
    StructureVersionStatus,
)
from app.modules.organization.domain.errors import (
    ConcurrencyConflictError,
    InvalidRelationshipError,
    OrganizationError,
    StaffingFteExceededError,
    StaffingSlotNotAvailableError,
    StructureNotEditableError,
    VersionConflictError,
)

JsonObject = dict[str, Any]


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalized_code(value: str) -> str:
    code = value.strip().upper()
    if not code:
        raise OrganizationError(
            "VALIDATION_FAILED",
            "code must not be empty.",
            details={"field": "code"},
        )
    if len(code) > 64:
        raise OrganizationError(
            "VALIDATION_FAILED",
            "code must be at most 64 characters.",
            details={"field": "code", "maxLength": 64},
        )
    return code


def non_empty_name(value: str, *, field_name: str = "name") -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise OrganizationError(
            "VALIDATION_FAILED",
            f"{field_name} must not be empty.",
            details={"field": field_name},
        )
    if len(normalized) > 255:
        raise OrganizationError(
            "VALIDATION_FAILED",
            f"{field_name} must be at most 255 characters.",
            details={"field": field_name, "maxLength": 255},
        )
    return normalized


def validate_date_range(effective_from: date | None, effective_to: date | None) -> None:
    if effective_from is not None and effective_to is not None and effective_to < effective_from:
        raise OrganizationError(
            "VALIDATION_FAILED",
            "effectiveTo must be on or after effectiveFrom.",
            details={"field": "effectiveTo"},
        )


@dataclass(slots=True)
class RevisionedEntity:
    revision: int = 1

    def assert_revision(self, expected_revision: int, entity_name: str, entity_id: UUID) -> None:
        if self.revision != expected_revision:
            raise ConcurrencyConflictError(entity_name, entity_id, expected_revision)

    def bump_revision(self) -> int:
        previous = self.revision
        self.revision += 1
        return previous


@dataclass(slots=True)
class Organization:
    id: UUID
    code: str
    legal_name: str
    display_name: str
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.code = normalized_code(self.code)
        self.legal_name = non_empty_name(self.legal_name, field_name="legal_name")
        self.display_name = non_empty_name(self.display_name, field_name="display_name")


@dataclass(slots=True)
class OrganizationStructureVersion(RevisionedEntity):
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID = field(default_factory=uuid4)
    version_number: int = 1
    name: str = "Draft"
    status: StructureVersionStatus = StructureVersionStatus.DRAFT
    based_on_version_id: UUID | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    created_by: UUID = field(default_factory=uuid4)
    published_by: UUID | None = None
    created_at: datetime = field(default_factory=utc_now)
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        self.name = non_empty_name(self.name)
        if self.version_number < 1:
            raise OrganizationError(
                "VALIDATION_FAILED",
                "versionNumber must be positive.",
                details={"field": "versionNumber"},
            )
        validate_date_range(self.effective_from, self.effective_to)

    def ensure_editable(self) -> None:
        if self.status is not StructureVersionStatus.DRAFT:
            raise StructureNotEditableError(self.id, self.status.value)

    def touch(self, expected_revision: int) -> int:
        self.ensure_editable()
        self.assert_revision(expected_revision, "organizationStructureVersion", self.id)
        return self.bump_revision()

    def submit_for_review(self, expected_revision: int) -> int:
        self.ensure_editable()
        self.assert_revision(expected_revision, "organizationStructureVersion", self.id)
        previous = self.bump_revision()
        self.status = StructureVersionStatus.IN_REVIEW
        return previous

    def return_for_correction(self, expected_revision: int) -> int:
        if self.status is not StructureVersionStatus.IN_REVIEW:
            raise VersionConflictError(
                "Only a structure in review can be returned for correction.",
                details={"versionId": str(self.id), "status": self.status.value},
            )
        self.assert_revision(expected_revision, "organizationStructureVersion", self.id)
        previous = self.bump_revision()
        self.status = StructureVersionStatus.DRAFT
        return previous

    def publish(
        self,
        *,
        expected_revision: int,
        effective_from: date,
        actor_id: UUID,
        now: datetime | None = None,
    ) -> int:
        if self.status not in {StructureVersionStatus.DRAFT, StructureVersionStatus.IN_REVIEW}:
            raise VersionConflictError(
                "Only a draft or reviewed structure can be published.",
                details={"versionId": str(self.id), "status": self.status.value},
            )
        self.assert_revision(expected_revision, "organizationStructureVersion", self.id)
        previous = self.bump_revision()
        self.status = StructureVersionStatus.PUBLISHED
        self.effective_from = effective_from
        self.published_by = actor_id
        self.published_at = now or utc_now()
        return previous


@dataclass(slots=True)
class OrganizationUnitType(RevisionedEntity):
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID = field(default_factory=uuid4)
    code: str = "UNIT"
    name: str = "Unit"
    description: str | None = None
    active: bool = True
    allowed_parent_type_ids: tuple[UUID, ...] = ()
    custom_fields_schema: JsonObject = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.code = normalized_code(self.code)
        self.name = non_empty_name(self.name)


@dataclass(slots=True)
class OrganizationRelationshipType(RevisionedEntity):
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID = field(default_factory=uuid4)
    code: str = "RELATIONSHIP"
    name: str = "Relationship"
    description: str | None = None
    directed: bool = True
    prevents_cycles: bool = False
    allow_self_link: bool = False
    active: bool = True
    metadata_schema: JsonObject = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.code = normalized_code(self.code)
        self.name = non_empty_name(self.name)


@dataclass(slots=True)
class OrganizationPolicy(RevisionedEntity):
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID = field(default_factory=uuid4)
    structure_version_id: UUID | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    managers_can_create_employee_drafts: bool = False
    managers_can_assign_existing_employees: bool = False
    manager_changes_require_hr_approval: bool = True
    managers_can_create_staffing_slots: bool = False
    staffing_changes_require_finance_review: bool = True
    structure_publish_requires_review: bool = True
    allow_multiple_unit_heads: bool = False
    allow_cross_unit_relationships: bool = True
    created_by: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        validate_date_range(self.effective_from, self.effective_to)

    def copy_for_version(self, version_id: UUID, actor_id: UUID) -> OrganizationPolicy:
        return replace(
            self,
            id=uuid4(),
            structure_version_id=version_id,
            revision=1,
            created_by=actor_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )


@dataclass(slots=True)
class StructureReviewRequest(RevisionedEntity):
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID = field(default_factory=uuid4)
    structure_version_id: UUID = field(default_factory=uuid4)
    status: ReviewRequestStatus = ReviewRequestStatus.PENDING
    submitted_by: UUID = field(default_factory=uuid4)
    submitted_at: datetime = field(default_factory=utc_now)
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    submission_reason: str | None = None
    resolution_reason: str | None = None

    def approve(self, actor_id: UUID, reason: str, expected_revision: int) -> int:
        self._ensure_pending()
        self.assert_revision(expected_revision, "structureReviewRequest", self.id)
        previous = self.bump_revision()
        self.status = ReviewRequestStatus.APPROVED
        self.resolved_by = actor_id
        self.resolved_at = utc_now()
        self.resolution_reason = non_empty_name(reason, field_name="reason")
        return previous

    def return_for_correction(self, actor_id: UUID, reason: str, expected_revision: int) -> int:
        self._ensure_pending()
        self.assert_revision(expected_revision, "structureReviewRequest", self.id)
        previous = self.bump_revision()
        self.status = ReviewRequestStatus.RETURNED
        self.resolved_by = actor_id
        self.resolved_at = utc_now()
        self.resolution_reason = non_empty_name(reason, field_name="reason")
        return previous

    def _ensure_pending(self) -> None:
        if self.status is not ReviewRequestStatus.PENDING:
            raise VersionConflictError(
                "The review request is no longer pending.",
                details={"reviewRequestId": str(self.id), "status": self.status.value},
            )


@dataclass(slots=True)
class OrganizationUnit(RevisionedEntity):
    id: UUID = field(default_factory=uuid4)
    structure_version_id: UUID = field(default_factory=uuid4)
    stable_key: UUID = field(default_factory=uuid4)
    code: str = "UNIT"
    name: str = "Unit"
    short_name: str | None = None
    unit_type_id: UUID = field(default_factory=uuid4)
    parent_unit_id: UUID | None = None
    sort_order: int = 0
    description: str | None = None
    active: bool = True
    custom_fields: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.code = normalized_code(self.code)
        self.name = non_empty_name(self.name)
        if self.short_name is not None:
            self.short_name = non_empty_name(self.short_name, field_name="short_name")
        if self.sort_order < 0:
            raise OrganizationError(
                "VALIDATION_FAILED",
                "sortOrder must not be negative.",
                details={"field": "sortOrder"},
            )

    def rename(self, name: str, short_name: str | None, expected_revision: int) -> int:
        self.assert_revision(expected_revision, "organizationUnit", self.id)
        previous = self.bump_revision()
        self.name = non_empty_name(name)
        self.short_name = (
            non_empty_name(short_name, field_name="short_name") if short_name is not None else None
        )
        return previous


@dataclass(slots=True)
class OrganizationRelationship(RevisionedEntity):
    id: UUID = field(default_factory=uuid4)
    structure_version_id: UUID = field(default_factory=uuid4)
    relationship_type_id: UUID = field(default_factory=uuid4)
    source_unit_id: UUID = field(default_factory=uuid4)
    target_unit_id: UUID = field(default_factory=uuid4)
    effective_from: date | None = None
    effective_to: date | None = None
    metadata: JsonObject = field(default_factory=dict)
    active: bool = True

    def __post_init__(self) -> None:
        validate_date_range(self.effective_from, self.effective_to)

    def ensure_not_self_link(self, relationship_type: OrganizationRelationshipType) -> None:
        if self.source_unit_id == self.target_unit_id and not relationship_type.allow_self_link:
            raise InvalidRelationshipError(
                "A relationship cannot link a unit to itself.",
                details={"unitId": str(self.source_unit_id)},
            )


@dataclass(slots=True)
class PositionDefinition(RevisionedEntity):
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID = field(default_factory=uuid4)
    code: str = "POSITION"
    name: str = "Position"
    description: str | None = None
    job_family: str | None = None
    grade: str | None = None
    active: bool = True
    custom_fields: JsonObject = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.code = normalized_code(self.code)
        self.name = non_empty_name(self.name)


@dataclass(slots=True)
class StaffingSlot(RevisionedEntity):
    id: UUID = field(default_factory=uuid4)
    structure_version_id: UUID = field(default_factory=uuid4)
    stable_key: UUID = field(default_factory=uuid4)
    organization_unit_id: UUID = field(default_factory=uuid4)
    position_definition_id: UUID = field(default_factory=uuid4)
    reports_to_slot_id: UUID | None = None
    head_of_unit: bool = False
    full_time_equivalent: Decimal = Decimal("1.00")
    employment_type: EmploymentType = EmploymentType.PERMANENT
    status: StaffingSlotStatus = StaffingSlotStatus.PLANNED
    effective_from: date | None = None
    effective_to: date | None = None
    custom_fields: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate_fte()
        validate_date_range(self.effective_from, self.effective_to)

    def validate_fte(self) -> None:
        if self.full_time_equivalent <= Decimal("0") or self.full_time_equivalent > Decimal("1"):
            raise StaffingFteExceededError(str(self.full_time_equivalent))

    def close(self, *, effective_to: date, expected_revision: int) -> int:
        self.assert_revision(expected_revision, "staffingSlot", self.id)
        if self.status in {StaffingSlotStatus.CLOSING, StaffingSlotStatus.CLOSED}:
            raise StaffingSlotNotAvailableError(self.id, self.status.value)
        if self.effective_from is not None and effective_to < self.effective_from:
            raise OrganizationError(
                "VALIDATION_FAILED",
                "effectiveTo must be on or after effectiveFrom.",
                details={"field": "effectiveTo"},
            )
        previous = self.bump_revision()
        self.status = (
            StaffingSlotStatus.CLOSING if effective_to > date.today() else StaffingSlotStatus.CLOSED
        )
        self.effective_to = effective_to
        return previous

    def effective_status(self, on_date: date | None = None) -> StaffingSlotStatus:
        effective_on = on_date or date.today()
        if (
            self.status is StaffingSlotStatus.CLOSING
            and self.effective_to is not None
            and self.effective_to <= effective_on
        ):
            return StaffingSlotStatus.CLOSED
        return self.status
