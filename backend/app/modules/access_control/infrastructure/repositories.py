"""Async SQLAlchemy adapters for access-control ports."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from types import TracebackType
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from app.core.errors import ConcurrencyConflictError
from app.modules.access_control.application.ports import (
    AccessControlTransaction,
    PermissionRepository,
    RoleAssignmentRepository,
    RoleRepository,
)
from app.modules.access_control.domain.entities import (
    AccessScope,
    Permission,
    PermissionGrant,
    Role,
    ScopeType,
    UserRoleAssignment,
)
from app.modules.access_control.infrastructure.models import (
    AccessScopeModel,
    AccessScopeUnitModel,
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    UserRoleAssignmentModel,
)
from app.modules.identity.infrastructure.models import UserAccountModel


def _permission_to_domain(model: PermissionModel) -> Permission:
    return Permission(
        id=model.id,
        code=model.code,
        name=model.name,
        description=model.description,
        active=model.active,
        system=model.system,
        revision=model.revision,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _scope_to_domain(model: AccessScopeModel) -> AccessScope:
    return AccessScope(
        id=model.id,
        scope_type=ScopeType(model.scope_type),
        organization_id=model.organization_id,
        unit_ids=frozenset(item.unit_id for item in model.units),
        created_at=model.created_at,
    )


def _assignment_to_domain(model: UserRoleAssignmentModel) -> UserRoleAssignment:
    return UserRoleAssignment(
        id=model.id,
        user_id=model.user_id,
        role_id=model.role_id,
        scope=_scope_to_domain(model.scope),
        effective_from=model.effective_from,
        effective_to=model.effective_to,
        created_by=model.created_by,
        created_at=model.created_at,
        revoked_at=model.revoked_at,
        revoked_by=model.revoked_by,
        revocation_reason=model.revocation_reason,
        revision=model.revision,
    )


class SqlAlchemyRoleRepository(RoleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _permission_codes(self, role_ids: Sequence[UUID]) -> dict[UUID, frozenset[str]]:
        if not role_ids:
            return {}
        rows = await self._session.execute(
            select(RolePermissionModel.role_id, PermissionModel.code)
            .join(PermissionModel, PermissionModel.id == RolePermissionModel.permission_id)
            .where(RolePermissionModel.role_id.in_(role_ids), PermissionModel.active.is_(True))
        )
        codes: defaultdict[UUID, set[str]] = defaultdict(set)
        for role_id, code in rows:
            codes[role_id].add(code)
        return {role_id: frozenset(values) for role_id, values in codes.items()}

    @staticmethod
    def _to_domain(model: RoleModel, permission_codes: frozenset[str]) -> Role:
        return Role(
            id=model.id,
            organization_id=model.organization_id,
            code=model.code,
            name=model.name,
            description=model.description,
            permission_codes=permission_codes,
            active=model.active,
            system=model.system,
            revision=model.revision,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list(self, *, organization_id: UUID | None = None) -> Sequence[Role]:
        statement = (
            select(RoleModel)
            .where(RoleModel.active.is_(True))
            .order_by(RoleModel.name, RoleModel.id)
        )
        if organization_id is not None:
            statement = statement.where(
                or_(
                    RoleModel.organization_id.is_(None),
                    RoleModel.organization_id == organization_id,
                )
            )
        models = tuple((await self._session.scalars(statement)).all())
        permission_codes = await self._permission_codes([model.id for model in models])
        return tuple(
            self._to_domain(model, permission_codes.get(model.id, frozenset())) for model in models
        )

    async def get(self, role_id: UUID) -> Role | None:
        model = await self._session.get(RoleModel, role_id)
        if model is None:
            return None
        permission_codes = await self._permission_codes([role_id])
        return self._to_domain(model, permission_codes.get(role_id, frozenset()))

    async def find_by_code(self, code: str, *, organization_id: UUID | None) -> Role | None:
        organization_predicate = (
            RoleModel.organization_id.is_(None)
            if organization_id is None
            else RoleModel.organization_id == organization_id
        )
        model = await self._session.scalar(
            select(RoleModel).where(RoleModel.code == code, organization_predicate)
        )
        if model is None:
            return None
        permission_codes = await self._permission_codes([model.id])
        return self._to_domain(model, permission_codes.get(model.id, frozenset()))

    async def add(self, role: Role) -> None:
        self._session.add(
            RoleModel(
                id=role.id,
                organization_id=role.organization_id,
                code=role.code,
                name=role.name,
                description=role.description,
                active=role.active,
                system=role.system,
                revision=role.revision,
                created_at=role.created_at,
                updated_at=role.updated_at,
            )
        )
        await self._session.flush()

    async def update(self, role: Role, *, expected_revision: int) -> bool:
        """Apply an edit, refusing to overwrite a concurrent one.

        Returns False when ``expected_revision`` no longer matches, so the caller can
        report the conflict rather than silently clobbering the other writer.
        """

        result = await self._session.execute(
            update(RoleModel)
            .where(RoleModel.id == role.id, RoleModel.revision == expected_revision)
            .values(
                name=role.name,
                description=role.description,
                active=role.active,
                revision=expected_revision + 1,
                updated_at=role.updated_at,
            )
        )
        await self._session.flush()
        return bool(result.rowcount)

    async def delete(self, role_id: UUID) -> None:
        await self._session.execute(
            delete(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
        )
        await self._session.execute(delete(RoleModel).where(RoleModel.id == role_id))
        await self._session.flush()

    async def assignment_count(self, role_id: UUID) -> int:
        """Assignments referencing this role, revoked ones included.

        A revoked assignment still names the role in its history, so deleting a role that
        has ever been assigned would strand that record.
        """

        total = await self._session.scalar(
            select(func.count())
            .select_from(UserRoleAssignmentModel)
            .where(UserRoleAssignmentModel.role_id == role_id)
        )
        return int(total or 0)

    async def replace_permissions(
        self,
        role_id: UUID,
        permission_ids: set[UUID],
        actor_id: UUID,
    ) -> None:
        await self._session.execute(
            delete(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
        )
        self._session.add_all(
            RolePermissionModel(
                role_id=role_id,
                permission_id=permission_id,
                granted_by=actor_id,
            )
            for permission_id in permission_ids
        )
        await self._session.flush()


class SqlAlchemyPermissionRepository(PermissionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, *, active_only: bool = True) -> Sequence[Permission]:
        statement = select(PermissionModel).order_by(PermissionModel.code)
        if active_only:
            statement = statement.where(PermissionModel.active.is_(True))
        return tuple(
            _permission_to_domain(model) for model in (await self._session.scalars(statement)).all()
        )

    async def get(self, permission_id: UUID) -> Permission | None:
        model = await self._session.get(PermissionModel, permission_id)
        return None if model is None else _permission_to_domain(model)

    async def find_by_codes(self, codes: set[str]) -> Sequence[Permission]:
        if not codes:
            return ()
        models = await self._session.scalars(
            select(PermissionModel).where(
                PermissionModel.code.in_(codes),
                PermissionModel.active.is_(True),
            )
        )
        return tuple(_permission_to_domain(model) for model in models.all())

    async def add(self, permission: Permission) -> None:
        self._session.add(
            PermissionModel(
                id=permission.id,
                code=permission.code,
                name=permission.name,
                description=permission.description,
                active=permission.active,
                system=permission.system,
                revision=permission.revision,
                created_at=permission.created_at,
                updated_at=permission.updated_at,
            )
        )
        await self._session.flush()

    async def update(self, permission: Permission, *, expected_revision: int) -> bool:
        """Apply an edit, refusing to overwrite a concurrent one.

        The code is deliberately not updatable: it is the identifier the source tree and
        stored workflow rules check against, so renaming it would break them silently.
        """

        result = await self._session.execute(
            update(PermissionModel)
            .where(
                PermissionModel.id == permission.id,
                PermissionModel.revision == expected_revision,
            )
            .values(
                name=permission.name,
                description=permission.description,
                active=permission.active,
                revision=expected_revision + 1,
                updated_at=permission.updated_at,
            )
        )
        await self._session.flush()
        return bool(result.rowcount)

    async def delete(self, permission_id: UUID) -> None:
        await self._session.execute(
            delete(RolePermissionModel).where(RolePermissionModel.permission_id == permission_id)
        )
        await self._session.execute(
            delete(PermissionModel).where(PermissionModel.id == permission_id)
        )
        await self._session.flush()

    async def granting_role_count(self, permission_id: UUID) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(RolePermissionModel)
            .where(RolePermissionModel.permission_id == permission_id)
        )
        return int(total or 0)

    async def synchronize_catalog(self, permissions: Sequence[Permission]) -> None:
        codes = {permission.code for permission in permissions}
        existing = {
            model.code: model
            for model in (
                await self._session.scalars(
                    select(PermissionModel).where(PermissionModel.code.in_(codes))
                )
            ).all()
        }
        for permission in permissions:
            model = existing.get(permission.code)
            if model is None:
                self._session.add(
                    PermissionModel(
                        id=permission.id,
                        code=permission.code,
                        name=permission.name,
                        description=permission.description,
                        active=True,
                        system=True,
                        created_at=permission.created_at,
                    )
                )
            else:
                model.name = permission.name
                model.description = permission.description
                model.active = True
                # A code that appears in the catalogue is checked by the source tree,
                # even if it was created through the administration API first.
                model.system = True
        await self._session.flush()


class SqlAlchemyRoleAssignmentRepository(RoleAssignmentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _with_scope() -> LoaderOption:
        return selectinload(UserRoleAssignmentModel.scope).selectinload(AccessScopeModel.units)

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        effective_at: datetime | None = None,
    ) -> Sequence[UserRoleAssignment]:
        statement = (
            select(UserRoleAssignmentModel)
            .where(UserRoleAssignmentModel.user_id == user_id)
            .options(self._with_scope())
            .order_by(UserRoleAssignmentModel.effective_from.desc())
        )
        if effective_at is not None:
            statement = statement.where(
                UserRoleAssignmentModel.revoked_at.is_(None),
                UserRoleAssignmentModel.effective_from <= effective_at,
                or_(
                    UserRoleAssignmentModel.effective_to.is_(None),
                    UserRoleAssignmentModel.effective_to > effective_at,
                ),
            )
        models = (await self._session.scalars(statement)).all()
        return tuple(_assignment_to_domain(model) for model in models)

    async def get(self, assignment_id: UUID) -> UserRoleAssignment | None:
        model = await self._session.scalar(
            select(UserRoleAssignmentModel)
            .where(UserRoleAssignmentModel.id == assignment_id)
            .options(self._with_scope())
        )
        return _assignment_to_domain(model) if model is not None else None

    async def add(self, assignment: UserRoleAssignment) -> None:
        scope_model = AccessScopeModel(
            id=assignment.scope.id,
            scope_type=assignment.scope.scope_type.value,
            organization_id=assignment.scope.organization_id,
            created_at=assignment.scope.created_at,
            units=[
                AccessScopeUnitModel(scope_id=assignment.scope.id, unit_id=unit_id)
                for unit_id in sorted(assignment.scope.unit_ids, key=str)
            ],
        )
        self._session.add(scope_model)
        self._session.add(
            UserRoleAssignmentModel(
                id=assignment.id,
                user_id=assignment.user_id,
                role_id=assignment.role_id,
                scope_id=assignment.scope.id,
                effective_from=assignment.effective_from,
                effective_to=assignment.effective_to,
                created_by=assignment.created_by,
                created_at=assignment.created_at,
                revoked_at=assignment.revoked_at,
                revoked_by=assignment.revoked_by,
                revocation_reason=assignment.revocation_reason,
                revision=assignment.revision,
            )
        )
        await self._session.flush()

    async def update(self, assignment: UserRoleAssignment, *, expected_revision: int) -> bool:
        result = await self._session.execute(
            update(UserRoleAssignmentModel)
            .where(
                UserRoleAssignmentModel.id == assignment.id,
                UserRoleAssignmentModel.revision == expected_revision,
            )
            .values(
                effective_to=assignment.effective_to,
                revoked_at=assignment.revoked_at,
                revoked_by=assignment.revoked_by,
                revocation_reason=assignment.revocation_reason,
                revision=assignment.revision,
            )
        )
        await self._session.flush()
        rowcount = getattr(result, "rowcount", None)
        if not isinstance(rowcount, int):
            raise RuntimeError("Database driver did not report the updated row count")
        return rowcount == 1

    async def active_grants(
        self,
        user_id: UUID,
        permission_code: str,
        *,
        effective_at: datetime,
    ) -> Sequence[PermissionGrant]:
        statement = (
            select(UserRoleAssignmentModel)
            .join(UserAccountModel, UserAccountModel.id == UserRoleAssignmentModel.user_id)
            .join(RoleModel, RoleModel.id == UserRoleAssignmentModel.role_id)
            .join(RolePermissionModel, RolePermissionModel.role_id == RoleModel.id)
            .join(PermissionModel, PermissionModel.id == RolePermissionModel.permission_id)
            .where(
                UserRoleAssignmentModel.user_id == user_id,
                UserAccountModel.active.is_(True),
                UserAccountModel.status == "active",
                UserRoleAssignmentModel.revoked_at.is_(None),
                UserRoleAssignmentModel.effective_from <= effective_at,
                or_(
                    UserRoleAssignmentModel.effective_to.is_(None),
                    UserRoleAssignmentModel.effective_to > effective_at,
                ),
                RoleModel.active.is_(True),
                PermissionModel.active.is_(True),
                PermissionModel.code == permission_code,
            )
            .options(self._with_scope())
        )
        models = (await self._session.scalars(statement)).unique().all()
        return tuple(
            PermissionGrant(
                permission_code=permission_code,
                assignment_id=model.id,
                scope=_scope_to_domain(model.scope),
            )
            for model in models
        )

    async def has_overlapping_assignment(self, assignment: UserRoleAssignment) -> bool:
        statement = (
            select(UserRoleAssignmentModel)
            .join(AccessScopeModel, AccessScopeModel.id == UserRoleAssignmentModel.scope_id)
            .where(
                UserRoleAssignmentModel.user_id == assignment.user_id,
                UserRoleAssignmentModel.role_id == assignment.role_id,
                UserRoleAssignmentModel.revoked_at.is_(None),
                AccessScopeModel.scope_type == assignment.scope.scope_type.value,
                (
                    AccessScopeModel.organization_id.is_(None)
                    if assignment.scope.organization_id is None
                    else AccessScopeModel.organization_id == assignment.scope.organization_id
                ),
                or_(
                    UserRoleAssignmentModel.effective_to.is_(None),
                    UserRoleAssignmentModel.effective_to > assignment.effective_from,
                ),
            )
            .options(self._with_scope())
        )
        if assignment.effective_to is not None:
            statement = statement.where(
                UserRoleAssignmentModel.effective_from < assignment.effective_to
            )
        candidates = (await self._session.scalars(statement)).all()
        return any(
            _scope_to_domain(candidate.scope).unit_ids == assignment.scope.unit_ids
            for candidate in candidates
        )


class SqlAlchemyAccessControlTransaction(AccessControlTransaction):
    """Request-scoped unit of work; writes commit or roll back as a unit."""

    def __init__(self, session: AsyncSession, *, close_on_exit: bool = False) -> None:
        self._session = session
        self._roles = SqlAlchemyRoleRepository(session)
        self._permissions = SqlAlchemyPermissionRepository(session)
        self._assignments = SqlAlchemyRoleAssignmentRepository(session)
        self._context: AsyncSessionTransaction | None = None
        self._owns_transaction = False
        self._close_on_exit = close_on_exit

    @property
    def roles(self) -> RoleRepository:
        return self._roles

    @property
    def permissions(self) -> PermissionRepository:
        return self._permissions

    @property
    def assignments(self) -> RoleAssignmentRepository:
        return self._assignments

    async def __aenter__(self) -> SqlAlchemyAccessControlTransaction:
        if self._session.in_transaction():
            self._owns_transaction = False
            return self
        self._context = self._session.begin()
        await self._context.__aenter__()
        self._owns_transaction = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if self._owns_transaction:
                if self._context is None:
                    raise RuntimeError("Access-control transaction was not entered")
                try:
                    await self._context.__aexit__(exc_type, exc, traceback)
                except IntegrityError as error:
                    await self._session.rollback()
                    raise ConcurrencyConflictError(
                        "The access-control change conflicts with persisted data."
                    ) from error
                if isinstance(exc, IntegrityError):
                    raise ConcurrencyConflictError(
                        "The access-control change conflicts with persisted data."
                    ) from exc
        finally:
            if self._close_on_exit:
                await self._session.close()
