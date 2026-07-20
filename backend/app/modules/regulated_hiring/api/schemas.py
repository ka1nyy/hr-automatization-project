from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.shared.api import CamelModel


class OrganizationBody(CamelModel):
    organization_id: UUID


class StartCaseBody(OrganizationBody):
    recruitment_request_id: UUID
    staffing_slot_id: UUID
    business_key: str = Field(min_length=3, max_length=200)
    process_engine: Literal["local", "camunda"] = "local"
    camunda_process_instance_key: str | None = Field(default=None, max_length=100)


class StageActionBody(OrganizationBody):
    expected_revision: int = Field(ge=1)
    action: Literal["approve", "complete", "return", "reject", "cancel"]
    idempotency_key: str = Field(min_length=8, max_length=200)
    reason: str | None = Field(default=None, max_length=4000)
    evidence: dict[str, Any] = Field(default_factory=dict)
    return_to_sequence: int | None = Field(default=None, ge=0, le=22)


class FormRecordBody(OrganizationBody):
    form_code: str = Field(pattern=r"^NAIM-(0[1-9]|1[0-9]|2[0-1])$")
    data: dict[str, Any]
    signed: bool = False
    signers: list[dict[str, Any]] = Field(default_factory=list)
    correction_reason: str | None = Field(default=None, max_length=4000)
    document_id: UUID | None = None


class AuthorityBindingBody(OrganizationBody):
    entity_type: Literal[
        "organization_unit",
        "position_definition",
        "staffing_slot",
        "functional_role",
        "signing_authority",
    ]
    entity_id: UUID
    authority_status: Literal["confirmed", "model", "document_required"]
    source_id: UUID | None = None
    assertion: str = Field(min_length=1, max_length=5000)
    effective_from: date
    effective_to: date | None = None
    granted_permissions: list[str] = Field(default_factory=list)
