"""Tenant-bound role-assignment authorization tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from app.core.errors import ForbiddenError, ScopeViolationError
from app.modules.access_control.application.authorization import (
    AuthorizationContext,
    AuthorizationService,
)
from app.modules.access_control.application.facade import (
    AccessActor,
    AuthorizedAccessControlService,
)
from app.modules.access_control.application.services import (
    AccessControlService,
    AssignRoleCommand,
)
from app.modules.access_control.domain.entities import AccessScope, ScopeType, UserRoleAssignment


def _command(*, user_id: UUID, role_id: UUID) -> AssignRoleCommand:
    return AssignRoleCommand(
        user_id=user_id,
        role_id=role_id,
        scope_type=ScopeType.SELF,
        effective_from=datetime.now(UTC),
    )


def _assignment(*, user_id: UUID, role_id: UUID, organization_id: UUID) -> UserRoleAssignment:
    return UserRoleAssignment(
        user_id=user_id,
        role_id=role_id,
        scope=AccessScope(scope_type=ScopeType.SELF, organization_id=organization_id),
        effective_from=datetime.now(UTC),
    )


def _service() -> tuple[
    AuthorizedAccessControlService,
    Mock,
    Mock,
]:
    access = Mock(spec=AccessControlService)
    authorization = Mock(spec=AuthorizationService)
    authorization.require = AsyncMock()
    authorization.is_organization_member = AsyncMock()
    return AuthorizedAccessControlService(access, authorization), access, authorization


@pytest.mark.asyncio
async def test_self_assignment_binds_actor_organization_for_a_verified_member() -> None:
    service, access, authorization = _service()
    actor = AccessActor(user_id=uuid4(), organization_id=uuid4())
    target_user_id = uuid4()
    role_id = uuid4()
    expected = _assignment(
        user_id=target_user_id,
        role_id=role_id,
        organization_id=actor.organization_id,
    )
    authorization.is_organization_member.return_value = True
    access.assign_role = AsyncMock(return_value=expected)

    result = await service.assign_role(
        _command(user_id=target_user_id, role_id=role_id),
        actor=actor,
    )

    assert result is expected
    authorization.require.assert_awaited_once_with(
        actor_user_id=actor.user_id,
        permission_code="roles.manage",
        context=AuthorizationContext(organization_id=actor.organization_id),
    )
    authorization.is_organization_member.assert_awaited_once_with(
        user_id=target_user_id,
        organization_id=actor.organization_id,
    )
    saved_command = access.assign_role.await_args.args[0]
    assert saved_command.organization_id == actor.organization_id


@pytest.mark.asyncio
async def test_self_assignment_rejects_user_outside_actor_organization() -> None:
    service, access, authorization = _service()
    actor = AccessActor(user_id=uuid4(), organization_id=uuid4())
    authorization.is_organization_member.return_value = False

    with pytest.raises(ScopeViolationError):
        await service.assign_role(
            _command(user_id=uuid4(), role_id=uuid4()),
            actor=actor,
        )

    access.assign_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_unbound_self_revocation_rejects_cross_organization_target() -> None:
    service, access, authorization = _service()
    actor = AccessActor(user_id=uuid4(), organization_id=uuid4())
    target_user_id = uuid4()
    assignment_id = uuid4()
    legacy_assignment = SimpleNamespace(
        user_id=target_user_id,
        scope=SimpleNamespace(scope_type=ScopeType.SELF, organization_id=None),
    )
    access.get_role_assignment = AsyncMock(return_value=legacy_assignment)
    access.revoke_role_assignment = AsyncMock()
    authorization.is_organization_member.return_value = False

    async def require(**kwargs: object) -> None:
        context = kwargs["context"]
        assert isinstance(context, AuthorizationContext)
        if context.organization_id is None:
            raise ForbiddenError()

    authorization.require.side_effect = require

    with pytest.raises(ScopeViolationError):
        await service.revoke_role_assignment(
            assignment_id,
            actor=actor,
            reason="Access is no longer required",
            expected_revision=1,
        )

    authorization.is_organization_member.assert_awaited_once_with(
        user_id=target_user_id,
        organization_id=actor.organization_id,
    )
    access.revoke_role_assignment.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_unbound_self_revocation_allows_verified_local_member() -> None:
    service, access, authorization = _service()
    actor = AccessActor(user_id=uuid4(), organization_id=uuid4())
    target_user_id = uuid4()
    assignment_id = uuid4()
    expected = _assignment(
        user_id=target_user_id,
        role_id=uuid4(),
        organization_id=actor.organization_id,
    )
    legacy_assignment = SimpleNamespace(
        user_id=target_user_id,
        scope=SimpleNamespace(scope_type=ScopeType.SELF, organization_id=None),
    )
    access.get_role_assignment = AsyncMock(return_value=legacy_assignment)
    access.revoke_role_assignment = AsyncMock(return_value=expected)
    authorization.is_organization_member.return_value = True

    result = await service.revoke_role_assignment(
        assignment_id,
        actor=actor,
        reason="Access is no longer required",
        expected_revision=1,
    )

    assert result is expected
    access.revoke_role_assignment.assert_awaited_once_with(
        assignment_id,
        actor_id=actor.user_id,
        reason="Access is no longer required",
        expected_revision=1,
    )
