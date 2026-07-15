"""Pydantic v2 camelCase contracts for organization endpoints."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.modules.organization.application.models import (
    OrganizationStructureView,
    OrganizationTreeNode,
    ValidationOutcome,
    VersionComparison,
)
from app.modules.organization.domain.entities import StaffingSlot
from app.modules.organization.domain.enums import (
    EmploymentType,
    OrganizationStatus,
    ReviewRequestStatus,
    StaffingSlotStatus,
    StructureVersionStatus,
    ValidationSeverity,
)
from app.shared.api.schemas import CamelModel


class OrganizationResponse(CamelModel):
    id: UUID
    code: str
    legal_name: str
    display_name: str
    status: OrganizationStatus
    created_at: datetime
    updated_at: datetime


class StructureVersionResponse(CamelModel):
    id: UUID
    organization_id: UUID
    version_number: int
    name: str
    status: StructureVersionStatus
    based_on_version_id: UUID | None
    effective_from: date | None
    effective_to: date | None
    revision: int
    created_by: UUID
    published_by: UUID | None
    created_at: datetime
    published_at: datetime | None


class OrganizationUnitResponse(CamelModel):
    id: UUID
    structure_version_id: UUID
    stable_key: UUID
    code: str
    name: str
    short_name: str | None
    unit_type_id: UUID
    parent_unit_id: UUID | None
    sort_order: int
    description: str | None
    active: bool
    custom_fields: dict[str, Any]
    revision: int


class OrganizationTreeNodeResponse(CamelModel):
    unit: OrganizationUnitResponse
    children: list[OrganizationTreeNodeResponse] = Field(default_factory=list)

    @classmethod
    def from_node(cls, node: OrganizationTreeNode) -> Self:
        return cls(
            unit=OrganizationUnitResponse.model_validate(node.unit),
            children=[cls.from_node(child) for child in node.children],
        )


class OrganizationRelationshipResponse(CamelModel):
    id: UUID
    structure_version_id: UUID
    relationship_type_id: UUID
    source_unit_id: UUID
    target_unit_id: UUID
    effective_from: date | None
    effective_to: date | None
    metadata: dict[str, Any]
    active: bool
    revision: int


class PositionDefinitionResponse(CamelModel):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    description: str | None
    job_family: str | None
    grade: str | None
    active: bool
    custom_fields: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime


class StaffingSlotResponse(CamelModel):
    id: UUID
    structure_version_id: UUID
    stable_key: UUID
    organization_unit_id: UUID
    position_definition_id: UUID
    reports_to_slot_id: UUID | None
    head_of_unit: bool
    full_time_equivalent: Decimal
    employment_type: EmploymentType
    status: StaffingSlotStatus
    effective_from: date | None
    effective_to: date | None
    custom_fields: dict[str, Any]
    revision: int

    @classmethod
    def from_domain(cls, slot: StaffingSlot) -> Self:
        return cls.model_validate(slot).model_copy(update={"status": slot.effective_status()})


class UnitTypeResponse(CamelModel):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    description: str | None
    active: bool
    allowed_parent_type_ids: tuple[UUID, ...]
    custom_fields_schema: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime


class RelationshipTypeResponse(CamelModel):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    description: str | None
    directed: bool
    prevents_cycles: bool
    allow_self_link: bool
    active: bool
    metadata_schema: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime


class OrganizationPolicyResponse(CamelModel):
    id: UUID
    organization_id: UUID
    structure_version_id: UUID | None
    effective_from: date | None
    effective_to: date | None
    managers_can_create_employee_drafts: bool
    managers_can_assign_existing_employees: bool
    manager_changes_require_hr_approval: bool
    managers_can_create_staffing_slots: bool
    staffing_changes_require_finance_review: bool
    structure_publish_requires_review: bool
    allow_multiple_unit_heads: bool
    allow_cross_unit_relationships: bool
    revision: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class ReviewRequestResponse(CamelModel):
    id: UUID
    organization_id: UUID
    structure_version_id: UUID
    status: ReviewRequestStatus
    submitted_by: UUID
    submitted_at: datetime
    resolved_by: UUID | None
    resolved_at: datetime | None
    submission_reason: str | None
    resolution_reason: str | None
    revision: int


class StructureViewResponse(CamelModel):
    version: StructureVersionResponse
    root: OrganizationTreeNodeResponse | None
    relationships: list[OrganizationRelationshipResponse]
    staffing_slots: list[StaffingSlotResponse]

    @classmethod
    def from_view(cls, view: OrganizationStructureView) -> Self:
        return cls(
            version=StructureVersionResponse.model_validate(view.version),
            root=(
                OrganizationTreeNodeResponse.from_node(view.root) if view.root is not None else None
            ),
            relationships=[
                OrganizationRelationshipResponse.model_validate(item) for item in view.relationships
            ],
            staffing_slots=[
                StaffingSlotResponse.model_validate(item) for item in view.staffing_slots
            ],
        )


class ValidationIssueResponse(CamelModel):
    code: str
    message: str
    severity: ValidationSeverity
    path: str | None
    entity_id: UUID | None
    details: dict[str, Any]


class ValidationResponse(CamelModel):
    version_id: UUID
    revision: int
    is_valid: bool
    error_count: int
    warning_count: int
    issues: list[ValidationIssueResponse]

    @classmethod
    def from_outcome(cls, outcome: ValidationOutcome) -> Self:
        return cls(
            version_id=outcome.version_id,
            revision=outcome.revision,
            is_valid=outcome.report.is_valid,
            error_count=outcome.report.error_count,
            warning_count=outcome.report.warning_count,
            issues=[ValidationIssueResponse.model_validate(item) for item in outcome.report.issues],
        )


class VersionComparisonResponse(CamelModel):
    from_version_id: UUID
    to_version_id: UUID
    added_units: list[OrganizationUnitResponse]
    removed_units: list[OrganizationUnitResponse]
    changed_units: list[dict[str, Any]]
    added_relationships: list[OrganizationRelationshipResponse]
    removed_relationships: list[OrganizationRelationshipResponse]
    added_staffing_slots: list[StaffingSlotResponse]
    removed_staffing_slots: list[StaffingSlotResponse]
    changed_staffing_slots: list[dict[str, Any]]

    @classmethod
    def from_comparison(cls, comparison: VersionComparison) -> Self:
        return cls(
            from_version_id=comparison.from_version_id,
            to_version_id=comparison.to_version_id,
            added_units=[
                OrganizationUnitResponse.model_validate(item) for item in comparison.added_units
            ],
            removed_units=[
                OrganizationUnitResponse.model_validate(item) for item in comparison.removed_units
            ],
            changed_units=list(comparison.changed_units),
            added_relationships=[
                OrganizationRelationshipResponse.model_validate(item)
                for item in comparison.added_relationships
            ],
            removed_relationships=[
                OrganizationRelationshipResponse.model_validate(item)
                for item in comparison.removed_relationships
            ],
            added_staffing_slots=[
                StaffingSlotResponse.model_validate(item)
                for item in comparison.added_staffing_slots
            ],
            removed_staffing_slots=[
                StaffingSlotResponse.model_validate(item)
                for item in comparison.removed_staffing_slots
            ],
            changed_staffing_slots=list(comparison.changed_staffing_slots),
        )


class CreateDraftRequest(CamelModel):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=255)
    based_on_version_id: UUID | None = None


class RevisionReasonRequest(CamelModel):
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)


class ReturnForCorrectionRequest(RevisionReasonRequest):
    review_revision: int = Field(ge=1)


class PublishStructureRequest(RevisionReasonRequest):
    effective_from: date
    review_revision: int | None = Field(default=None, ge=1)


class AddUnitRequest(CamelModel):
    version_revision: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    short_name: str | None = Field(default=None, max_length=255)
    unit_type_id: UUID
    parent_unit_id: UUID | None = None
    sort_order: int = Field(default=0, ge=0)
    description: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class UpdateUnitRequest(CamelModel):
    version_revision: int = Field(ge=1)
    revision: int = Field(ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    short_name: str | None = Field(default=None, max_length=255)
    unit_type_id: UUID | None = None
    sort_order: int | None = Field(default=None, ge=0)
    description: str | None = None
    custom_fields: dict[str, Any] | None = None

    def changes(self) -> dict[str, Any]:
        excluded = {"version_revision", "revision"}
        return {key: getattr(self, key) for key in self.model_fields_set if key not in excluded}


class MoveUnitRequest(CamelModel):
    version_revision: int = Field(ge=1)
    revision: int = Field(ge=1)
    parent_unit_id: UUID | None = None
    sort_order: int = Field(ge=0)


class ReorderUnitItemRequest(CamelModel):
    unit_id: UUID
    revision: int = Field(ge=1)
    sort_order: int = Field(ge=0)


class ReorderUnitsRequest(CamelModel):
    version_revision: int = Field(ge=1)
    parent_unit_id: UUID | None = None
    items: list[ReorderUnitItemRequest] = Field(min_length=1)


class DeactivateUnitRequest(RevisionReasonRequest):
    version_revision: int = Field(ge=1)


class AddRelationshipRequest(CamelModel):
    version_revision: int = Field(ge=1)
    relationship_type_id: UUID
    source_unit_id: UUID
    target_unit_id: UUID
    effective_from: date | None = None
    effective_to: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> Self:
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effectiveTo must be on or after effectiveFrom")
        return self


class UpdateRelationshipRequest(CamelModel):
    version_revision: int = Field(ge=1)
    revision: int = Field(ge=1)
    relationship_type_id: UUID | None = None
    source_unit_id: UUID | None = None
    target_unit_id: UUID | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    metadata: dict[str, Any] | None = None
    active: bool | None = None

    def changes(self) -> dict[str, Any]:
        excluded = {"version_revision", "revision"}
        return {key: getattr(self, key) for key in self.model_fields_set if key not in excluded}


class RemoveRelationshipRequest(RevisionReasonRequest):
    version_revision: int = Field(ge=1)


class CreatePositionRequest(CamelModel):
    organization_id: UUID
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    job_family: str | None = Field(default=None, max_length=128)
    grade: str | None = Field(default=None, max_length=64)
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class UpdatePositionRequest(CamelModel):
    revision: int = Field(ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    job_family: str | None = Field(default=None, max_length=128)
    grade: str | None = Field(default=None, max_length=64)
    active: bool | None = None
    custom_fields: dict[str, Any] | None = None

    def changes(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.model_fields_set if key != "revision"}


class CreateStaffingSlotRequest(CamelModel):
    version_id: UUID
    version_revision: int = Field(ge=1)
    organization_unit_id: UUID
    position_definition_id: UUID
    reports_to_slot_id: UUID | None = None
    head_of_unit: bool = False
    full_time_equivalent: Decimal = Field(gt=0, le=1, decimal_places=2)
    employment_type: EmploymentType = EmploymentType.PERMANENT
    status: StaffingSlotStatus = StaffingSlotStatus.PLANNED
    effective_from: date | None = None
    effective_to: date | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class UpdateStaffingSlotRequest(CamelModel):
    version_revision: int = Field(ge=1)
    revision: int = Field(ge=1)
    organization_unit_id: UUID | None = None
    position_definition_id: UUID | None = None
    reports_to_slot_id: UUID | None = None
    head_of_unit: bool | None = None
    full_time_equivalent: Decimal | None = Field(default=None, gt=0, le=1, decimal_places=2)
    employment_type: EmploymentType | None = None
    status: StaffingSlotStatus | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    custom_fields: dict[str, Any] | None = None

    def changes(self) -> dict[str, Any]:
        excluded = {"version_revision", "revision"}
        return {key: getattr(self, key) for key in self.model_fields_set if key not in excluded}


class CloseStaffingSlotRequest(RevisionReasonRequest):
    version_revision: int = Field(ge=1)
    effective_to: date


class CreateUnitTypeRequest(CamelModel):
    organization_id: UUID
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    allowed_parent_type_ids: list[UUID] = Field(default_factory=list)
    custom_fields_schema: dict[str, Any] = Field(default_factory=dict)


class UpdateUnitTypeRequest(CamelModel):
    revision: int = Field(ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    active: bool | None = None
    allowed_parent_type_ids: list[UUID] | None = None
    custom_fields_schema: dict[str, Any] | None = None

    def changes(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.model_fields_set if key != "revision"}


class CreateRelationshipTypeRequest(CamelModel):
    organization_id: UUID
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    directed: bool = True
    prevents_cycles: bool = False
    allow_self_link: bool = False
    metadata_schema: dict[str, Any] = Field(default_factory=dict)


class UpdateRelationshipTypeRequest(CamelModel):
    revision: int = Field(ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    directed: bool | None = None
    prevents_cycles: bool | None = None
    allow_self_link: bool | None = None
    active: bool | None = None
    metadata_schema: dict[str, Any] | None = None

    def changes(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.model_fields_set if key != "revision"}


class UpdatePolicyRequest(CamelModel):
    version_revision: int = Field(ge=1)
    revision: int = Field(ge=1)
    managers_can_create_employee_drafts: bool | None = None
    managers_can_assign_existing_employees: bool | None = None
    manager_changes_require_hr_approval: bool | None = None
    managers_can_create_staffing_slots: bool | None = None
    staffing_changes_require_finance_review: bool | None = None
    structure_publish_requires_review: bool | None = None
    allow_multiple_unit_heads: bool | None = None
    allow_cross_unit_relationships: bool | None = None

    def changes(self) -> dict[str, bool]:
        return {
            key: bool(getattr(self, key))
            for key in self.model_fields_set
            if key not in {"version_revision", "revision"}
        }
