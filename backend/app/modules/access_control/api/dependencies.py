"""Composition dependencies for the access-control API."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import async_session_factory, get_session
from app.core.security.ports import AuthorizationPort
from app.modules.access_control.application.authorization import (
    AuthorizationService,
    DenyAllOrganizationScopeResolver,
)
from app.modules.access_control.application.facade import AuthorizedAccessControlService
from app.modules.access_control.application.ports import (
    AccessControlTransaction,
    OrganizationScopeResolver,
)
from app.modules.access_control.application.services import AccessControlService
from app.modules.access_control.infrastructure.authorization_adapter import (
    DatabaseAuthorizationAdapter,
)
from app.modules.access_control.infrastructure.change_recorder import (
    SqlAlchemyAccessChangeRecorder,
)
from app.modules.access_control.infrastructure.repositories import (
    SqlAlchemyAccessControlTransaction,
)

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_organization_scope_resolver() -> OrganizationScopeResolver:
    """Fail-closed default; main composition can override with organization's adapter."""

    return DenyAllOrganizationScopeResolver()


def get_authorized_access_service(
    session: SessionDependency,
    scope_resolver: Annotated[
        OrganizationScopeResolver,
        Depends(get_organization_scope_resolver),
    ],
) -> AuthorizedAccessControlService:
    def transaction_factory() -> AccessControlTransaction:
        return SqlAlchemyAccessControlTransaction(session)

    access = AccessControlService(
        transaction_factory,
        change_recorder=SqlAlchemyAccessChangeRecorder(session),
    )

    def authorization_transaction_factory() -> AccessControlTransaction:
        return SqlAlchemyAccessControlTransaction(async_session_factory(), close_on_exit=True)

    authorization = AuthorizationService(authorization_transaction_factory, scope_resolver)
    return AuthorizedAccessControlService(access, authorization)


def get_database_authorization_port(
    scope_resolver: Annotated[
        OrganizationScopeResolver,
        Depends(get_organization_scope_resolver),
    ],
) -> AuthorizationPort:
    """Composition dependency used to override core's fail-closed default."""

    def transaction_factory() -> AccessControlTransaction:
        return SqlAlchemyAccessControlTransaction(async_session_factory(), close_on_exit=True)

    return DatabaseAuthorizationAdapter(AuthorizationService(transaction_factory, scope_resolver))
