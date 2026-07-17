from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.core.security.identity import Principal
from app.modules.absence.api.routes import _require


@pytest.mark.asyncio
async def test_self_service_permissions_bind_the_current_user_as_subject() -> None:
    authorization = AsyncMock()
    organization_id = uuid4()
    principal = Principal(user_id=uuid4(), subject="development:employee")

    await _require(authorization, principal, "leave.request", organization_id)

    authorization.require.assert_awaited_once_with(
        principal=principal,
        permission_code="leave.request",
        organization_id=organization_id,
        unit_id=None,
        subject_user_id=principal.user_id,
    )


@pytest.mark.asyncio
async def test_organization_permissions_do_not_receive_a_self_subject() -> None:
    authorization = AsyncMock()
    organization_id = uuid4()
    principal = Principal(user_id=uuid4(), subject="development:hr")

    await _require(authorization, principal, "absence.read_all", organization_id)

    authorization.require.assert_awaited_once_with(
        principal=principal,
        permission_code="absence.read_all",
        organization_id=organization_id,
        unit_id=None,
        subject_user_id=None,
    )
