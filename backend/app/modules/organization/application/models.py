"""Read models returned by organization application services."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.modules.organization.domain.entities import (
    OrganizationRelationship,
    OrganizationStructureVersion,
    OrganizationUnit,
    StaffingSlot,
)
from app.modules.organization.domain.validation import ValidationReport


@dataclass(frozen=True, slots=True)
class OrganizationTreeNode:
    unit: OrganizationUnit
    children: tuple["OrganizationTreeNode", ...] = ()


@dataclass(frozen=True, slots=True)
class OrganizationStructureView:
    version: OrganizationStructureVersion
    root: OrganizationTreeNode | None
    relationships: tuple[OrganizationRelationship, ...]
    staffing_slots: tuple[StaffingSlot, ...]


@dataclass(frozen=True, slots=True)
class VersionComparison:
    from_version_id: UUID
    to_version_id: UUID
    added_units: tuple[OrganizationUnit, ...]
    removed_units: tuple[OrganizationUnit, ...]
    changed_units: tuple[dict[str, Any], ...]
    added_relationships: tuple[OrganizationRelationship, ...]
    removed_relationships: tuple[OrganizationRelationship, ...]
    added_staffing_slots: tuple[StaffingSlot, ...]
    removed_staffing_slots: tuple[StaffingSlot, ...]
    changed_staffing_slots: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    version_id: UUID
    revision: int
    report: ValidationReport
