"""Database-authoritative employee actor resolution for API composition."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import or_, select

from app.core.database.session import async_session_factory
from app.core.errors import ForbiddenError, ScopeViolationError
from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.modules.access_control.domain.entities import ScopeType
from app.modules.access_control.domain.permissions import REQUIRED_PERMISSION_CODES
from app.modules.access_control.infrastructure.repositories import (
    SqlAlchemyRoleAssignmentRepository,
)
from app.modules.organization.infrastructure.authorization import (
    SqlAlchemyOrganizationScopeResolver,
)
from app.modules.organization.infrastructure.models import (
    OrganizationModel,
    OrganizationStructureVersionModel,
    OrganizationUnitModel,
)

from ..application.ports import Actor
from ..domain.enums import DelegationScopeType
from ..infrastructure.models import DelegationModel


async def _resolve_organization_id(principal: Principal, grant_organizations: set[UUID]) -> UUID:
    if principal.organization_id is not None:
        return principal.organization_id
    if len(grant_organizations) == 1:
        return next(iter(grant_organizations))
    if not grant_organizations:
        async with async_session_factory() as session:
            organizations = (
                await session.scalars(
                    select(OrganizationModel.id)
                    .where(OrganizationModel.status == "active")
                    .limit(2)
                )
            ).all()
        if len(organizations) == 1:
            return organizations[0]
    raise ScopeViolationError("An unambiguous organization context is required.")


def _descendants(
    own_units: frozenset[UUID], rows: list[tuple[UUID, UUID | None]]
) -> frozenset[UUID]:
    children: defaultdict[UUID, list[UUID]] = defaultdict(list)
    for unit_id, parent_id in rows:
        if parent_id is not None:
            children[parent_id].append(unit_id)
    result = set(own_units)
    stack = list(own_units)
    while stack:
        current = stack.pop()
        for child in children.get(current, ()):
            if child not in result:
                result.add(child)
                stack.append(child)
    return frozenset(result)


async def get_employee_actor(
    principal: Annotated[Principal, Depends(get_current_principal)],
    authorization: Annotated[AuthorizationPort, Depends(get_authorization_port)],
) -> Actor:
    """Resolve permissions and each permission's scope from active database grants."""

    now = datetime.now(UTC)
    async with async_session_factory() as session:
        assignments = SqlAlchemyRoleAssignmentRepository(session)
        grants_by_permission = {
            code: tuple(await assignments.active_grants(principal.user_id, code, effective_at=now))
            for code in REQUIRED_PERMISSION_CODES
        }
        grant_organizations = {
            grant.scope.organization_id
            for grants in grants_by_permission.values()
            for grant in grants
            if grant.scope.organization_id is not None
        }
        organization_id = await _resolve_organization_id(principal, grant_organizations)
        resolver = SqlAlchemyOrganizationScopeResolver(session)
        own_units = await resolver.user_unit_ids(
            principal.user_id, organization_id, effective_at=now
        )
        active_version_id = await session.scalar(
            select(OrganizationStructureVersionModel.id)
            .where(
                OrganizationStructureVersionModel.organization_id == organization_id,
                OrganizationStructureVersionModel.status == "published",
                OrganizationStructureVersionModel.effective_from <= date.today(),
                or_(
                    OrganizationStructureVersionModel.effective_to.is_(None),
                    OrganizationStructureVersionModel.effective_to >= date.today(),
                ),
            )
            .order_by(OrganizationStructureVersionModel.version_number.desc())
            .limit(1)
        )
        unit_rows: list[tuple[UUID, UUID | None]] = []
        unit_stable_keys: dict[UUID, UUID] = {}
        selected_unit_remap: dict[UUID, UUID] = {}
        if active_version_id is not None:
            unit_rows = list(
                (
                    await session.execute(
                        select(
                            OrganizationUnitModel.id,
                            OrganizationUnitModel.parent_unit_id,
                        ).where(
                            OrganizationUnitModel.structure_version_id == active_version_id,
                            OrganizationUnitModel.active.is_(True),
                        )
                    )
                ).tuples()
            )
            stable_key_rows = await session.execute(
                select(
                    OrganizationUnitModel.id,
                    OrganizationUnitModel.stable_key,
                ).where(
                    OrganizationUnitModel.structure_version_id == active_version_id,
                    OrganizationUnitModel.active.is_(True),
                )
            )
            unit_stable_keys = {unit_id: stable_key for unit_id, stable_key in stable_key_rows}
            selected_scope_unit_ids = {
                unit_id
                for grants in grants_by_permission.values()
                for grant in grants
                if grant.scope.scope_type is ScopeType.SELECTED_UNITS
                for unit_id in grant.scope.unit_ids
            }
            if selected_scope_unit_ids:
                source_key_rows = await session.execute(
                    select(
                        OrganizationUnitModel.id,
                        OrganizationUnitModel.stable_key,
                    ).where(OrganizationUnitModel.id.in_(selected_scope_unit_ids))
                )
                source_stable_keys = {
                    unit_id: stable_key for unit_id, stable_key in source_key_rows
                }
                current_by_stable_key = {
                    stable_key: unit_id for unit_id, stable_key in unit_stable_keys.items()
                }
                selected_unit_remap = {
                    source_id: current_by_stable_key[stable_key]
                    for source_id, stable_key in source_stable_keys.items()
                    if stable_key in current_by_stable_key
                }
        own_and_descendants = _descendants(own_units, unit_rows)
        active_delegations = (
            (
                await session.scalars(
                    select(DelegationModel).where(
                        DelegationModel.delegate_employee_id == principal.employee_id,
                        DelegationModel.status != "revoked",
                        DelegationModel.revoked_at.is_(None),
                        DelegationModel.effective_from <= now,
                        DelegationModel.effective_to > now,
                    )
                )
            ).all()
            if principal.employee_id is not None
            else []
        )

    permissions: set[str] = set()
    organization_permissions: set[str] = set()
    self_permissions: set[str] = set()
    unit_permissions: defaultdict[str, set[UUID]] = defaultdict(set)
    for permission, grants in grants_by_permission.items():
        for grant in grants:
            scope = grant.scope
            if scope.scope_type is ScopeType.SELF:
                permissions.add(permission)
                self_permissions.add(permission)
                continue
            if scope.organization_id != organization_id:
                continue
            permissions.add(permission)
            if scope.scope_type is ScopeType.ORGANIZATION:
                organization_permissions.add(permission)
            elif scope.scope_type is ScopeType.SELECTED_UNITS:
                unit_permissions[permission].update(
                    selected_unit_remap[unit_id]
                    for unit_id in scope.unit_ids
                    if unit_id in selected_unit_remap
                )
            elif scope.scope_type is ScopeType.OWN_UNIT:
                unit_permissions[permission].update(own_units)
            elif scope.scope_type is ScopeType.OWN_UNIT_AND_DESCENDANTS:
                unit_permissions[permission].update(own_and_descendants)

    all_unit_ids = tuple(unit_id for unit_id, _parent_id in unit_rows)
    for delegation in active_delegations:
        for permission in set(delegation.delegated_permissions).intersection(
            REQUIRED_PERMISSION_CODES
        ):
            scope_type = DelegationScopeType(delegation.scope_type)
            candidate_units: tuple[UUID, ...] = ()
            try_organization = scope_type in {
                DelegationScopeType.PERMISSIONS,
                DelegationScopeType.ORGANIZATION,
            }
            if scope_type is DelegationScopeType.UNIT:
                # Evaluate every current unit; the authorization adapter maps the
                # stored version-specific reference through the stable unit key.
                candidate_units = all_unit_ids
            elif scope_type is DelegationScopeType.PERMISSIONS:
                candidate_units = all_unit_ids

            if try_organization:
                try:
                    await authorization.require(
                        principal=principal,
                        permission_code=permission,
                        organization_id=organization_id,
                    )
                    permissions.add(permission)
                    organization_permissions.add(permission)
                    continue
                except (ForbiddenError, ScopeViolationError):
                    pass
            for unit_id in candidate_units:
                try:
                    await authorization.require(
                        principal=principal,
                        permission_code=permission,
                        organization_id=organization_id,
                        unit_id=unit_id,
                    )
                    permissions.add(permission)
                    unit_permissions[permission].add(unit_id)
                except (ForbiddenError, ScopeViolationError):
                    continue

    return Actor(
        user_id=principal.user_id,
        employee_id=principal.employee_id,
        organization_id=organization_id,
        permissions=frozenset(permissions),
        organization_wide_permissions=frozenset(organization_permissions),
        permission_unit_ids={
            code: frozenset(unit_ids) for code, unit_ids in unit_permissions.items()
        },
        permission_unit_stable_keys={
            code: frozenset(
                unit_stable_keys[unit_id] for unit_id in unit_ids if unit_id in unit_stable_keys
            )
            for code, unit_ids in unit_permissions.items()
        },
        self_permissions=frozenset(self_permissions),
    )
