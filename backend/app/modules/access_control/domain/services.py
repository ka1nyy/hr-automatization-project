"""Pure scope evaluation rules."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection
from uuid import UUID

from app.modules.access_control.domain.entities import AccessScope, ScopeType


async def scope_allows(
    scope: AccessScope,
    *,
    actor_user_id: UUID,
    target_user_id: UUID | None,
    target_organization_id: UUID | None,
    target_unit_id: UUID | None,
    actor_unit_ids: Collection[UUID],
    is_descendant_or_same: Callable[[UUID, UUID], Awaitable[bool]],
) -> bool:
    """Evaluate a grant against an explicit resource context.

    Unit-scoped grants intentionally fail closed when the resource has no unit.
    """

    if scope.scope_type is ScopeType.SELF:
        return (
            target_user_id is not None
            and target_user_id == actor_user_id
            and target_organization_id is not None
            and scope.organization_id == target_organization_id
        )

    if target_organization_id is None or scope.organization_id != target_organization_id:
        return False

    if scope.scope_type is ScopeType.ORGANIZATION:
        return True

    if target_unit_id is None:
        return False

    if scope.scope_type is ScopeType.SELECTED_UNITS:
        for selected_unit_id in scope.unit_ids:
            if selected_unit_id == target_unit_id:
                return True
            # Stable organization units receive new row IDs in each published version.
            # Mutual ancestry is true only for the same stable unit, not descendants.
            if await is_descendant_or_same(
                selected_unit_id, target_unit_id
            ) and await is_descendant_or_same(target_unit_id, selected_unit_id):
                return True
        return False

    if scope.scope_type is ScopeType.OWN_UNIT:
        for own_unit_id in actor_unit_ids:
            if own_unit_id == target_unit_id:
                return True
            if await is_descendant_or_same(
                own_unit_id, target_unit_id
            ) and await is_descendant_or_same(target_unit_id, own_unit_id):
                return True
        return False

    if scope.scope_type is ScopeType.OWN_UNIT_AND_DESCENDANTS:
        for own_unit_id in actor_unit_ids:
            if await is_descendant_or_same(own_unit_id, target_unit_id):
                return True
        return False
