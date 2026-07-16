from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.shared.api import CamelModel


class OrganizationBody(CamelModel):
    organization_id: UUID


class RequestCreate(OrganizationBody):
    requesting_unit_id: UUID
    requested_by_employee_id: UUID
    staffing_slot_id: UUID | None = None
    position_definition_id: UUID
    requested_fte: Decimal = Field(gt=0, le=1)
    employment_type: str
    desired_start_date: date
    reason: str = Field(min_length=1)
    responsibilities: str
    requirements: str
    proposed_compensation: dict[str, Any] | None = None


class RequestCorrection(OrganizationBody):
    revision: int = Field(ge=1)
    requesting_unit_id: UUID
    desired_start_date: date
    reason: str = Field(min_length=1)
    responsibilities: str
    requirements: str


class ReviewBody(OrganizationBody):
    revision: int = Field(ge=1)
    decision: Literal["approve", "return", "reject"]
    comment: str = Field(min_length=1)


class StaffingReviewBody(ReviewBody):
    vacant_slot_confirmed: bool
    approved_fte: Decimal | None = None
    budget_confirmed: bool
    compensation_range: dict[str, Any] | None = None


class VacancyCreate(OrganizationBody):
    code: str
    title: str
    description: str = ""
    employment_conditions: dict[str, Any] = Field(default_factory=dict)
    application_deadline: date | None = None


class PublishBody(OrganizationBody):
    revision: int = Field(ge=1)
    channel_id: UUID
    responsible_employee_id: UUID
    external_reference: str | None = None


class CandidateCreate(OrganizationBody):
    first_name: str
    last_name: str
    middle_name: str | None = None
    display_name: str
    personal_email: str | None = None
    phone: str | None = None
    identity: str | None = None
    source: str
    consent_status: Literal["granted", "denied", "withdrawn"]
    retention_until: date | None = None


class CandidateAnonymize(OrganizationBody):
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1)


class ApplicationCreate(OrganizationBody):
    candidate_id: UUID
    vacancy_id: UUID
    source: str


class ScreeningBody(OrganizationBody):
    revision: int = Field(ge=1)
    decision: Literal["advance", "reject"]
    criteria_results: list[dict[str, Any]] = Field(default_factory=list)
    comment: str = ""


class Participant(CamelModel):
    employee_id: UUID
    role: str
    required: bool = True


class InterviewBody(OrganizationBody):
    round_number: int = Field(default=1, ge=1)
    scheduled_at: datetime
    format: str
    location_reference: str | None = None
    participants: list[Participant]


class EvaluationBody(OrganizationBody):
    interviewer_employee_id: UUID
    criteria_results: list[dict[str, Any]]
    recommendation: str
    comment: str = ""


class CommissionDecisionBody(OrganizationBody):
    commission_id: UUID
    decision: Literal[
        "recommended", "reserve", "rejected", "additional_interview_required", "no_decision"
    ]
    comment: str = ""


class OfferCreate(OrganizationBody):
    proposed_conditions: dict[str, Any] = Field(default_factory=dict)
    proposed_start_date: date
    expiration_date: date
    document_id: UUID | None = None


class OfferResponse(OrganizationBody):
    revision: int = Field(ge=1)
    accepted: bool
    reason: str | None = None


class HiringStart(OrganizationBody):
    pass


class HiringComplete(OrganizationBody):
    revision: int = Field(ge=1)
    employee_number: str
    corporate_email: str | None = None
    full_time_equivalent: Decimal = Field(default=Decimal("1"), gt=0, le=1)
    source_document_id: UUID | None = None


class CancelBody(OrganizationBody):
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1)


class ChannelCreate(OrganizationBody):
    code: str
    name: str
    channel_type: str


class CommissionMember(CamelModel):
    employee_id: UUID
    role: str
    conflict_declared: bool = False
    declaration: str | None = None


class CommissionCreate(OrganizationBody):
    code: str
    meeting_at: datetime
    quorum_required: int = Field(ge=1)
    protocol_document_id: UUID | None = None
    members: list[CommissionMember]


class OnboardingTaskCreate(OrganizationBody):
    task_type: str
    assigned_unit_id: UUID | None = None
    assigned_employee_id: UUID | None = None
    due_at: datetime | None = None


class OnboardingTaskComplete(OrganizationBody):
    revision: int = Field(ge=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
