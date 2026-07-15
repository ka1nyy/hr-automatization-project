"""Temporary-delegation augmentation for the core authorization contract."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ForbiddenError, ScopeViolationError
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.modules.identity.infrastructure.models import UserAccountModel
from app.modules.organization.infrastructure.models import OrganizationUnitModel

from ..domain.enums import DelegationScopeType
from .models import DelegationModel, EmployeeModel


class DelegationAwareAuthorizationAdapter(AuthorizationPort):
    """Accept a valid role grant or a valid, bounded delegation from an authorized user."""

    def __init__(
        self,
        base: AuthorizationPort,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._base = base
        self._session_factory = session_factory

    async def require(
        self,
        *,
        principal: Principal,
        permission_code: str,
        organization_id: UUID | None = None,
        unit_id: UUID | None = None,
        subject_user_id: UUID | None = None,
    ) -> None:
        try:
            await self._base.require(
                principal=principal,
                permission_code=permission_code,
                organization_id=organization_id,
                unit_id=unit_id,
                subject_user_id=subject_user_id,
            )
            return
        except (ForbiddenError, ScopeViolationError) as error:
            denial = error
            if principal.employee_id is None or organization_id is None:
                raise

        now = datetime.now(UTC)
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(DelegationModel, UserAccountModel)
                    .join(
                        UserAccountModel,
                        UserAccountModel.employee_id == DelegationModel.delegator_employee_id,
                    )
                    .join(
                        EmployeeModel,
                        EmployeeModel.id == DelegationModel.delegator_employee_id,
                    )
                    .where(
                        DelegationModel.delegate_employee_id == principal.employee_id,
                        DelegationModel.status != "revoked",
                        DelegationModel.revoked_at.is_(None),
                        DelegationModel.effective_from <= now,
                        DelegationModel.effective_to > now,
                        DelegationModel.delegated_permissions.contains([permission_code]),
                        EmployeeModel.organization_id == organization_id,
                        UserAccountModel.active.is_(True),
                        UserAccountModel.status == "active",
                    )
                )
            ).all()

        for delegation, delegator_account in rows:
            if not await self._scope_matches(
                delegation.scope_type,
                delegation.scope_reference,
                organization_id,
                unit_id,
            ):
                continue
            delegator = Principal(
                user_id=delegator_account.id,
                subject=delegator_account.external_subject,
                organization_id=organization_id,
                employee_id=delegator_account.employee_id,
            )
            try:
                await self._base.require(
                    principal=delegator,
                    permission_code=permission_code,
                    organization_id=organization_id,
                    unit_id=unit_id,
                    subject_user_id=subject_user_id,
                )
                return
            except (ForbiddenError, ScopeViolationError):
                continue
        raise denial

    async def _scope_matches(
        self,
        scope_type: str,
        scope_reference: str | None,
        organization_id: UUID | None,
        unit_id: UUID | None,
    ) -> bool:
        parsed_type = DelegationScopeType(scope_type)
        if parsed_type is DelegationScopeType.PERMISSIONS:
            return True
        if parsed_type is DelegationScopeType.ORGANIZATION:
            return organization_id is not None and scope_reference == str(organization_id)
        if parsed_type is DelegationScopeType.UNIT:
            if unit_id is None or scope_reference is None:
                return False
            if scope_reference == str(unit_id):
                return True
            try:
                reference_id = UUID(scope_reference)
            except ValueError:
                return False
            async with self._session_factory() as session:
                target_stable_key = await session.scalar(
                    select(OrganizationUnitModel.stable_key).where(
                        OrganizationUnitModel.id == unit_id
                    )
                )
                if target_stable_key is None:
                    return False
                if reference_id == target_stable_key:
                    return True
                reference_stable_key = await session.scalar(
                    select(OrganizationUnitModel.stable_key).where(
                        OrganizationUnitModel.id == reference_id
                    )
                )
            return reference_stable_key == target_stable_key
        # Process/request scopes need a future workflow resource context and therefore fail closed.
        return False
