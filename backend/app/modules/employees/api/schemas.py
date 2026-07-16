"""Versioned HTTP DTOs. These never expose persistence objects."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..application.commands import (
    CreateAssignmentCommand,
    CreateDelegationCommand,
    CreateEmployeeCommand,
    EndAssignmentCommand,
    ReviewAssignmentCommand,
    RevokeDelegationCommand,
    UpdateEmployeeCommand,
)
from ..application.functions import FunctionDescriptor
from ..application.views import EmployeeDetails
from ..domain.entities import Delegation, EmployeeAssignment
from ..domain.enums import AssignmentType, DelegationScopeType, EmploymentStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


class Meta(ApiModel):
    request_id: UUID
    page: int | None = None
    page_size: int | None = None
    total: int | None = None


class Envelope[T](ApiModel):
    data: T
    meta: Meta


class CreateEmployeeRequest(ApiModel):
    first_name: str = Field(min_length=1, max_length=160)
    last_name: str = Field(min_length=1, max_length=160)
    employee_number: str = Field(min_length=1, max_length=64)
    hire_date: date
    middle_name: str | None = Field(default=None, max_length=160)
    display_name: str | None = Field(default=None, max_length=500)
    iin: str | None = Field(default=None, min_length=12, max_length=12, repr=False)
    birth_date: date | None = Field(default=None, repr=False)
    personal_email: str | None = Field(default=None, max_length=320, repr=False)
    phone: str | None = Field(default=None, max_length=80, repr=False)
    corporate_email: str | None = Field(default=None, max_length=320)
    employment_status: EmploymentStatus = EmploymentStatus.DRAFT

    def to_command(self) -> CreateEmployeeCommand:
        return CreateEmployeeCommand(**self.model_dump())


class UpdateEmployeeRequest(ApiModel):
    revision: int = Field(ge=1)
    corporate_email: str | None = Field(default=None, max_length=320)
    employment_status: EmploymentStatus | None = None
    active: bool | None = None
    termination_date: date | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=160)
    last_name: str | None = Field(default=None, min_length=1, max_length=160)
    middle_name: str | None = Field(default=None, max_length=160)
    display_name: str | None = Field(default=None, max_length=500)
    personal_email: str | None = Field(default=None, max_length=320, repr=False)
    phone: str | None = Field(default=None, max_length=80, repr=False)

    def to_command(self, employee_id: UUID) -> UpdateEmployeeCommand:
        return UpdateEmployeeCommand(employee_id=employee_id, **self.model_dump())


class AssignmentResponse(ApiModel):
    id: UUID
    employee_id: UUID
    staffing_slot_id: UUID
    assignment_type: AssignmentType
    full_time_equivalent: Decimal
    effective_from: date
    effective_to: date | None
    primary: bool
    acting: bool
    status: str
    source_document_id: UUID | None
    revision: int

    @classmethod
    def from_domain(cls, assignment: EmployeeAssignment) -> AssignmentResponse:
        return cls(
            id=assignment.id,
            employee_id=assignment.employee_id,
            staffing_slot_id=assignment.staffing_slot_id,
            assignment_type=assignment.assignment_type,
            full_time_equivalent=assignment.full_time_equivalent,
            effective_from=assignment.effective_from,
            effective_to=assignment.effective_to,
            primary=assignment.primary,
            acting=assignment.acting,
            status=assignment.effective_status().value,
            source_document_id=assignment.source_document_id,
            revision=assignment.revision,
        )


class EmployeeResponse(ApiModel):
    id: UUID
    organization_id: UUID
    created_by: UUID
    person_id: UUID
    employee_number: str
    first_name: str
    last_name: str
    middle_name: str | None
    display_name: str
    employment_status: EmploymentStatus
    hire_date: date
    termination_date: date | None
    corporate_email: str | None
    active: bool
    revision: int
    assignments: list[AssignmentResponse]
    iin: str | None = None
    birth_date: date | None = None
    personal_email: str | None = None
    phone: str | None = None

    @classmethod
    def from_details(
        cls, details: EmployeeDetails, *, include_sensitive: bool = False
    ) -> EmployeeResponse:
        employee = details.employee
        person = details.person
        return cls(
            id=employee.id,
            organization_id=employee.organization_id,
            created_by=employee.created_by,
            person_id=person.id,
            employee_number=employee.employee_number,
            first_name=person.first_name,
            last_name=person.last_name,
            middle_name=person.middle_name,
            display_name=person.display_name or "",
            employment_status=employee.employment_status,
            hire_date=employee.hire_date,
            termination_date=employee.termination_date,
            corporate_email=employee.corporate_email,
            active=employee.active,
            revision=employee.revision,
            assignments=[AssignmentResponse.from_domain(item) for item in details.assignments],
            iin=details.revealed_iin if include_sensitive else None,
            birth_date=person.birth_date if include_sensitive else None,
            personal_email=person.personal_email if include_sensitive else None,
            phone=person.phone if include_sensitive else None,
        )


class CreateAssignmentRequest(ApiModel):
    employee_id: UUID
    staffing_slot_id: UUID
    assignment_type: AssignmentType
    full_time_equivalent: Decimal = Field(gt=0, le=1, max_digits=5, decimal_places=2)
    effective_from: date
    effective_to: date | None = None
    primary: bool = False
    acting: bool = False
    source_document_id: UUID | None = None

    def to_command(self) -> CreateAssignmentCommand:
        return CreateAssignmentCommand(**self.model_dump())


class EndAssignmentRequest(ApiModel):
    effective_to: date
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)

    def to_command(self, assignment_id: UUID) -> EndAssignmentCommand:
        return EndAssignmentCommand(assignment_id=assignment_id, **self.model_dump())


class ReviewAssignmentRequest(ApiModel):
    approved: bool
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)

    def to_command(self, assignment_id: UUID) -> ReviewAssignmentCommand:
        return ReviewAssignmentCommand(assignment_id=assignment_id, **self.model_dump())


class CreateDelegationRequest(ApiModel):
    delegator_employee_id: UUID
    delegate_employee_id: UUID
    scope_type: DelegationScopeType
    scope_reference: str | None = Field(default=None, max_length=500)
    delegated_permissions: tuple[str, ...] = Field(min_length=1)
    effective_from: datetime
    effective_to: datetime
    reason: str = Field(min_length=1, max_length=2000)
    source_document_id: UUID | None = None

    def to_command(self) -> CreateDelegationCommand:
        return CreateDelegationCommand(**self.model_dump())


class RevokeDelegationRequest(ApiModel):
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)

    def to_command(self, delegation_id: UUID) -> RevokeDelegationCommand:
        return RevokeDelegationCommand(delegation_id=delegation_id, **self.model_dump())


class DelegationResponse(ApiModel):
    id: UUID
    delegator_employee_id: UUID
    delegate_employee_id: UUID
    scope_type: DelegationScopeType
    scope_reference: str | None
    delegated_permissions: list[str]
    effective_from: datetime
    effective_to: datetime
    reason: str
    source_document_id: UUID | None
    status: str
    created_by: UUID
    created_at: datetime
    revoked_at: datetime | None
    revision: int

    @classmethod
    def from_domain(cls, delegation: Delegation) -> DelegationResponse:
        return cls(
            id=delegation.id,
            delegator_employee_id=delegation.delegator_employee_id,
            delegate_employee_id=delegation.delegate_employee_id,
            scope_type=delegation.scope_type,
            scope_reference=delegation.scope_reference,
            delegated_permissions=list(delegation.delegated_permissions),
            effective_from=delegation.effective_from,
            effective_to=delegation.effective_to,
            reason=delegation.reason,
            source_document_id=delegation.source_document_id,
            status=delegation.effective_status().value,
            created_by=delegation.created_by,
            created_at=delegation.created_at,
            revoked_at=delegation.revoked_at,
            revision=delegation.revision,
        )


class FunctionDescriptorResponse(ApiModel):
    key: str
    title: str
    description: str
    scope: str

    @classmethod
    def from_descriptor(cls, descriptor: FunctionDescriptor) -> FunctionDescriptorResponse:
        return cls(
            key=descriptor.key,
            title=descriptor.title,
            description=descriptor.description,
            scope=descriptor.scope.value,
        )


class InvokeFunctionRequest(ApiModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class ErrorBody(ApiModel):
    code: str
    message: str
    details: dict[str, Any]
    request_id: UUID


class ErrorEnvelope(ApiModel):
    error: ErrorBody
