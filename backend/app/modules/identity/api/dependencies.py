"""Resolve an authenticated provider subject to an active internal account."""

from dataclasses import replace
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import or_, select

from app.core.database.session import async_session_factory
from app.core.errors import ApplicationError, UnauthenticatedError
from app.core.security.identity import Principal
from app.modules.access_control.infrastructure.models import (
    AccessScopeModel,
    UserRoleAssignmentModel,
)
from app.modules.identity.infrastructure.models import UserAccountModel


async def get_database_principal(request: Request) -> Principal:
    """Return the active internal identity for the already verified provider principal."""

    error = getattr(request.state, "authentication_error", None)
    if isinstance(error, ApplicationError):
        raise error
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal):
        raise UnauthenticatedError()

    issuer = str(principal.attributes.get("issuer", "")).strip()
    subjects = {principal.subject}
    if issuer:
        subjects.add(f"{issuer}:{principal.subject}")
    async with async_session_factory() as session:
        account = await session.scalar(
            select(UserAccountModel).where(
                UserAccountModel.active.is_(True),
                UserAccountModel.status == "active",
                or_(
                    UserAccountModel.id == principal.user_id,
                    UserAccountModel.external_subject.in_(subjects),
                ),
            )
        )
        organization_id = principal.organization_id
        if account is not None and organization_id is None:
            now = datetime.now(UTC)
            organizations = (
                await session.scalars(
                    select(AccessScopeModel.organization_id)
                    .join(
                        UserRoleAssignmentModel,
                        UserRoleAssignmentModel.scope_id == AccessScopeModel.id,
                    )
                    .where(
                        UserRoleAssignmentModel.user_id == account.id,
                        UserRoleAssignmentModel.revoked_at.is_(None),
                        UserRoleAssignmentModel.effective_from <= now,
                        or_(
                            UserRoleAssignmentModel.effective_to.is_(None),
                            UserRoleAssignmentModel.effective_to > now,
                        ),
                        AccessScopeModel.organization_id.is_not(None),
                    )
                    .distinct()
                    .limit(2)
                )
            ).all()
            if len(organizations) == 1:
                organization_id = organizations[0]
    if account is None:
        raise UnauthenticatedError("The authenticated identity is not linked to an active account.")
    return replace(
        principal,
        user_id=account.id,
        organization_id=organization_id,
        employee_id=account.employee_id,
        permissions=frozenset(),
        role_codes=frozenset(),
        unit_ids=frozenset(),
    )
