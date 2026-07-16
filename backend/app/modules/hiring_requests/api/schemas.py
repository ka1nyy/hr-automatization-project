from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.shared.api import CamelModel


class HiringRequestPayload(CamelModel):
    """Draft payload. Completeness is enforced when the official PDF is generated."""

    personal: dict[str, Any]
    employment: dict[str, Any]
    education: dict[str, Any]


class HiringRequestCreate(HiringRequestPayload):
    organization_id: UUID


class HiringRequestUpdate(HiringRequestPayload):
    organization_id: UUID
    revision: int = Field(ge=1)


class OrganizationAction(CamelModel):
    organization_id: UUID
    revision: int = Field(ge=1)


class ApprovalDecisionRequest(OrganizationAction):
    decision: Literal["approve", "return", "reject"]
    comment: str = Field(default="", max_length=4000)

    @field_validator("comment")
    @classmethod
    def require_negative_comment(cls, value: str, info: Any) -> str:
        if info.data.get("decision") in {"return", "reject"} and not value.strip():
            raise ValueError("A comment is required for return or rejection")
        return value.strip()


class AcknowledgeRequest(OrganizationAction):
    comment: str = Field(default="", max_length=2000)
