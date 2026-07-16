from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.shared.api import CamelModel


class OrgBody(CamelModel):
    organization_id: UUID


class InitiateBody(OrgBody):
    employee_id: UUID
    initiated_by_employee_id: UUID | None = None
    reason_id: UUID
    legal_basis: str = Field(min_length=1)
    requested_date: date
    unit_id: UUID


class DecisionBody(OrgBody):
    revision: int = Field(ge=1)
    decision: Literal["approve", "return", "reject"]
    comment: str = ""


class ResubmitBody(OrgBody):
    revision: int = Field(ge=1)
    employee_id: UUID
    unit_id: UUID
    legal_basis: str = Field(min_length=1)
    requested_date: date


class RegisterBody(OrgBody):
    revision: int = Field(ge=1)
    document_id: UUID


class TaskItem(CamelModel):
    task_type: str
    assigned_user_id: UUID | None = None
    assigned_employee_id: UUID | None = None
    assigned_unit_id: UUID | None = None
    due_at: datetime | None = None


class TasksBody(OrgBody):
    tasks: list[TaskItem]


class TaskCompleteBody(OrgBody):
    revision: int = Field(ge=1)
    evidence: dict[str, Any] = Field(default_factory=dict)


class WaiveBody(OrgBody):
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1)


class SecondaryPlan(CamelModel):
    assignment_id: UUID
    action: Literal["end", "retain"]


class ScheduleBody(OrgBody):
    revision: int = Field(ge=1)
    effective_date: date
    secondary_assignments: list[SecondaryPlan] = Field(default_factory=list)


class CompleteBody(OrgBody):
    revision: int = Field(ge=1)


class CancelBody(CompleteBody):
    reason: str = Field(min_length=1)
