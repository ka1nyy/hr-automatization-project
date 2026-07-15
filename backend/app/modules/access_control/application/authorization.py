"""Authoritative RBAC plus organization-scope checks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import ForbiddenError, ScopeViolationError
from app.modules.access_control.application.ports import (
    AccessControlTransaction,
    OrganizationScopeResolver,
)
from app.modules.access_control.domain.services import scope_allows


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorizationContext:
    """Resource attributes supplied by a use case, never trusted from identity alone."""

    organization_id: UUID | None = None
    unit_id: UUID | None = None
    subject_user_id: UUID | None = None


class AuthorizationService:
    def __init__(
        self,
        transaction_factory: Callable[[], AccessControlTransaction],
        organization_resolver: OrganizationScopeResolver,
    ) -> None:
        self._transaction_factory = transaction_factory
        self._organization_resolver = organization_resolver

    async def is_organization_member(
        self,
        *,
        user_id: UUID,
        organization_id: UUID,
        effective_at: datetime | None = None,
    ) -> bool:
        """Check current membership using the authoritative organization adapter."""

        unit_ids = await self._organization_resolver.user_unit_ids(
            user_id,
            organization_id,
            effective_at=effective_at or datetime.now(UTC),
        )
        return bool(unit_ids)

    async def is_allowed(
        self,
        *,
        actor_user_id: UUID,
        permission_code: str,
        context: AuthorizationContext,
        effective_at: datetime | None = None,
    ) -> bool:
        at = effective_at or datetime.now(UTC)
        async with self._transaction_factory() as transaction:
            grants = await transaction.assignments.active_grants(
                actor_user_id,
                permission_code,
                effective_at=at,
            )

        actor_units: frozenset[UUID] = frozenset()
        if context.organization_id is not None:
            actor_units = await self._organization_resolver.user_unit_ids(
                actor_user_id,
                context.organization_id,
                effective_at=at,
            )

        async def descendant(ancestor_id: UUID, candidate_id: UUID) -> bool:
            if context.organization_id is None:
                return False
            return await self._organization_resolver.is_descendant_or_same(
                context.organization_id,
                ancestor_id,
                candidate_id,
                effective_at=at,
            )

        for grant in grants:
            if await scope_allows(
                grant.scope,
                actor_user_id=actor_user_id,
                target_user_id=context.subject_user_id,
                target_organization_id=context.organization_id,
                target_unit_id=context.unit_id,
                actor_unit_ids=actor_units,
                is_descendant_or_same=descendant,
            ):
                return True
        return False

    async def require(
        self,
        *,
        actor_user_id: UUID,
        permission_code: str,
        context: AuthorizationContext,
        effective_at: datetime | None = None,
    ) -> None:
        allowed = await self.is_allowed(
            actor_user_id=actor_user_id,
            permission_code=permission_code,
            context=context,
            effective_at=effective_at,
        )
        if allowed:
            return
        if context.unit_id is not None:
            raise ScopeViolationError(
                f"Permission {permission_code!r} does not cover the requested organization unit"
            )
        raise ForbiddenError(f"Permission {permission_code!r} is required")


class DenyAllOrganizationScopeResolver:
    """Safe default used until the organization module supplies the real resolver."""

    async def user_unit_ids(
        self,
        user_id: UUID,
        organization_id: UUID,
        *,
        effective_at: datetime,
    ) -> frozenset[UUID]:
        return frozenset()

    async def is_descendant_or_same(
        self,
        organization_id: UUID,
        ancestor_unit_id: UUID,
        candidate_unit_id: UUID,
        *,
        effective_at: datetime,
    ) -> bool:
        return False
