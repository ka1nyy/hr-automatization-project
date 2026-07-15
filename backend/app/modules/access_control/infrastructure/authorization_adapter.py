"""Adapter from the core authorization contract to database-backed access control."""

from __future__ import annotations

from uuid import UUID

from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.modules.access_control.application.authorization import (
    AuthorizationContext,
    AuthorizationService,
)


class DatabaseAuthorizationAdapter(AuthorizationPort):
    def __init__(self, authorization: AuthorizationService) -> None:
        self._authorization = authorization

    async def require(
        self,
        *,
        principal: Principal,
        permission_code: str,
        organization_id: UUID | None = None,
        unit_id: UUID | None = None,
        subject_user_id: UUID | None = None,
    ) -> None:
        await self._authorization.require(
            actor_user_id=principal.user_id,
            permission_code=permission_code,
            context=AuthorizationContext(
                organization_id=organization_id,
                unit_id=unit_id,
                subject_user_id=subject_user_id,
            ),
        )
