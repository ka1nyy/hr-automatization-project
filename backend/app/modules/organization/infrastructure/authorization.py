"""Adapters connecting organization use cases to authoritative access control."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.modules.employees.infrastructure.models import EmployeeAssignmentModel
from app.modules.identity.infrastructure.models import UserAccountModel
from app.modules.organization.domain.errors import PermissionDeniedError
from app.modules.organization.domain.ports import Actor
from app.modules.organization.infrastructure.models import (
    OrganizationStructureVersionModel,
    OrganizationUnitModel,
    StaffingSlotModel,
)


class CoreOrganizationAuthorizationAdapter:
    """Delegates every decision to the database-backed core authorization port."""

    def __init__(self, authorization: AuthorizationPort, principal: Principal) -> None:
        self._authorization = authorization
        self._principal = principal

    async def require(
        self,
        actor: Actor,
        permission: str,
        organization_id: UUID,
        *,
        unit_id: UUID | None = None,
    ) -> None:
        if actor.user_id != self._principal.user_id:
            raise PermissionDeniedError(permission, scope_violation=True)
        await self._authorization.require(
            principal=self._principal,
            permission_code=permission,
            organization_id=organization_id,
            unit_id=unit_id,
        )


class SqlAlchemyOrganizationScopeResolver:
    """Resolve own-unit scopes across versioned trees using stable unit keys."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def user_unit_ids(
        self,
        user_id: UUID,
        organization_id: UUID,
        *,
        effective_at: datetime,
    ) -> frozenset[UUID]:
        effective_date = effective_at.date()
        stable_keys = tuple(
            (
                await self._session.scalars(
                    select(OrganizationUnitModel.stable_key)
                    .join(
                        StaffingSlotModel,
                        StaffingSlotModel.organization_unit_id == OrganizationUnitModel.id,
                    )
                    .join(
                        EmployeeAssignmentModel,
                        EmployeeAssignmentModel.staffing_slot_id == StaffingSlotModel.id,
                    )
                    .join(
                        UserAccountModel,
                        UserAccountModel.employee_id == EmployeeAssignmentModel.employee_id,
                    )
                    .join(
                        OrganizationStructureVersionModel,
                        OrganizationStructureVersionModel.id
                        == StaffingSlotModel.structure_version_id,
                    )
                    .where(
                        UserAccountModel.id == user_id,
                        UserAccountModel.active.is_(True),
                        OrganizationStructureVersionModel.organization_id == organization_id,
                        EmployeeAssignmentModel.status.in_(
                            ("planned", "active", "scheduled_end", "ended")
                        ),
                        EmployeeAssignmentModel.effective_from <= effective_date,
                        or_(
                            EmployeeAssignmentModel.effective_to.is_(None),
                            EmployeeAssignmentModel.effective_to >= effective_date,
                        ),
                        or_(
                            EmployeeAssignmentModel.primary.is_(True),
                            EmployeeAssignmentModel.acting.is_(True),
                        ),
                    )
                    .distinct()
                )
            ).all()
        )
        if not stable_keys:
            return frozenset()
        active_version_id = await self._session.scalar(
            select(OrganizationStructureVersionModel.id)
            .where(
                OrganizationStructureVersionModel.organization_id == organization_id,
                OrganizationStructureVersionModel.status == "published",
                OrganizationStructureVersionModel.effective_from.is_not(None),
                OrganizationStructureVersionModel.effective_from <= effective_date,
                or_(
                    OrganizationStructureVersionModel.effective_to.is_(None),
                    OrganizationStructureVersionModel.effective_to >= effective_date,
                ),
            )
            .order_by(
                OrganizationStructureVersionModel.effective_from.desc(),
                OrganizationStructureVersionModel.version_number.desc(),
            )
            .limit(1)
        )
        if active_version_id is None:
            return frozenset()
        unit_ids = (
            await self._session.scalars(
                select(OrganizationUnitModel.id).where(
                    OrganizationUnitModel.structure_version_id == active_version_id,
                    OrganizationUnitModel.stable_key.in_(stable_keys),
                    OrganizationUnitModel.active.is_(True),
                )
            )
        ).all()
        return frozenset(unit_ids)

    async def is_descendant_or_same(
        self,
        organization_id: UUID,
        ancestor_unit_id: UUID,
        candidate_unit_id: UUID,
        *,
        effective_at: datetime,
    ) -> bool:
        del effective_at  # Tree identity is resolved by the candidate's explicit version.
        ancestor_stable_key = await self._session.scalar(
            select(OrganizationUnitModel.stable_key)
            .join(
                OrganizationStructureVersionModel,
                OrganizationStructureVersionModel.id == OrganizationUnitModel.structure_version_id,
            )
            .where(
                OrganizationUnitModel.id == ancestor_unit_id,
                OrganizationStructureVersionModel.organization_id == organization_id,
            )
        )
        candidate = (
            await self._session.execute(
                select(
                    OrganizationUnitModel.id,
                    OrganizationUnitModel.structure_version_id,
                    OrganizationUnitModel.parent_unit_id,
                )
                .join(
                    OrganizationStructureVersionModel,
                    OrganizationStructureVersionModel.id
                    == OrganizationUnitModel.structure_version_id,
                )
                .where(
                    OrganizationUnitModel.id == candidate_unit_id,
                    OrganizationUnitModel.active.is_(True),
                    OrganizationStructureVersionModel.organization_id == organization_id,
                )
            )
        ).one_or_none()
        if ancestor_stable_key is None or candidate is None:
            return False
        mapped_ancestor_id = await self._session.scalar(
            select(OrganizationUnitModel.id).where(
                OrganizationUnitModel.structure_version_id == candidate.structure_version_id,
                OrganizationUnitModel.stable_key == ancestor_stable_key,
                OrganizationUnitModel.active.is_(True),
            )
        )
        if mapped_ancestor_id is None:
            return False
        current_id: UUID | None = candidate.id
        parent_id: UUID | None = candidate.parent_unit_id
        seen: set[UUID] = set()
        while current_id is not None:
            if current_id == mapped_ancestor_id:
                return True
            if current_id in seen:
                return False
            seen.add(current_id)
            if parent_id is None:
                return False
            row = (
                await self._session.execute(
                    select(
                        OrganizationUnitModel.id,
                        OrganizationUnitModel.parent_unit_id,
                    ).where(
                        and_(
                            OrganizationUnitModel.id == parent_id,
                            OrganizationUnitModel.structure_version_id
                            == candidate.structure_version_id,
                            OrganizationUnitModel.active.is_(True),
                        )
                    )
                )
            ).one_or_none()
            if row is None:
                return False
            current_id = row.id
            parent_id = row.parent_unit_id
        return False
