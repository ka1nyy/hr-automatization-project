"""Session-factory wrapper for organization scope reads used during authorization."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.access_control.application.ports import OrganizationScopeResolver

from .authorization import SqlAlchemyOrganizationScopeResolver


class SessionFactoryOrganizationScopeResolver(OrganizationScopeResolver):
    """Give authorization reads their own short-lived session.

    This prevents permission checks from opening an implicit transaction on a business
    mutation's request session while still sharing the same committed PostgreSQL state.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def user_unit_ids(
        self,
        user_id: UUID,
        organization_id: UUID,
        *,
        effective_at: datetime,
    ) -> frozenset[UUID]:
        async with self._session_factory() as session:
            resolver = SqlAlchemyOrganizationScopeResolver(session)
            return await resolver.user_unit_ids(user_id, organization_id, effective_at=effective_at)

    async def is_descendant_or_same(
        self,
        organization_id: UUID,
        ancestor_unit_id: UUID,
        candidate_unit_id: UUID,
        *,
        effective_at: datetime,
    ) -> bool:
        async with self._session_factory() as session:
            resolver = SqlAlchemyOrganizationScopeResolver(session)
            return await resolver.is_descendant_or_same(
                organization_id,
                ancestor_unit_id,
                candidate_unit_id,
                effective_at=effective_at,
            )
