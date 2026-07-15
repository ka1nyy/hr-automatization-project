"""Stable frontend-facing DTOs for operational and HR workflows."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.shared.api import CamelModel

Priority = Literal["normal", "high", "urgent"]
TaskState = Literal["available", "claimed", "completed", "overdue"]
ProcessState = Literal["published", "draft", "incident"]
CorrespondenceStatus = Literal[
    "draft",
    "registered",
    "resolution",
    "execution",
    "approval",
    "signature",
    "dispatch",
    "completed",
]
LeaveStatus = Literal["pending_manager", "hr_review", "approved", "rejected"]


class AttachmentDto(CamelModel):
    id: str
    name: str
    size: str
    kind: Literal["scan", "attachment", "response"]


class AuditEntryDto(CamelModel):
    id: str
    at: datetime
    actor: str
    action: str
    detail: str


class CorrespondenceDto(CamelModel):
    id: UUID
    number: str
    sender: str
    sender_number: str
    sender_date: date
    received_at: datetime
    subject: str
    summary: str
    document_type: str
    channel: str
    department: str
    executive: str
    executor: str
    due_date: date
    priority: Priority
    status: CorrespondenceStatus
    workflow_step: str
    confidentiality: Literal["public", "internal", "restricted"]
    response_required: bool
    attachments: list[AttachmentDto]
    tags: list[str]
    audit: list[AuditEntryDto]


class IncomingLetterRequest(CamelModel):
    sender: str = Field(min_length=2, max_length=300)
    sender_type: str = Field(min_length=1, max_length=80)
    sender_number: str = Field(min_length=1, max_length=120)
    sender_date: date
    channel: str = Field(min_length=1, max_length=80)
    document_type: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=3, max_length=500)
    summary: str = Field(min_length=3, max_length=10_000)
    language: str = Field(min_length=2, max_length=16)
    page_count: int = Field(ge=1, le=10_000)
    confidentiality: Literal["public", "internal", "restricted"]
    priority: Priority
    response_required: bool
    due_date: date
    department: str = Field(min_length=1, max_length=240)
    executive: str = Field(min_length=1, max_length=240)
    notes: str = Field(default="", max_length=10_000)


class WorkTaskDto(CamelModel):
    id: UUID
    title: str
    document_number: str
    process: str
    role: str
    department: str
    due_date: date
    priority: Priority
    state: TaskState
    assignee: str | None = None


class ProcessDefinitionDto(CamelModel):
    id: str
    name: str
    version: int
    state: ProcessState
    active_instances: int
    owner: str
    updated_at: datetime
    steps: list[str]


class DashboardDto(CamelModel):
    incoming_today: int
    awaiting_resolution: int
    active_tasks: int
    overdue: int
    signature_queue: int
    dispatch_queue: int


class CreateLeaveRequest(CamelModel):
    employee_id: UUID
    leave_type: str = Field(min_length=2, max_length=160)
    start_date: date
    end_date: date
    comment: str = Field(default="", max_length=5_000)
    substitute: str = Field(min_length=2, max_length=300)


class ReviewRequest(CamelModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(default="", max_length=2_000)


class LeaveRequestDto(CamelModel):
    id: UUID
    employee_id: UUID
    employee_name: str
    leave_type: str
    start_date: date
    end_date: date
    days: int
    comment: str
    substitute: str
    status: LeaveStatus
    document_number: str
    workflow_step: str
    created_at: datetime
    audit: list[AuditEntryDto]


class HrEmployeeDto(CamelModel):
    id: UUID
    employee_number: str
    full_name: str
    initials: str
    position: str
    department: str
    manager: str | None
    work_email: str
    phone: str
    start_date: date
    location: str
    status: Literal["active", "probation", "on_leave", "sick_leave"]
    availability: Literal["available", "away", "remote"]
    employment_type: str
    contract_end: date | None
    probation_end: date | None
    leave_balance: int
    personnel_file_completeness: int
    salary: int
    currency: Literal["KZT"] = "KZT"
    skills: list[str]


class DirectoryEmployeeDto(CamelModel):
    id: UUID
    name: str
    initials: str
    role: str
    department: str
    candidate_groups: list[str]
    status: Literal["active", "acting", "delegated"]


class HrOverviewDto(CamelModel):
    total_employees: int
    active_employees: int
    on_probation: int
    on_leave: int
    on_sick_leave: int
    on_business_trip: int
    onboarding_cases: int
    overdue_tasks: int
    incomplete_files: int
    expiring_contracts: int
    active_processes: int


class HiringSubmission(CamelModel):
    values: dict[str, Any]
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class HiringRequestDto(CamelModel):
    id: UUID
    number: str
    status: str
    current_step: str
    created_at: datetime
    attachments: list[dict[str, Any]]
