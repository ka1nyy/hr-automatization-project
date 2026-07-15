"""Request-scoped production composition for the organization API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_session
from app.core.logging.context import get_request_id
from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.modules.access_control.application.ports import OrganizationScopeResolver
from app.modules.organization.application.service import OrganizationService
from app.modules.organization.domain.ports import Actor
from app.modules.organization.infrastructure.authorization import (
    CoreOrganizationAuthorizationAdapter,
    SqlAlchemyOrganizationScopeResolver,
)
from app.modules.organization.infrastructure.external_validation import (
    SqlAlchemyExternalStructureValidationAdapter,
)
from app.modules.organization.infrastructure.uow import (
    SqlAlchemyOrganizationUnitOfWorkFactory,
)

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
AuthorizationDependency = Annotated[AuthorizationPort, Depends(get_authorization_port)]


def get_organization_scope_resolver(
    session: SessionDependency,
) -> OrganizationScopeResolver:
    """Override access_control's fail-closed resolver with this dependency."""

    return SqlAlchemyOrganizationScopeResolver(session)


def get_organization_service(
    session: SessionDependency,
    principal: PrincipalDependency,
    authorization: AuthorizationDependency,
) -> OrganizationService:
    return OrganizationService(
        SqlAlchemyOrganizationUnitOfWorkFactory(session),
        authorizer=CoreOrganizationAuthorizationAdapter(authorization, principal),
        external_validator=SqlAlchemyExternalStructureValidationAdapter(session),
    )


def get_organization_actor(principal: PrincipalDependency) -> Actor:
    try:
        request_id = UUID(get_request_id())
    except ValueError:
        request_id = None
    return Actor(
        user_id=principal.user_id,
        organization_id=principal.organization_id,
        request_id=request_id,
    )
