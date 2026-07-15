"""Transport-neutral command objects for organization use cases."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.modules.organization.domain.enums import EmploymentType, StaffingSlotStatus


@dataclass(frozen=True, slots=True)
class CreateDraftCommand:
    organization_id: UUID
    name: str
    based_on_version_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AddUnitCommand:
    version_id: UUID
    version_revision: int
    code: str
    name: str
    unit_type_id: UUID
    parent_unit_id: UUID | None
    short_name: str | None = None
    sort_order: int = 0
    description: str | None = None
    custom_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpdateUnitCommand:
    version_id: UUID
    unit_id: UUID
    version_revision: int
    unit_revision: int
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MoveUnitCommand:
    version_id: UUID
    unit_id: UUID
    version_revision: int
    unit_revision: int
    parent_unit_id: UUID | None
    sort_order: int


@dataclass(frozen=True, slots=True)
class ReorderUnitItem:
    unit_id: UUID
    revision: int
    sort_order: int


@dataclass(frozen=True, slots=True)
class ReorderUnitsCommand:
    version_id: UUID
    version_revision: int
    parent_unit_id: UUID | None
    items: tuple[ReorderUnitItem, ...]


@dataclass(frozen=True, slots=True)
class DeactivateUnitCommand:
    version_id: UUID
    unit_id: UUID
    version_revision: int
    unit_revision: int
    reason: str


@dataclass(frozen=True, slots=True)
class AddRelationshipCommand:
    version_id: UUID
    version_revision: int
    relationship_type_id: UUID
    source_unit_id: UUID
    target_unit_id: UUID
    effective_from: date | None = None
    effective_to: date | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpdateRelationshipCommand:
    version_id: UUID
    relationship_id: UUID
    version_revision: int
    relationship_revision: int
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RemoveRelationshipCommand:
    version_id: UUID
    relationship_id: UUID
    version_revision: int
    relationship_revision: int
    reason: str


@dataclass(frozen=True, slots=True)
class CreatePositionCommand:
    organization_id: UUID
    code: str
    name: str
    description: str | None = None
    job_family: str | None = None
    grade: str | None = None
    custom_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpdatePositionCommand:
    position_id: UUID
    revision: int
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CreateStaffingSlotCommand:
    version_id: UUID
    version_revision: int
    organization_unit_id: UUID
    position_definition_id: UUID
    reports_to_slot_id: UUID | None
    head_of_unit: bool
    full_time_equivalent: Decimal
    employment_type: EmploymentType
    status: StaffingSlotStatus
    effective_from: date | None = None
    effective_to: date | None = None
    custom_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpdateStaffingSlotCommand:
    slot_id: UUID
    version_revision: int
    slot_revision: int
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CloseStaffingSlotCommand:
    slot_id: UUID
    version_revision: int
    slot_revision: int
    effective_to: date
    reason: str


@dataclass(frozen=True, slots=True)
class SubmitReviewCommand:
    version_id: UUID
    revision: int
    reason: str


@dataclass(frozen=True, slots=True)
class ReturnForCorrectionCommand:
    version_id: UUID
    revision: int
    review_revision: int
    reason: str


@dataclass(frozen=True, slots=True)
class PublishStructureCommand:
    version_id: UUID
    revision: int
    effective_from: date
    reason: str
    review_revision: int | None = None


@dataclass(frozen=True, slots=True)
class CreateUnitTypeCommand:
    organization_id: UUID
    code: str
    name: str
    description: str | None = None
    allowed_parent_type_ids: tuple[UUID, ...] = ()
    custom_fields_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpdateUnitTypeCommand:
    type_id: UUID
    revision: int
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CreateRelationshipTypeCommand:
    organization_id: UUID
    code: str
    name: str
    description: str | None = None
    directed: bool = True
    prevents_cycles: bool = False
    allow_self_link: bool = False
    metadata_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpdateRelationshipTypeCommand:
    type_id: UUID
    revision: int
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UpdatePolicyCommand:
    version_id: UUID
    version_revision: int
    policy_revision: int
    changes: dict[str, bool]
