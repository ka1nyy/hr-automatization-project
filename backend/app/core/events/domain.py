"""Application event vocabulary for the transactional outbox."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.shared.identifiers import new_uuid
from app.shared.time import utc_now


class EventName(StrEnum):
    ORGANIZATION_STRUCTURE_PUBLISHED = "organizationStructurePublished"
    ORGANIZATION_UNIT_CHANGED = "organizationUnitChanged"
    STAFFING_SLOT_CREATED = "staffingSlotCreated"
    STAFFING_SLOT_VACATED = "staffingSlotVacated"
    STAFFING_SLOT_CLOSURE_SCHEDULED = "staffingSlotClosureScheduled"
    EMPLOYEE_CREATED = "employeeCreated"
    EMPLOYEE_HIRED = "employeeHired"
    EMPLOYEE_TERMINATED = "employeeTerminated"
    EMPLOYEE_TERMINATION_SCHEDULED = "employeeTerminationScheduled"
    EMPLOYEE_TRANSFERRED = "employeeTransferred"
    EMPLOYEE_ABSENCE_REGISTERED = "employeeAbsenceRegistered"
    EMPLOYEE_ABSENCE_CANCELLED = "employeeAbsenceCancelled"
    EMPLOYEE_ASSIGNMENT_STARTED = "employeeAssignmentStarted"
    EMPLOYEE_ASSIGNMENT_ENDED = "employeeAssignmentEnded"
    EMPLOYEE_ASSIGNMENT_END_SCHEDULED = "employeeAssignmentEndScheduled"
    EMPLOYEE_ASSIGNMENT_REVIEW_REQUESTED = "employeeAssignmentReviewRequested"
    EMPLOYEE_ASSIGNMENT_REVIEW_REJECTED = "employeeAssignmentReviewRejected"
    DELEGATION_STARTED = "delegationStarted"
    DELEGATION_REVOKED = "delegationRevoked"
    ROLE_ASSIGNMENT_CHANGED = "roleAssignmentChanged"
    PROCESS_INSTANCE_STARTED = "processInstanceStarted"
    WORKFLOW_TASK_ASSIGNED = "workflowTaskAssigned"
    WORKFLOW_TASK_COMPLETED = "workflowTaskCompleted"
    PROCESS_INSTANCE_COMPLETED = "processInstanceCompleted"
    PROCESS_INSTANCE_CANCELLED = "processInstanceCancelled"
    RECRUITMENT_REQUEST_SUBMITTED = "recruitmentRequestSubmitted"
    RECRUITMENT_REQUEST_APPROVED = "recruitmentRequestApproved"
    VACANCY_PUBLISHED = "vacancyPublished"
    CANDIDATE_APPLICATION_RECEIVED = "candidateApplicationReceived"
    CANDIDATE_ANONYMIZED = "candidateAnonymized"
    INTERVIEW_SCHEDULED = "interviewScheduled"
    COMMISSION_DECISION_RECORDED = "commissionDecisionRecorded"
    JOB_OFFER_SENT = "jobOfferSent"
    JOB_OFFER_ACCEPTED = "jobOfferAccepted"
    JOB_OFFER_DECLINED = "jobOfferDeclined"
    HIRING_CASE_STARTED = "hiringCaseStarted"
    HIRING_CASE_CANCELLED = "hiringCaseCancelled"
    HIRING_REQUEST_SUBMITTED = "hiringRequestSubmitted"
    HIRING_APPROVAL_DECIDED = "hiringApprovalDecided"
    HIRING_PACKAGE_DISPATCHED = "hiringPackageDispatched"
    HIRING_PACKAGE_ACKNOWLEDGED = "hiringPackageAcknowledged"
    TERMINATION_CASE_STARTED = "terminationCaseStarted"
    TERMINATION_CASE_APPROVED = "terminationCaseApproved"
    TERMINATION_SCHEDULED = "terminationScheduled"
    TERMINATION_ORDER_REGISTERED = "terminationOrderRegistered"
    OFFBOARDING_TASK_ASSIGNED = "offboardingTaskAssigned"
    EMPLOYEE_TERMINATION_EFFECTIVE = "employeeTerminationEffective"
    TERMINATION_CASE_COMPLETED = "terminationCaseCompleted"
    TERMINATION_CASE_CANCELLED = "terminationCaseCancelled"
    LEAVE_REQUEST_SUBMITTED = "leaveRequestSubmitted"
    LEAVE_REQUEST_APPROVED = "leaveRequestApproved"
    LEAVE_REQUEST_REJECTED = "leaveRequestRejected"
    LEAVE_REQUEST_CANCELLED = "leaveRequestCancelled"
    BUSINESS_TRIP_SUBMITTED = "businessTripSubmitted"
    BUSINESS_TRIP_APPROVED = "businessTripApproved"
    BUSINESS_TRIP_REGISTERED = "businessTripRegistered"
    BUSINESS_TRIP_REJECTED = "businessTripRejected"
    BUSINESS_TRIP_CANCELLED = "businessTripCancelled"


@dataclass(frozen=True, slots=True)
class ApplicationEvent:
    name: EventName
    aggregate_type: str
    aggregate_id: UUID
    payload: Mapping[str, Any]
    id: UUID = field(default_factory=new_uuid)
    occurred_at: datetime = field(default_factory=utc_now)
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    event: ApplicationEvent
    attempts: int
    available_at: datetime
