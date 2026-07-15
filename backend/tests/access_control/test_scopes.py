"""Organization scope evaluation fails closed and honors descendant boundaries."""

from uuid import uuid4

import pytest
from app.modules.access_control.domain.entities import AccessScope, ScopeType
from app.modules.access_control.domain.services import scope_allows


async def never_descendant(_ancestor, _candidate):  # type: ignore[no-untyped-def]
    return False


def test_self_scope_requires_an_organization() -> None:
    with pytest.raises(ValueError, match="organization_id is required"):
        AccessScope(scope_type=ScopeType.SELF)


@pytest.mark.asyncio
async def test_self_scope_requires_the_target_user_and_organization() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    scope = AccessScope(scope_type=ScopeType.SELF, organization_id=organization_id)

    assert await scope_allows(
        scope,
        actor_user_id=actor_id,
        target_user_id=actor_id,
        target_organization_id=organization_id,
        target_unit_id=None,
        actor_unit_ids=(),
        is_descendant_or_same=never_descendant,
    )
    assert not await scope_allows(
        scope,
        actor_user_id=actor_id,
        target_user_id=actor_id,
        target_organization_id=uuid4(),
        target_unit_id=None,
        actor_unit_ids=(),
        is_descendant_or_same=never_descendant,
    )


@pytest.mark.asyncio
async def test_selected_unit_rejects_id_substitution() -> None:
    organization_id = uuid4()
    allowed_unit = uuid4()
    supplied_other_unit = uuid4()
    scope = AccessScope(
        scope_type=ScopeType.SELECTED_UNITS,
        organization_id=organization_id,
        unit_ids=frozenset({allowed_unit}),
    )
    assert not await scope_allows(
        scope,
        actor_user_id=uuid4(),
        target_user_id=None,
        target_organization_id=organization_id,
        target_unit_id=supplied_other_unit,
        actor_unit_ids=(),
        is_descendant_or_same=never_descendant,
    )


@pytest.mark.asyncio
async def test_own_unit_and_descendants_allows_only_resolved_branch() -> None:
    organization_id = uuid4()
    own_unit = uuid4()
    descendant = uuid4()

    async def resolver(ancestor, candidate):  # type: ignore[no-untyped-def]
        return ancestor == own_unit and candidate == descendant

    scope = AccessScope(
        scope_type=ScopeType.OWN_UNIT_AND_DESCENDANTS,
        organization_id=organization_id,
    )
    assert await scope_allows(
        scope,
        actor_user_id=uuid4(),
        target_user_id=None,
        target_organization_id=organization_id,
        target_unit_id=descendant,
        actor_unit_ids=(own_unit,),
        is_descendant_or_same=resolver,
    )
    assert not await scope_allows(
        scope,
        actor_user_id=uuid4(),
        target_user_id=None,
        target_organization_id=uuid4(),
        target_unit_id=descendant,
        actor_unit_ids=(own_unit,),
        is_descendant_or_same=resolver,
    )


@pytest.mark.asyncio
async def test_unit_scope_fails_closed_without_stored_target_unit() -> None:
    scope = AccessScope(scope_type=ScopeType.OWN_UNIT, organization_id=uuid4())
    assert not await scope_allows(
        scope,
        actor_user_id=uuid4(),
        target_user_id=None,
        target_organization_id=scope.organization_id,
        target_unit_id=None,
        actor_unit_ids=(uuid4(),),
        is_descendant_or_same=never_descendant,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("scope_type", [ScopeType.SELECTED_UNITS, ScopeType.OWN_UNIT])
async def test_exact_unit_scopes_follow_stable_identity_across_versions(
    scope_type: ScopeType,
) -> None:
    organization_id = uuid4()
    prior_version_unit = uuid4()
    current_version_unit = uuid4()
    current_descendant = uuid4()

    async def resolver(ancestor, candidate):  # type: ignore[no-untyped-def]
        return (ancestor, candidate) in {
            (prior_version_unit, current_version_unit),
            (current_version_unit, prior_version_unit),
            (prior_version_unit, current_descendant),
        }

    scope = AccessScope(
        scope_type=scope_type,
        organization_id=organization_id,
        unit_ids=(
            frozenset({prior_version_unit})
            if scope_type is ScopeType.SELECTED_UNITS
            else frozenset()
        ),
    )
    common = {
        "actor_user_id": uuid4(),
        "target_user_id": None,
        "target_organization_id": organization_id,
        "actor_unit_ids": (prior_version_unit,),
        "is_descendant_or_same": resolver,
    }
    assert await scope_allows(scope, target_unit_id=current_version_unit, **common)
    assert not await scope_allows(scope, target_unit_id=current_descendant, **common)
