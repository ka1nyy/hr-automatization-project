"""Anti-corruption adapter from organization persistence to employee staffing snapshots."""

from datetime import date
from uuid import UUID

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organization.infrastructure.models import (
    OrganizationPolicyModel,
    OrganizationStructureVersionModel,
    OrganizationUnitModel,
    StaffingSlotModel,
)

from ..application.ports import (
    EmployeePolicyReader,
    EmployeePolicySnapshot,
    StaffingSlotReader,
    StaffingSlotSnapshot,
)


class SqlAlchemyStaffingSlotReader(StaffingSlotReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, staffing_slot_id: UUID) -> StaffingSlotSnapshot | None:
        row = (
            await self._session.execute(
                select(
                    StaffingSlotModel,
                    OrganizationStructureVersionModel.organization_id,
                    OrganizationUnitModel.stable_key,
                    OrganizationStructureVersionModel.status,
                    OrganizationStructureVersionModel.effective_from,
                    OrganizationStructureVersionModel.effective_to,
                )
                .join(
                    OrganizationStructureVersionModel,
                    OrganizationStructureVersionModel.id == StaffingSlotModel.structure_version_id,
                )
                .join(
                    OrganizationUnitModel,
                    OrganizationUnitModel.id == StaffingSlotModel.organization_unit_id,
                )
                .where(StaffingSlotModel.id == staffing_slot_id)
            )
        ).one_or_none()
        if row is None:
            return None
        (
            slot,
            organization_id,
            unit_stable_key,
            structure_status,
            structure_effective_from,
            structure_effective_to,
        ) = row
        return StaffingSlotSnapshot(
            id=slot.id,
            organization_id=organization_id,
            organization_unit_id=slot.organization_unit_id,
            structure_version_id=slot.structure_version_id,
            full_time_equivalent=slot.full_time_equivalent,
            status=slot.status,
            effective_from=slot.effective_from or date.min,
            effective_to=slot.effective_to,
            organization_unit_stable_key=unit_stable_key,
            structure_status=structure_status,
            structure_effective_from=structure_effective_from,
            structure_effective_to=structure_effective_to,
        )


class SqlAlchemyEmployeePolicyReader(EmployeePolicyReader):
    """Read the effective organization policy without leaking its ORM into use cases."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def current(self, organization_id: UUID, *, effective_on: date) -> EmployeePolicySnapshot:
        active_version_id = await self._session.scalar(
            select(OrganizationStructureVersionModel.id)
            .where(
                OrganizationStructureVersionModel.organization_id == organization_id,
                OrganizationStructureVersionModel.status == "published",
                OrganizationStructureVersionModel.effective_from <= effective_on,
                or_(
                    OrganizationStructureVersionModel.effective_to.is_(None),
                    OrganizationStructureVersionModel.effective_to >= effective_on,
                ),
            )
            .order_by(
                OrganizationStructureVersionModel.effective_from.desc(),
                OrganizationStructureVersionModel.version_number.desc(),
            )
            .limit(1)
        )
        policy = await self._session.scalar(
            select(OrganizationPolicyModel)
            .where(
                OrganizationPolicyModel.organization_id == organization_id,
                or_(
                    OrganizationPolicyModel.structure_version_id == active_version_id,
                    OrganizationPolicyModel.structure_version_id.is_(None),
                ),
                or_(
                    OrganizationPolicyModel.effective_from.is_(None),
                    OrganizationPolicyModel.effective_from <= effective_on,
                ),
                or_(
                    OrganizationPolicyModel.effective_to.is_(None),
                    OrganizationPolicyModel.effective_to >= effective_on,
                ),
            )
            .order_by(
                case(
                    (OrganizationPolicyModel.structure_version_id == active_version_id, 0),
                    else_=1,
                ),
                OrganizationPolicyModel.revision.desc(),
            )
            .limit(1)
        )
        if policy is None:
            return EmployeePolicySnapshot()
        return EmployeePolicySnapshot(
            managers_can_create_employee_drafts=policy.managers_can_create_employee_drafts,
            managers_can_assign_existing_employees=(policy.managers_can_assign_existing_employees),
            manager_changes_require_hr_approval=(policy.manager_changes_require_hr_approval),
        )
