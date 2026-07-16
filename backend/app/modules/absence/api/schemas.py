from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.shared.api import CamelModel


class OrgBody(CamelModel):
    organization_id: UUID


class LeaveCreateBody(OrgBody):
    employee_id: UUID
    leave_type_id: UUID
    start_date: date
    end_date: date
    reason: str | None = None


class LeaveResubmitBody(OrgBody):
    revision: int = Field(ge=1)
    start_date: date
    end_date: date
    reason: str | None = None


class TripCreateBody(OrgBody):
    employee_id: UUID
    destination: str = Field(min_length=1, max_length=500)
    start_date: date
    end_date: date
    purpose: str = Field(min_length=1)
    estimated_cost: float = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    funding_details: dict[str, Any] = Field(default_factory=dict)


class TripResubmitBody(TripCreateBody):
    revision: int = Field(ge=1)


class DecisionBody(OrgBody):
    revision: int = Field(ge=1)
    decision: Literal["approve", "return", "reject"]
    comment: str = ""


class CancelBody(OrgBody):
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1)
