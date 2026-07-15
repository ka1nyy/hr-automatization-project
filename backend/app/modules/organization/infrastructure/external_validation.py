"""Cross-module publication checks implemented as an organization validation port."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.employees.infrastructure.models import (
    DelegationModel,
    EmployeeAssignmentModel,
)
from app.modules.organization.domain.validation import ValidationIssue
from app.modules.organization.infrastructure.models import (
    OrganizationStructureVersionModel,
    OrganizationUnitModel,
    StaffingSlotModel,
)


class SqlAlchemyExternalStructureValidationAdapter:
    """Adds assignment and delegation checks without coupling application logic."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def validate_structure_version(
        self,
        version_id: UUID,
        *,
        effective_from: date | None = None,
    ) -> tuple[ValidationIssue, ...]:
        slots = tuple(
            (
                await self._session.scalars(
                    select(StaffingSlotModel).where(
                        StaffingSlotModel.structure_version_id == version_id
                    )
                )
            ).all()
        )
        slot_by_id = {slot.id: slot for slot in slots}
        assignments = tuple(
            (
                await self._session.scalars(
                    select(EmployeeAssignmentModel).where(
                        EmployeeAssignmentModel.staffing_slot_id.in_(slot_by_id)
                    )
                )
            ).all()
        )
        issues = self._assignment_issues(assignments, slot_by_id)

        organization_id = await self._session.scalar(
            select(OrganizationStructureVersionModel.organization_id).where(
                OrganizationStructureVersionModel.id == version_id
            )
        )
        if organization_id is not None:
            if effective_from is not None:
                issues.extend(
                    await self._assignment_transition_issues(
                        organization_id=organization_id,
                        version_id=version_id,
                        target_slots=slots,
                        effective_from=effective_from,
                    )
                )
            employee_ids = tuple(
                (
                    await self._session.scalars(
                        select(EmployeeAssignmentModel.employee_id)
                        .join(
                            StaffingSlotModel,
                            StaffingSlotModel.id == EmployeeAssignmentModel.staffing_slot_id,
                        )
                        .join(
                            OrganizationStructureVersionModel,
                            OrganizationStructureVersionModel.id
                            == StaffingSlotModel.structure_version_id,
                        )
                        .where(OrganizationStructureVersionModel.organization_id == organization_id)
                        .distinct()
                    )
                ).all()
            )
            if employee_ids:
                delegations = tuple(
                    (
                        await self._session.scalars(
                            select(DelegationModel).where(
                                or_(
                                    DelegationModel.delegator_employee_id.in_(employee_ids),
                                    DelegationModel.delegate_employee_id.in_(employee_ids),
                                )
                            )
                        )
                    ).all()
                )
                issues.extend(self._delegation_issues(delegations))
        return tuple(issues)

    async def _assignment_transition_issues(
        self,
        *,
        organization_id: UUID,
        version_id: UUID,
        target_slots: tuple[StaffingSlotModel, ...],
        effective_from: date,
    ) -> list[ValidationIssue]:
        """Prevent publication from silently moving live employment authority."""

        target_unit_keys = dict(
            (
                await self._session.execute(
                    select(OrganizationUnitModel.id, OrganizationUnitModel.stable_key).where(
                        OrganizationUnitModel.structure_version_id == version_id
                    )
                )
            ).tuples()
        )
        rows = (
            await self._session.execute(
                select(
                    EmployeeAssignmentModel,
                    StaffingSlotModel,
                    OrganizationUnitModel.stable_key,
                )
                .join(
                    StaffingSlotModel,
                    StaffingSlotModel.id == EmployeeAssignmentModel.staffing_slot_id,
                )
                .join(
                    OrganizationUnitModel,
                    OrganizationUnitModel.id == StaffingSlotModel.organization_unit_id,
                )
                .join(
                    OrganizationStructureVersionModel,
                    OrganizationStructureVersionModel.id == StaffingSlotModel.structure_version_id,
                )
                .where(
                    OrganizationStructureVersionModel.organization_id == organization_id,
                    EmployeeAssignmentModel.status != "cancelled",
                    or_(
                        EmployeeAssignmentModel.effective_to.is_(None),
                        EmployeeAssignmentModel.effective_to >= effective_from,
                    ),
                )
            )
        ).all()
        placements = tuple(
            (assignment, source_slot, source_unit_stable_key)
            for assignment, source_slot, source_unit_stable_key in rows
        )
        return self._transition_issues(
            placements,
            target_slots=target_slots,
            target_unit_keys=target_unit_keys,
            effective_from=effective_from,
        )

    @staticmethod
    def _transition_issues(
        placements: tuple[
            tuple[EmployeeAssignmentModel, StaffingSlotModel, UUID],
            ...,
        ],
        *,
        target_slots: tuple[StaffingSlotModel, ...],
        target_unit_keys: dict[UUID, UUID],
        effective_from: date,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        target_by_key = {slot.stable_key: slot for slot in target_slots}
        valid_by_target: dict[UUID, list[EmployeeAssignmentModel]] = defaultdict(list)

        for assignment, source_slot, source_unit_key in placements:
            if assignment.status == "cancelled" or (
                assignment.effective_to is not None and assignment.effective_to < effective_from
            ):
                continue
            target = target_by_key.get(source_slot.stable_key)
            if target is None:
                issues.append(
                    ValidationIssue(
                        "EMPLOYEE_ASSIGNMENT_OUTSIDE_VERSION",
                        (
                            "An ongoing assignment's staffing slot is missing from the "
                            "candidate version."
                        ),
                        entity_id=assignment.id,
                        path="employeeAssignments.staffingSlotId",
                        details={"staffingSlotStableKey": str(source_slot.stable_key)},
                    )
                )
                continue
            target_unit_key = target_unit_keys.get(target.organization_unit_id)
            if target_unit_key != source_unit_key:
                issues.append(
                    ValidationIssue(
                        "EMPLOYEE_ASSIGNMENT_OUTSIDE_VERSION",
                        (
                            "An ongoing assignment cannot move to another organization unit "
                            "during structure publication."
                        ),
                        entity_id=assignment.id,
                        path="employeeAssignments.organizationUnitId",
                        details={
                            "sourceUnitStableKey": str(source_unit_key),
                            "targetUnitStableKey": (
                                str(target_unit_key) if target_unit_key is not None else None
                            ),
                        },
                    )
                )
                continue
            if target.position_definition_id != source_slot.position_definition_id:
                issues.append(
                    ValidationIssue(
                        "EMPLOYEE_ASSIGNMENT_OUTSIDE_VERSION",
                        (
                            "An ongoing assignment cannot change position during structure "
                            "publication."
                        ),
                        entity_id=assignment.id,
                        path="employeeAssignments.positionDefinitionId",
                        details={
                            "sourcePositionDefinitionId": str(source_slot.position_definition_id),
                            "targetPositionDefinitionId": str(target.position_definition_id),
                        },
                    )
                )
                continue
            if target.status == "closed":
                issues.append(
                    ValidationIssue(
                        "EMPLOYEE_ASSIGNMENT_OUTSIDE_VERSION",
                        "An ongoing assignment cannot reference a closed candidate staffing slot.",
                        entity_id=assignment.id,
                        path="employeeAssignments.staffingSlotId",
                        details={"staffingSlotId": str(target.id)},
                    )
                )
                continue

            remaining_start = max(assignment.effective_from, effective_from)
            dates_conflict = (
                target.effective_from is not None and remaining_start < target.effective_from
            ) or (
                target.effective_to is not None
                and (
                    assignment.effective_to is None or assignment.effective_to > target.effective_to
                )
            )
            if target.status == "closing" and target.effective_to is None:
                dates_conflict = True
            if dates_conflict:
                issues.append(
                    ValidationIssue(
                        "ASSIGNMENT_DATE_CONFLICT",
                        "An ongoing assignment does not fit the candidate staffing slot dates.",
                        entity_id=assignment.id,
                        path="employeeAssignments.effectiveTo",
                        details={"staffingSlotId": str(target.id)},
                    )
                )
                continue
            valid_by_target[target.id].append(assignment)

        target_by_id = {slot.id: slot for slot in target_slots}
        for target_id, assignments in valid_by_target.items():
            target = target_by_id[target_id]
            peak = _peak_fte(assignments, effective_from=effective_from)
            if peak > target.full_time_equivalent:
                issues.append(
                    ValidationIssue(
                        "STAFFING_FTE_EXCEEDED",
                        "Ongoing assignments exceed the candidate staffing slot's approved FTE.",
                        entity_id=target.id,
                        path="employeeAssignments.fullTimeEquivalent",
                        details={
                            "approvedFte": str(target.full_time_equivalent),
                            "assignedFte": str(peak),
                            "assignmentIds": [str(item.id) for item in assignments],
                        },
                    )
                )
        return issues

    @staticmethod
    def _assignment_issues(
        assignments: tuple[EmployeeAssignmentModel, ...],
        slot_by_id: dict[UUID, StaffingSlotModel],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        active_assignments = tuple(
            item for item in assignments if item.status not in {"ended", "cancelled"}
        )
        primary_by_employee: dict[UUID, list[EmployeeAssignmentModel]] = defaultdict(list)
        assignments_by_slot: dict[UUID, list[EmployeeAssignmentModel]] = defaultdict(list)
        for assignment in active_assignments:
            assignments_by_slot[assignment.staffing_slot_id].append(assignment)
            if assignment.primary:
                primary_by_employee[assignment.employee_id].append(assignment)
            slot = slot_by_id.get(assignment.staffing_slot_id)
            if slot is None:
                issues.append(
                    ValidationIssue(
                        "ORG_STRUCTURE_INVALID_STAFFING_REFERENCE",
                        "An employee assignment references a staffing slot outside the version.",
                        entity_id=assignment.id,
                        path="staffingSlotId",
                    )
                )
                continue
            if (
                slot.effective_from is not None and assignment.effective_from < slot.effective_from
            ) or (
                slot.effective_to is not None
                and (assignment.effective_to is None or assignment.effective_to > slot.effective_to)
            ):
                issues.append(
                    ValidationIssue(
                        "ASSIGNMENT_DATE_CONFLICT",
                        "Assignment dates must fit within the staffing slot dates.",
                        entity_id=assignment.id,
                        path="effectiveFrom",
                        details={"staffingSlotId": str(slot.id)},
                    )
                )

        for employee_id, employee_assignments in primary_by_employee.items():
            for index, left in enumerate(employee_assignments):
                for right in employee_assignments[index + 1 :]:
                    if _ranges_overlap(
                        left.effective_from,
                        left.effective_to,
                        right.effective_from,
                        right.effective_to,
                    ):
                        issues.append(
                            ValidationIssue(
                                "EMPLOYEE_ALREADY_ASSIGNED",
                                "An employee has overlapping primary assignments.",
                                entity_id=employee_id,
                                path="employeeAssignments.primary",
                                details={"assignmentIds": [str(left.id), str(right.id)]},
                            )
                        )
        for slot_id, slot_assignments in assignments_by_slot.items():
            slot = slot_by_id.get(slot_id)
            if slot is None:
                continue
            peak = _peak_fte(slot_assignments)
            if peak > slot.full_time_equivalent:
                issues.append(
                    ValidationIssue(
                        "STAFFING_FTE_EXCEEDED",
                        "Active assignments exceed the staffing slot's approved FTE.",
                        entity_id=slot_id,
                        path="employeeAssignments.fullTimeEquivalent",
                        details={
                            "approvedFte": str(slot.full_time_equivalent),
                            "assignedFte": str(peak),
                        },
                    )
                )
        return issues

    @staticmethod
    def _delegation_issues(
        delegations: tuple[DelegationModel, ...],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for delegation in delegations:
            if delegation.delegator_employee_id == delegation.delegate_employee_id:
                issues.append(
                    ValidationIssue(
                        "DELEGATION_DATE_CONFLICT",
                        "Delegator and delegate must be different employees.",
                        entity_id=delegation.id,
                        path="delegateEmployeeId",
                    )
                )
            if delegation.effective_to <= delegation.effective_from:
                issues.append(
                    ValidationIssue(
                        "DELEGATION_DATE_CONFLICT",
                        "Delegation effectiveTo must be after effectiveFrom.",
                        entity_id=delegation.id,
                        path="effectiveTo",
                    )
                )
            if not delegation.delegated_permissions:
                issues.append(
                    ValidationIssue(
                        "DELEGATION_DATE_CONFLICT",
                        "A delegation must include at least one permission.",
                        entity_id=delegation.id,
                        path="delegatedPermissions",
                    )
                )
        return issues


def _ranges_overlap(
    left_from: date,
    left_to: date | None,
    right_from: date,
    right_to: date | None,
) -> bool:
    return (left_to is None or right_from <= left_to) and (
        right_to is None or left_from <= right_to
    )


def _peak_fte(
    assignments: list[EmployeeAssignmentModel], *, effective_from: date | None = None
) -> Decimal:
    relevant = [
        item
        for item in assignments
        if effective_from is None
        or item.effective_to is None
        or item.effective_to >= effective_from
    ]
    if not relevant:
        return Decimal("0")
    boundaries = {
        item.effective_from if effective_from is None else max(item.effective_from, effective_from)
        for item in relevant
    }
    boundaries.update(
        item.effective_to + timedelta(days=1)
        for item in relevant
        if item.effective_to is not None
        and (effective_from is None or item.effective_to >= effective_from)
    )
    peak = Decimal("0")
    for boundary in boundaries:
        total = sum(
            (
                item.full_time_equivalent
                for item in relevant
                if item.effective_from <= boundary
                and (item.effective_to is None or boundary <= item.effective_to)
            ),
            start=Decimal("0"),
        )
        peak = max(peak, total)
    return peak
