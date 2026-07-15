"""Pure employee aggregates and temporal invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from .enums import (
    AssignmentReviewStatus,
    AssignmentStatus,
    AssignmentType,
    DelegationScopeType,
    DelegationStatus,
    EmploymentStatus,
    PersonStatus,
)
from .errors import EmployeeDomainError, validation_error


def utc_now() -> datetime:
    return datetime.now(UTC)


def ranges_overlap(
    left_from: date,
    left_to: date | None,
    right_from: date,
    right_to: date | None,
) -> bool:
    """Return whether two inclusive, open-ended effective-date ranges overlap."""
    return (left_to is None or right_from <= left_to) and (
        right_to is None or left_from <= right_to
    )


@dataclass(slots=True, kw_only=True)
class Person:
    first_name: str
    last_name: str
    id: UUID = field(default_factory=uuid4)
    middle_name: str | None = None
    display_name: str | None = None
    protected_iin: bytes | None = field(default=None, repr=False)
    birth_date: date | None = field(default=None, repr=False)
    personal_email: str | None = field(default=None, repr=False)
    phone: str | None = field(default=None, repr=False)
    status: PersonStatus = PersonStatus.ACTIVE
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    revision: int = 1

    def __post_init__(self) -> None:
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        if not self.first_name or not self.last_name:
            raise validation_error("First and last names are required.")
        if not self.display_name:
            parts = (self.last_name, self.first_name, self.middle_name or "")
            self.display_name = " ".join(part for part in parts if part).strip()


@dataclass(slots=True, kw_only=True)
class Employee:
    organization_id: UUID
    created_by: UUID
    person_id: UUID
    employee_number: str
    hire_date: date
    id: UUID = field(default_factory=uuid4)
    employment_status: EmploymentStatus = EmploymentStatus.DRAFT
    termination_date: date | None = None
    corporate_email: str | None = None
    active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    revision: int = 1

    def __post_init__(self) -> None:
        self.employee_number = self.employee_number.strip()
        if not self.employee_number:
            raise validation_error("Employee number is required.")
        if self.termination_date is not None and self.termination_date < self.hire_date:
            raise validation_error(
                "Termination date cannot precede hire date.",
                hireDate=self.hire_date.isoformat(),
                terminationDate=self.termination_date.isoformat(),
            )


@dataclass(slots=True, kw_only=True)
class EmployeeAssignment:
    employee_id: UUID
    staffing_slot_id: UUID
    assignment_type: AssignmentType
    full_time_equivalent: Decimal
    effective_from: date
    id: UUID = field(default_factory=uuid4)
    effective_to: date | None = None
    primary: bool = False
    acting: bool = False
    status: AssignmentStatus = AssignmentStatus.PLANNED
    source_document_id: UUID | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    revision: int = 1

    def __post_init__(self) -> None:
        if self.full_time_equivalent <= Decimal("0"):
            raise validation_error("Assignment FTE must be greater than zero.")
        if self.full_time_equivalent > Decimal("1"):
            raise EmployeeDomainError(
                "STAFFING_FTE_EXCEEDED",
                "A single assignment cannot exceed 1.0 FTE.",
                {"fullTimeEquivalent": str(self.full_time_equivalent)},
            )
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise EmployeeDomainError(
                "ASSIGNMENT_DATE_CONFLICT",
                "Assignment end date cannot precede its start date.",
                {},
            )
        if self.assignment_type is AssignmentType.ACTING:
            self.acting = True

    def overlaps(self, other: EmployeeAssignment) -> bool:
        return ranges_overlap(
            self.effective_from,
            self.effective_to,
            other.effective_from,
            other.effective_to,
        )

    def end(self, *, effective_to: date, expected_revision: int) -> None:
        if expected_revision != self.revision:
            raise EmployeeDomainError(
                "CONCURRENCY_CONFLICT",
                "The assignment was changed by another user.",
                {"expectedRevision": expected_revision, "actualRevision": self.revision},
            )
        if effective_to < self.effective_from:
            raise EmployeeDomainError(
                "ASSIGNMENT_DATE_CONFLICT",
                "Assignment end date cannot precede its start date.",
                {},
            )
        if self.status in {
            AssignmentStatus.PENDING_REVIEW,
            AssignmentStatus.CANCELLED,
            AssignmentStatus.ENDED,
        }:
            raise EmployeeDomainError(
                "VERSION_CONFLICT",
                "The assignment cannot be ended in its current state.",
                {"status": self.status.value},
            )
        if self.effective_to is not None and effective_to > self.effective_to:
            raise EmployeeDomainError(
                "ASSIGNMENT_DATE_CONFLICT",
                "An existing assignment end date cannot be extended.",
                {"existingEffectiveTo": self.effective_to.isoformat()},
            )
        self.effective_to = effective_to
        self.status = (
            AssignmentStatus.SCHEDULED_END
            if effective_to > date.today()
            else AssignmentStatus.ENDED
        )
        self.revision += 1
        self.updated_at = utc_now()

    def effective_status(self, at: date | None = None) -> AssignmentStatus:
        on_date = at or date.today()
        if self.status in {
            AssignmentStatus.CANCELLED,
            AssignmentStatus.PENDING_REVIEW,
        }:
            return self.status
        if on_date < self.effective_from:
            return AssignmentStatus.PLANNED
        if self.effective_to is not None and on_date > self.effective_to:
            return AssignmentStatus.ENDED
        return AssignmentStatus.ACTIVE

    def resolve_review(self, *, approved: bool, expected_revision: int) -> None:
        if expected_revision != self.revision:
            raise EmployeeDomainError(
                "CONCURRENCY_CONFLICT",
                "The assignment was changed by another user.",
                {"expectedRevision": expected_revision, "actualRevision": self.revision},
            )
        if self.status is not AssignmentStatus.PENDING_REVIEW:
            raise EmployeeDomainError(
                "VERSION_CONFLICT",
                "The assignment is not awaiting review.",
                {"status": self.status.value},
            )
        today = date.today()
        self.status = (
            AssignmentStatus.CANCELLED
            if not approved
            else AssignmentStatus.ENDED
            if self.effective_to is not None and self.effective_to < today
            else AssignmentStatus.ACTIVE
            if self.effective_from <= today
            else AssignmentStatus.PLANNED
        )
        self.revision += 1
        self.updated_at = utc_now()


@dataclass(slots=True, kw_only=True)
class AssignmentReviewRequest:
    organization_id: UUID
    assignment_id: UUID
    submitted_by: UUID
    submission_reason: str
    id: UUID = field(default_factory=uuid4)
    status: AssignmentReviewStatus = AssignmentReviewStatus.PENDING
    submitted_at: datetime = field(default_factory=utc_now)
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    resolution_reason: str | None = None
    revision: int = 1

    def resolve(
        self,
        *,
        approved: bool,
        actor_id: UUID,
        reason: str,
        expected_revision: int,
    ) -> None:
        if expected_revision != self.revision:
            raise EmployeeDomainError(
                "CONCURRENCY_CONFLICT",
                "The assignment review was changed by another user.",
                {"expectedRevision": expected_revision, "actualRevision": self.revision},
            )
        if self.status is not AssignmentReviewStatus.PENDING:
            raise EmployeeDomainError(
                "VERSION_CONFLICT",
                "The assignment review is no longer pending.",
                {"status": self.status.value},
            )
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise validation_error("A review resolution reason is required.")
        self.status = (
            AssignmentReviewStatus.APPROVED if approved else AssignmentReviewStatus.REJECTED
        )
        self.resolved_by = actor_id
        self.resolved_at = utc_now()
        self.resolution_reason = normalized_reason
        self.revision += 1


@dataclass(slots=True, kw_only=True)
class Delegation:
    delegator_employee_id: UUID
    delegate_employee_id: UUID
    scope_type: DelegationScopeType
    scope_reference: str | None
    delegated_permissions: tuple[str, ...]
    effective_from: datetime
    effective_to: datetime
    reason: str
    created_by: UUID
    id: UUID = field(default_factory=uuid4)
    source_document_id: UUID | None = None
    status: DelegationStatus = DelegationStatus.SCHEDULED
    created_at: datetime = field(default_factory=utc_now)
    revoked_at: datetime | None = None
    revision: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.delegator_employee_id == self.delegate_employee_id:
            raise EmployeeDomainError(
                "DELEGATION_DATE_CONFLICT",
                "Delegator and delegate must be different employees.",
                {},
            )
        if self.effective_to <= self.effective_from:
            raise EmployeeDomainError(
                "DELEGATION_DATE_CONFLICT",
                "Delegation end must be after its start.",
                {},
            )
        if self.effective_from.tzinfo is None or self.effective_to.tzinfo is None:
            raise validation_error("Delegation dates must include a UTC offset.")
        if not self.delegated_permissions:
            raise validation_error("At least one delegated permission is required.")
        self.delegated_permissions = tuple(sorted(set(self.delegated_permissions)))
        self.reason = self.reason.strip()
        if not self.reason:
            raise validation_error("A delegation reason is required.")

    def effective_status(self, at: datetime | None = None) -> DelegationStatus:
        instant = at or utc_now()
        if self.revoked_at is not None or self.status is DelegationStatus.REVOKED:
            return DelegationStatus.REVOKED
        if instant >= self.effective_to:
            return DelegationStatus.EXPIRED
        if instant >= self.effective_from:
            return DelegationStatus.ACTIVE
        return DelegationStatus.SCHEDULED

    def revoke(self, *, revoked_at: datetime, expected_revision: int) -> None:
        if expected_revision != self.revision:
            raise EmployeeDomainError(
                "CONCURRENCY_CONFLICT",
                "The delegation was changed by another user.",
                {"expectedRevision": expected_revision, "actualRevision": self.revision},
            )
        if self.status is DelegationStatus.REVOKED:
            raise EmployeeDomainError(
                "DELEGATION_DATE_CONFLICT", "The delegation is already revoked.", {}
            )
        self.status = DelegationStatus.REVOKED
        self.revoked_at = revoked_at
        self.revision += 1
