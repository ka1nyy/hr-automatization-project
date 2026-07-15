"""SQLAlchemy transaction composition for organization use cases."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organization.domain.errors import VersionConflictError
from app.modules.organization.domain.ports import (
    AuditRepository,
    OrganizationRepository,
    OrganizationUnitOfWork,
    OutboxRepository,
    PolicyRepository,
    PositionRepository,
    RelationshipRepository,
    RelationshipTypeRepository,
    ReviewRequestRepository,
    StaffingRepository,
    StructureVersionRepository,
    UnitRepository,
    UnitTypeRepository,
)
from app.modules.organization.infrastructure.repositories import (
    SqlAlchemyAuditRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyOutboxRepository,
    SqlAlchemyPolicyRepository,
    SqlAlchemyPositionRepository,
    SqlAlchemyRelationshipRepository,
    SqlAlchemyRelationshipTypeRepository,
    SqlAlchemyReviewRequestRepository,
    SqlAlchemyStaffingRepository,
    SqlAlchemyStructureVersionRepository,
    SqlAlchemyUnitRepository,
    SqlAlchemyUnitTypeRepository,
)


class SqlAlchemyOrganizationUnitOfWork:
    """One session-backed atomic boundary; it never creates tables at runtime."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._committed = False
        self.organizations: OrganizationRepository = SqlAlchemyOrganizationRepository(session)
        self.versions: StructureVersionRepository = SqlAlchemyStructureVersionRepository(session)
        self.unit_types: UnitTypeRepository = SqlAlchemyUnitTypeRepository(session)
        self.relationship_types: RelationshipTypeRepository = SqlAlchemyRelationshipTypeRepository(
            session
        )
        self.policies: PolicyRepository = SqlAlchemyPolicyRepository(session)
        self.review_requests: ReviewRequestRepository = SqlAlchemyReviewRequestRepository(session)
        self.units: UnitRepository = SqlAlchemyUnitRepository(session)
        self.relationships: RelationshipRepository = SqlAlchemyRelationshipRepository(session)
        self.positions: PositionRepository = SqlAlchemyPositionRepository(session)
        self.staffing: StaffingRepository = SqlAlchemyStaffingRepository(session)
        self.audit: AuditRepository = SqlAlchemyAuditRepository(session)
        self.outbox: OutboxRepository = SqlAlchemyOutboxRepository(session)

    async def __aenter__(self) -> Self:
        self._committed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc is not None or not self._committed:
            await self._session.rollback()
        if isinstance(exc, IntegrityError):
            raise self._integrity_error(exc) from exc

    async def flush(self) -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise self._integrity_error(exc) from exc

    async def commit(self) -> None:
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise self._integrity_error(exc) from exc
        self._committed = True

    async def rollback(self) -> None:
        await self._session.rollback()

    @staticmethod
    def _integrity_error(exc: IntegrityError) -> VersionConflictError:
        diagnostic = getattr(exc.orig, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        return VersionConflictError(
            "The requested organization change conflicts with persisted data.",
            details={"constraint": constraint_name} if constraint_name else {},
        )


class SqlAlchemyOrganizationUnitOfWorkFactory:
    """Callable factory suitable for OrganizationService construction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> OrganizationUnitOfWork:
        return SqlAlchemyOrganizationUnitOfWork(self._session)
