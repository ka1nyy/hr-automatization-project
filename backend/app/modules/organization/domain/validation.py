"""Complete, side-effect-free validation of an organization structure snapshot."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.modules.organization.domain.entities import (
    OrganizationPolicy,
    OrganizationRelationship,
    OrganizationRelationshipType,
    OrganizationStructureVersion,
    OrganizationUnit,
    OrganizationUnitType,
    PositionDefinition,
    StaffingSlot,
)
from app.modules.organization.domain.enums import StaffingSlotStatus, ValidationSeverity


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    path: str | None = None
    entity_id: UUID | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "path": self.path,
            "entityId": str(self.entity_id) if self.entity_id else None,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity is ValidationSeverity.ERROR for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(issue.severity is ValidationSeverity.ERROR for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity is ValidationSeverity.WARNING for issue in self.issues)


@dataclass(frozen=True, slots=True)
class StructureSnapshot:
    version: OrganizationStructureVersion
    units: tuple[OrganizationUnit, ...]
    relationships: tuple[OrganizationRelationship, ...]
    staffing_slots: tuple[StaffingSlot, ...]
    unit_types: tuple[OrganizationUnitType, ...]
    relationship_types: tuple[OrganizationRelationshipType, ...]
    position_definitions: tuple[PositionDefinition, ...]
    policy: OrganizationPolicy


class OrganizationStructureValidator:
    """Collects every detectable issue instead of failing on the first one."""

    def validate(self, snapshot: StructureSnapshot) -> ValidationReport:
        issues: list[ValidationIssue] = []
        active_units = tuple(unit for unit in snapshot.units if unit.active)
        unit_by_id = {unit.id: unit for unit in snapshot.units}
        active_unit_by_id = {unit.id: unit for unit in active_units}
        unit_type_by_id = {item.id: item for item in snapshot.unit_types}

        issues.extend(self._validate_version_dates(snapshot.version))
        issues.extend(self._validate_roots(active_units))
        issues.extend(self._validate_unit_references(snapshot.version.id, active_units, unit_by_id))
        issues.extend(self._validate_unit_types(active_units, unit_type_by_id, active_unit_by_id))
        issues.extend(self._validate_unique_unit_values(active_units))
        issues.extend(self._validate_tree_cycles(active_units))
        issues.extend(
            self._validate_relationships(
                snapshot,
                unit_by_id=unit_by_id,
                active_unit_by_id=active_unit_by_id,
            )
        )
        issues.extend(
            self._validate_staffing(
                snapshot,
                unit_by_id=unit_by_id,
            )
        )
        return ValidationReport(tuple(issues))

    @staticmethod
    def _validate_version_dates(version: OrganizationStructureVersion) -> list[ValidationIssue]:
        if (
            version.effective_from is not None
            and version.effective_to is not None
            and version.effective_to < version.effective_from
        ):
            return [
                ValidationIssue(
                    "ORG_STRUCTURE_INVALID_DATE_RANGE",
                    "Structure version effectiveTo precedes effectiveFrom.",
                    path="effectiveTo",
                    entity_id=version.id,
                )
            ]
        return []

    @staticmethod
    def _validate_roots(units: tuple[OrganizationUnit, ...]) -> list[ValidationIssue]:
        roots = [unit for unit in units if unit.parent_unit_id is None]
        if len(roots) == 1:
            return []
        return [
            ValidationIssue(
                "ORG_STRUCTURE_MULTIPLE_ROOTS",
                "A structure version must contain exactly one active root unit.",
                path="units",
                details={"rootCount": len(roots), "rootIds": [str(unit.id) for unit in roots]},
            )
        ]

    @staticmethod
    def _validate_unit_references(
        version_id: UUID,
        units: tuple[OrganizationUnit, ...],
        unit_by_id: dict[UUID, OrganizationUnit],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for unit in units:
            if unit.structure_version_id != version_id:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_EXTERNAL_VERSION_REFERENCE",
                        "A unit belongs to a different structure version.",
                        entity_id=unit.id,
                        path="structureVersionId",
                    )
                )
            if unit.parent_unit_id is None:
                continue
            parent = unit_by_id.get(unit.parent_unit_id)
            if parent is None or not parent.active:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_ORPHAN_UNIT",
                        "An active unit must have an active parent in the same version.",
                        entity_id=unit.id,
                        path="parentUnitId",
                        details={"parentUnitId": str(unit.parent_unit_id)},
                    )
                )
            elif parent.structure_version_id != version_id:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_EXTERNAL_VERSION_REFERENCE",
                        "A unit cannot reference a parent in another structure version.",
                        entity_id=unit.id,
                        path="parentUnitId",
                        details={"parentUnitId": str(parent.id)},
                    )
                )
        return issues

    @staticmethod
    def _validate_unit_types(
        units: tuple[OrganizationUnit, ...],
        unit_type_by_id: dict[UUID, OrganizationUnitType],
        unit_by_id: dict[UUID, OrganizationUnit],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for unit in units:
            unit_type = unit_type_by_id.get(unit.unit_type_id)
            if unit_type is None or not unit_type.active:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_UNIT_TYPE",
                        "An active unit must reference an active unit type.",
                        entity_id=unit.id,
                        path="unitTypeId",
                        details={"unitTypeId": str(unit.unit_type_id)},
                    )
                )
                continue
            if unit.parent_unit_id is None or not unit_type.allowed_parent_type_ids:
                continue
            parent = unit_by_id.get(unit.parent_unit_id)
            if parent is not None and parent.unit_type_id not in unit_type.allowed_parent_type_ids:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_PARENT_TYPE",
                        "The configured unit type does not allow this parent type.",
                        entity_id=unit.id,
                        path="parentUnitId",
                        details={
                            "parentUnitId": str(parent.id),
                            "parentUnitTypeId": str(parent.unit_type_id),
                        },
                    )
                )
        return issues

    @staticmethod
    def _validate_unique_unit_values(units: tuple[OrganizationUnit, ...]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        codes: dict[str, list[UUID]] = defaultdict(list)
        stable_keys: dict[UUID, list[UUID]] = defaultdict(list)
        sibling_orders: dict[tuple[UUID | None, int], list[UUID]] = defaultdict(list)
        for unit in units:
            codes[unit.code.casefold()].append(unit.id)
            stable_keys[unit.stable_key].append(unit.id)
            sibling_orders[(unit.parent_unit_id, unit.sort_order)].append(unit.id)
        for code, unit_ids in codes.items():
            if len(unit_ids) > 1:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_DUPLICATE_UNIT_CODE",
                        "Unit codes must be unique inside a structure version.",
                        path="units.code",
                        details={"code": code, "unitIds": [str(item) for item in unit_ids]},
                    )
                )
        for stable_key, unit_ids in stable_keys.items():
            if len(unit_ids) > 1:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_DUPLICATE_STABLE_KEY",
                        "Unit stable keys must be unique inside a structure version.",
                        path="units.stableKey",
                        details={
                            "stableKey": str(stable_key),
                            "unitIds": [str(item) for item in unit_ids],
                        },
                    )
                )
        for (parent_id, sort_order), unit_ids in sibling_orders.items():
            if len(unit_ids) > 1:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_DUPLICATE_SORT_ORDER",
                        "Sibling units must have distinct sort orders.",
                        path="units.sortOrder",
                        details={
                            "parentUnitId": str(parent_id) if parent_id else None,
                            "sortOrder": sort_order,
                            "unitIds": [str(item) for item in unit_ids],
                        },
                    )
                )
        return issues

    @staticmethod
    def _validate_tree_cycles(units: tuple[OrganizationUnit, ...]) -> list[ValidationIssue]:
        parent_by_id = {unit.id: unit.parent_unit_id for unit in units}
        state: dict[UUID, int] = {}
        issues: list[ValidationIssue] = []
        reported: set[frozenset[UUID]] = set()

        for start_id in parent_by_id:
            if state.get(start_id) == 2:
                continue
            path: list[UUID] = []
            positions: dict[UUID, int] = {}
            current: UUID | None = start_id
            while current is not None and current in parent_by_id:
                if current in positions:
                    cycle = path[positions[current] :]
                    cycle_key = frozenset(cycle)
                    if cycle_key not in reported:
                        reported.add(cycle_key)
                        issues.append(
                            ValidationIssue(
                                "ORG_STRUCTURE_CYCLE",
                                "The primary organization tree contains a cycle.",
                                entity_id=current,
                                path="units.parentUnitId",
                                details={"unitIds": [str(item) for item in cycle]},
                            )
                        )
                    break
                if state.get(current) == 2:
                    break
                positions[current] = len(path)
                path.append(current)
                state[current] = 1
                current = parent_by_id[current]
            for item in path:
                state[item] = 2
        return issues

    def _validate_relationships(
        self,
        snapshot: StructureSnapshot,
        *,
        unit_by_id: dict[UUID, OrganizationUnit],
        active_unit_by_id: dict[UUID, OrganizationUnit],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        type_by_id = {item.id: item for item in snapshot.relationship_types}
        seen: dict[tuple[UUID, UUID, UUID, date | None, date | None], UUID] = {}
        cycle_edges: dict[UUID, list[tuple[UUID, UUID]]] = defaultdict(list)

        for relationship in (item for item in snapshot.relationships if item.active):
            relationship_type = type_by_id.get(relationship.relationship_type_id)
            if relationship.structure_version_id != snapshot.version.id:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_EXTERNAL_VERSION_REFERENCE",
                        "A relationship belongs to a different structure version.",
                        entity_id=relationship.id,
                        path="structureVersionId",
                    )
                )
            if relationship_type is None or not relationship_type.active:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_RELATIONSHIP",
                        "A relationship must reference an active relationship type.",
                        entity_id=relationship.id,
                        path="relationshipTypeId",
                    )
                )
                continue
            source = unit_by_id.get(relationship.source_unit_id)
            target = unit_by_id.get(relationship.target_unit_id)
            if source is None or target is None or not source.active or not target.active:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_RELATIONSHIP",
                        "A relationship must reference two active units in this version.",
                        entity_id=relationship.id,
                        path="sourceUnitId",
                        details={
                            "sourceUnitId": str(relationship.source_unit_id),
                            "targetUnitId": str(relationship.target_unit_id),
                        },
                    )
                )
                continue
            if (
                source.structure_version_id != snapshot.version.id
                or target.structure_version_id != snapshot.version.id
            ):
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_EXTERNAL_VERSION_REFERENCE",
                        "Relationship endpoints must belong to the same structure version.",
                        entity_id=relationship.id,
                        path="sourceUnitId",
                    )
                )
            if source.id == target.id and not relationship_type.allow_self_link:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_RELATIONSHIP",
                        "The configured relationship type prohibits self-links.",
                        entity_id=relationship.id,
                        path="targetUnitId",
                    )
                )
            if (
                relationship.effective_from is not None
                and relationship.effective_to is not None
                and relationship.effective_to < relationship.effective_from
            ):
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_DATE_RANGE",
                        "Relationship effectiveTo precedes effectiveFrom.",
                        entity_id=relationship.id,
                        path="effectiveTo",
                    )
                )
            key = (
                relationship.relationship_type_id,
                relationship.source_unit_id,
                relationship.target_unit_id,
                relationship.effective_from,
                relationship.effective_to,
            )
            existing_id = seen.get(key)
            if existing_id is not None:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_RELATIONSHIP",
                        "Duplicate active relationships are not allowed.",
                        entity_id=relationship.id,
                        path="relationships",
                        details={"duplicateOfRelationshipId": str(existing_id)},
                    )
                )
            else:
                seen[key] = relationship.id
            if relationship_type.prevents_cycles and source.id != target.id:
                cycle_edges[relationship_type.id].append((source.id, target.id))
            if not snapshot.policy.allow_cross_unit_relationships:
                source_branch = self._top_level_branch(source.id, active_unit_by_id)
                target_branch = self._top_level_branch(target.id, active_unit_by_id)
                if source_branch != target_branch:
                    issues.append(
                        ValidationIssue(
                            "ORG_STRUCTURE_INVALID_RELATIONSHIP",
                            "Cross-unit relationships are disabled by organization policy.",
                            entity_id=relationship.id,
                            path="targetUnitId",
                            details={
                                "sourceBranchId": str(source_branch),
                                "targetBranchId": str(target_branch),
                            },
                        )
                    )

        for type_id, edges in cycle_edges.items():
            cycle = self._first_directed_cycle(edges)
            if cycle:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_RELATIONSHIP",
                        "A relationship type configured as acyclic contains a cycle.",
                        path="relationships",
                        details={
                            "relationshipTypeId": str(type_id),
                            "unitIds": [str(item) for item in cycle],
                        },
                    )
                )
        return issues

    @staticmethod
    def _top_level_branch(unit_id: UUID, unit_by_id: dict[UUID, OrganizationUnit]) -> UUID:
        current = unit_by_id[unit_id]
        seen: set[UUID] = set()
        while current.parent_unit_id is not None and current.parent_unit_id in unit_by_id:
            if current.id in seen:
                return current.id
            seen.add(current.id)
            parent = unit_by_id[current.parent_unit_id]
            if parent.parent_unit_id is None:
                return current.id
            current = parent
        return current.id

    @staticmethod
    def _first_directed_cycle(edges: list[tuple[UUID, UUID]]) -> list[UUID]:
        adjacency: dict[UUID, list[UUID]] = defaultdict(list)
        for source, target in edges:
            adjacency[source].append(target)
        visiting: set[UUID] = set()
        visited: set[UUID] = set()
        stack: list[UUID] = []

        def visit(node: UUID) -> list[UUID]:
            if node in visiting:
                return [*stack[stack.index(node) :], node]
            if node in visited:
                return []
            visiting.add(node)
            stack.append(node)
            for target in adjacency.get(node, []):
                cycle = visit(target)
                if cycle:
                    return cycle
            stack.pop()
            visiting.remove(node)
            visited.add(node)
            return []

        for node in adjacency:
            cycle = visit(node)
            if cycle:
                return cycle
        return []

    def _validate_staffing(
        self,
        snapshot: StructureSnapshot,
        *,
        unit_by_id: dict[UUID, OrganizationUnit],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        position_by_id = {item.id: item for item in snapshot.position_definitions}
        slot_by_id = {slot.id: slot for slot in snapshot.staffing_slots}
        active_slots = tuple(
            slot
            for slot in snapshot.staffing_slots
            if slot.status not in {StaffingSlotStatus.CLOSED, StaffingSlotStatus.CLOSING}
        )
        stable_keys: dict[UUID, list[UUID]] = defaultdict(list)
        head_counts: Counter[UUID] = Counter()

        for slot in active_slots:
            stable_keys[slot.stable_key].append(slot.id)
            if slot.structure_version_id != snapshot.version.id:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_EXTERNAL_VERSION_REFERENCE",
                        "A staffing slot belongs to a different structure version.",
                        entity_id=slot.id,
                        path="structureVersionId",
                    )
                )
            unit = unit_by_id.get(slot.organization_unit_id)
            if unit is None or not unit.active or unit.structure_version_id != snapshot.version.id:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_STAFFING_REFERENCE",
                        "A staffing slot must reference an active unit in this version.",
                        entity_id=slot.id,
                        path="organizationUnitId",
                    )
                )
            position = position_by_id.get(slot.position_definition_id)
            if position is None or not position.active:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_STAFFING_REFERENCE",
                        "A staffing slot must reference an active position definition.",
                        entity_id=slot.id,
                        path="positionDefinitionId",
                    )
                )
            if slot.full_time_equivalent <= Decimal("0") or slot.full_time_equivalent > Decimal(
                "1"
            ):
                issues.append(
                    ValidationIssue(
                        "STAFFING_FTE_EXCEEDED",
                        "Staffing slot FTE must be greater than zero and no more than one.",
                        entity_id=slot.id,
                        path="fullTimeEquivalent",
                        details={"fullTimeEquivalent": str(slot.full_time_equivalent)},
                    )
                )
            if (
                slot.effective_from is not None
                and slot.effective_to is not None
                and slot.effective_to < slot.effective_from
            ):
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_DATE_RANGE",
                        "Staffing slot effectiveTo precedes effectiveFrom.",
                        entity_id=slot.id,
                        path="effectiveTo",
                    )
                )
            if slot.reports_to_slot_id is not None:
                manager = slot_by_id.get(slot.reports_to_slot_id)
                if (
                    manager is None
                    or manager.structure_version_id != snapshot.version.id
                    or manager.status in {StaffingSlotStatus.CLOSED, StaffingSlotStatus.CLOSING}
                ):
                    issues.append(
                        ValidationIssue(
                            "ORG_STRUCTURE_INVALID_STAFFING_REFERENCE",
                            "A reporting slot must be active in the same structure version.",
                            entity_id=slot.id,
                            path="reportsToSlotId",
                        )
                    )
            if slot.head_of_unit:
                head_counts[slot.organization_unit_id] += 1

        for stable_key, slot_ids in stable_keys.items():
            if len(slot_ids) > 1:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_DUPLICATE_STABLE_KEY",
                        "Staffing slot stable keys must be unique inside a version.",
                        path="staffingSlots.stableKey",
                        details={
                            "stableKey": str(stable_key),
                            "staffingSlotIds": [str(item) for item in slot_ids],
                        },
                    )
                )
        if not snapshot.policy.allow_multiple_unit_heads:
            for unit_id, count in head_counts.items():
                if count > 1:
                    issues.append(
                        ValidationIssue(
                            "ORG_STRUCTURE_MULTIPLE_UNIT_HEADS",
                            "An organization unit has more than one active head slot.",
                            entity_id=unit_id,
                            path="staffingSlots.headOfUnit",
                            details={"headCount": count},
                        )
                    )
        for unit in (item for item in snapshot.units if item.active):
            if head_counts[unit.id] == 0:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_UNIT_HEAD_MISSING",
                        "The active unit has no designated head staffing slot.",
                        severity=ValidationSeverity.WARNING,
                        entity_id=unit.id,
                        path="staffingSlots.headOfUnit",
                    )
                )

        reporting_edges = [
            (slot.id, slot.reports_to_slot_id)
            for slot in active_slots
            if slot.reports_to_slot_id is not None and slot.reports_to_slot_id in slot_by_id
        ]
        cycle = self._first_directed_cycle(
            [(source, target) for source, target in reporting_edges if target is not None]
        )
        if cycle:
            issues.append(
                ValidationIssue(
                    "ORG_STRUCTURE_REPORTING_CYCLE",
                    "The staffing reporting chain contains a cycle.",
                    path="staffingSlots.reportsToSlotId",
                    details={"staffingSlotIds": [str(item) for item in cycle]},
                )
            )
        return issues
