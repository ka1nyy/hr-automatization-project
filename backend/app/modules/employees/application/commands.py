"""Stable input commands for employee use cases."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from ..domain.enums import AbsenceType, AssignmentType, DelegationScopeType, EmploymentStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateEmployeeCommand:
    first_name: str
    last_name: str
    employee_number: str
    hire_date: date
    middle_name: str | None = None
    display_name: str | None = None
    iin: str | None = None
    birth_date: date | None = None
    personal_email: str | None = None
    phone: str | None = None
    corporate_email: str | None = None
    employment_status: EmploymentStatus = EmploymentStatus.DRAFT


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateEmployeeCommand:
    employee_id: UUID
    revision: int
    corporate_email: str | None = None
    employment_status: EmploymentStatus | None = None
    active: bool | None = None
    termination_date: date | None = None
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    display_name: str | None = None
    personal_email: str | None = None
    phone: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class HireEmployeeCommand:
    first_name: str
    last_name: str
    employee_number: str
    hire_date: date
    middle_name: str | None = None
    display_name: str | None = None
    iin: str | None = None
    birth_date: date | None = None
    personal_email: str | None = None
    phone: str | None = None
    corporate_email: str | None = None
    staffing_slot_id: UUID | None = None
    assignment_type: AssignmentType = AssignmentType.PERMANENT
    full_time_equivalent: Decimal = Decimal("1.00")


@dataclass(frozen=True, slots=True, kw_only=True)
class TerminateEmployeeCommand:
    employee_id: UUID
    termination_date: date
    reason: str
    revision: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TransferEmployeeCommand:
    employee_id: UUID
    staffing_slot_id: UUID
    effective_from: date
    reason: str
    assignment_type: AssignmentType = AssignmentType.PERMANENT
    full_time_equivalent: Decimal = Decimal("1.00")


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateAbsenceCommand:
    employee_id: UUID
    absence_type: AbsenceType
    date_from: date
    date_to: date
    reason: str
    details: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CancelAbsenceCommand:
    employee_id: UUID
    absence_id: UUID
    reason: str
    revision: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateAssignmentCommand:
    employee_id: UUID
    staffing_slot_id: UUID
    assignment_type: AssignmentType
    full_time_equivalent: Decimal
    effective_from: date
    effective_to: date | None = None
    primary: bool = False
    acting: bool = False
    source_document_id: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EndAssignmentCommand:
    assignment_id: UUID
    effective_to: date
    revision: int
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewAssignmentCommand:
    assignment_id: UUID
    approved: bool
    revision: int
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateDelegationCommand:
    delegator_employee_id: UUID
    delegate_employee_id: UUID
    scope_type: DelegationScopeType
    scope_reference: str | None
    delegated_permissions: tuple[str, ...]
    effective_from: datetime
    effective_to: datetime
    reason: str
    source_document_id: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RevokeDelegationCommand:
    delegation_id: UUID
    revision: int
    reason: str
