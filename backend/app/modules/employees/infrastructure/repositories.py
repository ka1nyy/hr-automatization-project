"""SQLAlchemy implementations of the employee application ports."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from datetime import date, datetime
from types import TracebackType
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from ..application.ports import (
    AbsenceRepository,
    AssignmentRepository,
    AssignmentReviewRepository,
    AuditSink,
    DelegationRepository,
    EmployeePolicyReader,
    EmployeeRepository,
    EmployeeUnitOfWork,
    EmployeeUnitOfWorkFactory,
    OutboxSink,
    PersonRepository,
    StaffingSlotReader,
)
from ..domain.entities import (
    AssignmentReviewRequest,
    Delegation,
    Employee,
    EmployeeAbsence,
    EmployeeAssignment,
    Person,
)
from ..domain.enums import (
    AbsenceStatus,
    AbsenceType,
    AssignmentReviewStatus,
    AssignmentStatus,
    AssignmentType,
    DelegationScopeType,
    DelegationStatus,
    EmploymentStatus,
    PersonStatus,
)
from ..domain.errors import EmployeeDomainError
from .models import (
    AssignmentReviewRequestModel,
    DelegationModel,
    EmployeeAbsenceModel,
    EmployeeAssignmentModel,
    EmployeeModel,
    PersonModel,
)


def _absence(model: EmployeeAbsenceModel) -> EmployeeAbsence:
    return EmployeeAbsence(
        id=model.id,
        employee_id=model.employee_id,
        absence_type=AbsenceType(model.absence_type),
        date_from=model.date_from,
        date_to=model.date_to,
        reason=model.reason,
        details=model.details,
        status=AbsenceStatus(model.status),
        created_by=model.created_by,
        source_document_id=model.source_document_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        revision=model.revision,
    )


def _person(model: PersonModel) -> Person:
    return Person(
        id=model.id,
        first_name=model.first_name,
        last_name=model.last_name,
        middle_name=model.middle_name,
        display_name=model.display_name,
        protected_iin=model.protected_iin,
        birth_date=model.birth_date,
        personal_email=model.personal_email,
        phone=model.phone,
        status=PersonStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
        revision=model.revision,
    )


def _employee(model: EmployeeModel) -> Employee:
    return Employee(
        id=model.id,
        organization_id=model.organization_id,
        created_by=model.created_by,
        person_id=model.person_id,
        employee_number=model.employee_number,
        employment_status=EmploymentStatus(model.employment_status),
        hire_date=model.hire_date,
        probation_end=model.probation_end,
        termination_date=model.termination_date,
        corporate_email=model.corporate_email,
        active=model.active,
        created_at=model.created_at,
        updated_at=model.updated_at,
        revision=model.revision,
    )


def _assignment(model: EmployeeAssignmentModel) -> EmployeeAssignment:
    return EmployeeAssignment(
        id=model.id,
        employee_id=model.employee_id,
        staffing_slot_id=model.staffing_slot_id,
        assignment_type=AssignmentType(model.assignment_type),
        full_time_equivalent=model.full_time_equivalent,
        effective_from=model.effective_from,
        effective_to=model.effective_to,
        primary=model.primary,
        acting=model.acting,
        status=AssignmentStatus(model.status),
        source_document_id=model.source_document_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        revision=model.revision,
    )


def _assignment_review(model: AssignmentReviewRequestModel) -> AssignmentReviewRequest:
    return AssignmentReviewRequest(
        id=model.id,
        organization_id=model.organization_id,
        assignment_id=model.assignment_id,
        status=AssignmentReviewStatus(model.status),
        submitted_by=model.submitted_by,
        submitted_at=model.submitted_at,
        resolved_by=model.resolved_by,
        resolved_at=model.resolved_at,
        submission_reason=model.submission_reason,
        resolution_reason=model.resolution_reason,
        revision=model.revision,
    )


def _delegation(model: DelegationModel) -> Delegation:
    return Delegation(
        id=model.id,
        delegator_employee_id=model.delegator_employee_id,
        delegate_employee_id=model.delegate_employee_id,
        scope_type=DelegationScopeType(model.scope_type),
        scope_reference=model.scope_reference,
        delegated_permissions=tuple(model.delegated_permissions),
        effective_from=model.effective_from,
        effective_to=model.effective_to,
        reason=model.reason,
        source_document_id=model.source_document_id,
        status=DelegationStatus(model.status),
        created_by=model.created_by,
        created_at=model.created_at,
        revoked_at=model.revoked_at,
        revision=model.revision,
        metadata=dict(model.extra_metadata),
    )


def _ensure_updated(result: Any) -> None:
    cursor = cast(CursorResult[Any], result)
    if cursor.rowcount != 1:
        raise EmployeeDomainError(
            "CONCURRENCY_CONFLICT", "The record was changed by another user.", {}
        )


class SqlAlchemyPersonRepository(PersonRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, person_id: UUID) -> Person | None:
        model = await self._session.get(PersonModel, person_id)
        return _person(model) if model is not None else None

    async def add(self, person: Person) -> None:
        self._session.add(
            PersonModel(
                id=person.id,
                first_name=person.first_name,
                last_name=person.last_name,
                middle_name=person.middle_name,
                display_name=person.display_name,
                protected_iin=person.protected_iin,
                birth_date=person.birth_date,
                personal_email=person.personal_email,
                phone=person.phone,
                status=person.status.value,
                created_at=person.created_at,
                updated_at=person.updated_at,
                revision=person.revision,
            )
        )
        # EmployeeModel references this person, but the models intentionally do not
        # declare ORM relationships. Flush the principal row so SQLAlchemy cannot
        # emit the dependent employee INSERT before its foreign key target.
        await self._session.flush()

    async def update(self, person: Person, expected_revision: int) -> None:
        result = await self._session.execute(
            update(PersonModel)
            .where(PersonModel.id == person.id, PersonModel.revision == expected_revision)
            .values(
                first_name=person.first_name,
                last_name=person.last_name,
                middle_name=person.middle_name,
                display_name=person.display_name,
                protected_iin=person.protected_iin,
                birth_date=person.birth_date,
                personal_email=person.personal_email,
                phone=person.phone,
                status=person.status.value,
                updated_at=person.updated_at,
                revision=person.revision,
            )
        )
        _ensure_updated(result)


class SqlAlchemyEmployeeRepository(EmployeeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, employee_id: UUID) -> Employee | None:
        model = await self._session.get(EmployeeModel, employee_id)
        return _employee(model) if model is not None else None

    async def get_by_number(self, organization_id: UUID, employee_number: str) -> Employee | None:
        model = await self._session.scalar(
            select(EmployeeModel).where(
                EmployeeModel.organization_id == organization_id,
                EmployeeModel.employee_number == employee_number,
            )
        )
        return _employee(model) if model is not None else None

    @staticmethod
    def _visible_query(
        *,
        organization_id: UUID,
        organization_wide: bool,
        unit_ids: frozenset[UUID],
        self_employee_id: UUID | None,
        creator_user_id: UUID,
        active: bool | None,
    ) -> Select[tuple[EmployeeModel]]:
        statement = select(EmployeeModel).where(EmployeeModel.organization_id == organization_id)
        if active is not None:
            statement = statement.where(EmployeeModel.active == active)
        if organization_wide:
            return statement

        from app.modules.organization.infrastructure.models import (
            OrganizationStructureVersionModel,
            OrganizationUnitModel,
            StaffingSlotModel,
        )

        assigned_unit = aliased(OrganizationUnitModel)
        permitted_stable_keys = select(OrganizationUnitModel.stable_key).where(
            OrganizationUnitModel.id.in_(unit_ids),
            OrganizationUnitModel.active.is_(True),
        )
        assignment_visible = (
            select(EmployeeAssignmentModel.id)
            .join(
                StaffingSlotModel,
                StaffingSlotModel.id == EmployeeAssignmentModel.staffing_slot_id,
            )
            .join(
                OrganizationStructureVersionModel,
                OrganizationStructureVersionModel.id == StaffingSlotModel.structure_version_id,
            )
            .join(
                assigned_unit,
                assigned_unit.id == StaffingSlotModel.organization_unit_id,
            )
            .where(
                EmployeeAssignmentModel.employee_id == EmployeeModel.id,
                OrganizationStructureVersionModel.organization_id == organization_id,
                assigned_unit.stable_key.in_(permitted_stable_keys),
                EmployeeAssignmentModel.status.in_(
                    (
                        AssignmentStatus.PLANNED.value,
                        AssignmentStatus.ACTIVE.value,
                        AssignmentStatus.SCHEDULED_END.value,
                        AssignmentStatus.ENDED.value,
                    )
                ),
                EmployeeAssignmentModel.effective_from <= date.today(),
                or_(
                    EmployeeAssignmentModel.effective_to.is_(None),
                    EmployeeAssignmentModel.effective_to >= date.today(),
                ),
            )
            .exists()
        )
        creator_visible = (EmployeeModel.created_by == creator_user_id) & (
            EmployeeModel.employment_status == EmploymentStatus.DRAFT.value
        )
        if unit_ids and self_employee_id is not None:
            return statement.where(
                or_(
                    EmployeeModel.id == self_employee_id,
                    creator_visible,
                    assignment_visible,
                )
            )
        if unit_ids:
            return statement.where(or_(creator_visible, assignment_visible))
        if self_employee_id is not None:
            return statement.where(or_(EmployeeModel.id == self_employee_id, creator_visible))
        return statement.where(creator_visible)

    async def list_visible(
        self,
        *,
        organization_id: UUID,
        organization_wide: bool,
        unit_ids: frozenset[UUID],
        self_employee_id: UUID | None,
        creator_user_id: UUID,
        offset: int,
        limit: int,
        active: bool | None,
        sort: str,
    ) -> list[Employee]:
        sort_column: Any = {
            "employeeNumber": EmployeeModel.employee_number.asc(),
            "-employeeNumber": EmployeeModel.employee_number.desc(),
            "hireDate": EmployeeModel.hire_date.asc(),
            "-hireDate": EmployeeModel.hire_date.desc(),
            "createdAt": EmployeeModel.created_at.asc(),
            "-createdAt": EmployeeModel.created_at.desc(),
        }[sort]
        statement = self._visible_query(
            organization_id=organization_id,
            organization_wide=organization_wide,
            unit_ids=unit_ids,
            self_employee_id=self_employee_id,
            creator_user_id=creator_user_id,
            active=active,
        ).order_by(sort_column, EmployeeModel.id.asc())
        models = (await self._session.scalars(statement.offset(offset).limit(limit))).all()
        return [_employee(model) for model in models]

    async def count_visible(
        self,
        *,
        organization_id: UUID,
        organization_wide: bool,
        unit_ids: frozenset[UUID],
        self_employee_id: UUID | None,
        creator_user_id: UUID,
        active: bool | None,
    ) -> int:
        query = self._visible_query(
            organization_id=organization_id,
            organization_wide=organization_wide,
            unit_ids=unit_ids,
            self_employee_id=self_employee_id,
            creator_user_id=creator_user_id,
            active=active,
        ).subquery()
        return int(await self._session.scalar(select(func.count()).select_from(query)) or 0)

    async def add(self, employee: Employee) -> None:
        self._session.add(
            EmployeeModel(
                id=employee.id,
                organization_id=employee.organization_id,
                created_by=employee.created_by,
                person_id=employee.person_id,
                employee_number=employee.employee_number,
                employment_status=employee.employment_status.value,
                hire_date=employee.hire_date,
                probation_end=employee.probation_end,
                termination_date=employee.termination_date,
                corporate_email=employee.corporate_email,
                active=employee.active,
                created_at=employee.created_at,
                updated_at=employee.updated_at,
                revision=employee.revision,
            )
        )
        # EmployeeAssignmentModel references this employee without an ORM
        # relationship. Flush the principal row so a same-transaction assignment
        # INSERT cannot precede its foreign key target.
        await self._session.flush()

    async def update(self, employee: Employee, expected_revision: int) -> None:
        result = await self._session.execute(
            update(EmployeeModel)
            .where(EmployeeModel.id == employee.id, EmployeeModel.revision == expected_revision)
            .values(
                employment_status=employee.employment_status.value,
                probation_end=employee.probation_end,
                termination_date=employee.termination_date,
                corporate_email=employee.corporate_email,
                active=employee.active,
                updated_at=employee.updated_at,
                revision=employee.revision,
            )
        )
        _ensure_updated(result)


class SqlAlchemyAbsenceRepository(AbsenceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, absence_id: UUID) -> EmployeeAbsence | None:
        model = await self._session.get(EmployeeAbsenceModel, absence_id)
        return _absence(model) if model is not None else None

    async def list_for_employee(self, employee_id: UUID) -> list[EmployeeAbsence]:
        models = (
            await self._session.scalars(
                select(EmployeeAbsenceModel)
                .where(EmployeeAbsenceModel.employee_id == employee_id)
                .order_by(EmployeeAbsenceModel.date_from.desc())
            )
        ).all()
        return [_absence(model) for model in models]

    async def list_covering(self, organization_id: UUID, on_date: date) -> list[EmployeeAbsence]:
        models = (
            await self._session.scalars(
                select(EmployeeAbsenceModel)
                .join(EmployeeModel, EmployeeModel.id == EmployeeAbsenceModel.employee_id)
                .where(
                    EmployeeModel.organization_id == organization_id,
                    EmployeeAbsenceModel.status != AbsenceStatus.CANCELLED.value,
                    EmployeeAbsenceModel.date_from <= on_date,
                    EmployeeAbsenceModel.date_to >= on_date,
                )
                .order_by(EmployeeAbsenceModel.date_from)
            )
        ).all()
        return [_absence(model) for model in models]

    async def add(self, absence: EmployeeAbsence) -> None:
        self._session.add(
            EmployeeAbsenceModel(
                id=absence.id,
                employee_id=absence.employee_id,
                absence_type=absence.absence_type.value,
                date_from=absence.date_from,
                date_to=absence.date_to,
                reason=absence.reason,
                details=absence.details,
                status=absence.status.value,
                created_by=absence.created_by,
                source_document_id=absence.source_document_id,
                created_at=absence.created_at,
                updated_at=absence.updated_at,
                revision=absence.revision,
            )
        )

    async def update(self, absence: EmployeeAbsence, expected_revision: int) -> None:
        result = await self._session.execute(
            update(EmployeeAbsenceModel)
            .where(
                EmployeeAbsenceModel.id == absence.id,
                EmployeeAbsenceModel.revision == expected_revision,
            )
            .values(
                status=absence.status.value,
                updated_at=absence.updated_at,
                revision=absence.revision,
            )
        )
        _ensure_updated(result)


class SqlAlchemyAssignmentRepository(AssignmentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, assignment_id: UUID) -> EmployeeAssignment | None:
        model = await self._session.get(EmployeeAssignmentModel, assignment_id)
        return _assignment(model) if model is not None else None

    async def list_for_employee(self, employee_id: UUID) -> list[EmployeeAssignment]:
        models = (
            await self._session.scalars(
                select(EmployeeAssignmentModel)
                .where(EmployeeAssignmentModel.employee_id == employee_id)
                .order_by(EmployeeAssignmentModel.effective_from.desc())
            )
        ).all()
        return [_assignment(model) for model in models]

    async def list_for_slot(self, staffing_slot_id: UUID) -> list[EmployeeAssignment]:
        models = (
            await self._session.scalars(
                select(EmployeeAssignmentModel)
                .where(EmployeeAssignmentModel.staffing_slot_id == staffing_slot_id)
                .order_by(EmployeeAssignmentModel.effective_from.desc())
            )
        ).all()
        return [_assignment(model) for model in models]

    async def add(self, assignment: EmployeeAssignment) -> None:
        self._session.add(
            EmployeeAssignmentModel(
                id=assignment.id,
                employee_id=assignment.employee_id,
                staffing_slot_id=assignment.staffing_slot_id,
                assignment_type=assignment.assignment_type.value,
                full_time_equivalent=assignment.full_time_equivalent,
                effective_from=assignment.effective_from,
                effective_to=assignment.effective_to,
                primary=assignment.primary,
                acting=assignment.acting,
                status=assignment.status.value,
                source_document_id=assignment.source_document_id,
                created_at=assignment.created_at,
                updated_at=assignment.updated_at,
                revision=assignment.revision,
            )
        )

    async def update(self, assignment: EmployeeAssignment, expected_revision: int) -> None:
        result = await self._session.execute(
            update(EmployeeAssignmentModel)
            .where(
                EmployeeAssignmentModel.id == assignment.id,
                EmployeeAssignmentModel.revision == expected_revision,
            )
            .values(
                effective_to=assignment.effective_to,
                status=assignment.status.value,
                updated_at=assignment.updated_at,
                revision=assignment.revision,
            )
        )
        _ensure_updated(result)


class SqlAlchemyAssignmentReviewRepository(AssignmentReviewRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pending_for_assignment(
        self, assignment_id: UUID
    ) -> AssignmentReviewRequest | None:
        model = await self._session.scalar(
            select(AssignmentReviewRequestModel).where(
                AssignmentReviewRequestModel.assignment_id == assignment_id,
                AssignmentReviewRequestModel.status == AssignmentReviewStatus.PENDING.value,
            )
        )
        return _assignment_review(model) if model is not None else None

    async def add(self, review: AssignmentReviewRequest) -> None:
        self._session.add(
            AssignmentReviewRequestModel(
                id=review.id,
                organization_id=review.organization_id,
                assignment_id=review.assignment_id,
                status=review.status.value,
                submitted_by=review.submitted_by,
                submitted_at=review.submitted_at,
                resolved_by=review.resolved_by,
                resolved_at=review.resolved_at,
                submission_reason=review.submission_reason,
                resolution_reason=review.resolution_reason,
                revision=review.revision,
            )
        )

    async def update(self, review: AssignmentReviewRequest, expected_revision: int) -> None:
        result = await self._session.execute(
            update(AssignmentReviewRequestModel)
            .where(
                AssignmentReviewRequestModel.id == review.id,
                AssignmentReviewRequestModel.revision == expected_revision,
            )
            .values(
                status=review.status.value,
                resolved_by=review.resolved_by,
                resolved_at=review.resolved_at,
                resolution_reason=review.resolution_reason,
                revision=review.revision,
            )
        )
        _ensure_updated(result)


class SqlAlchemyDelegationRepository(DelegationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, delegation_id: UUID) -> Delegation | None:
        model = await self._session.get(DelegationModel, delegation_id)
        return _delegation(model) if model is not None else None

    def _list_query(
        self, organization_id: UUID, employee_id: UUID | None, at: datetime | None
    ) -> Select[tuple[DelegationModel]]:
        delegator = aliased(EmployeeModel)
        statement = (
            select(DelegationModel)
            .join(
                delegator,
                delegator.id == DelegationModel.delegator_employee_id,
            )
            .where(delegator.organization_id == organization_id)
        )
        if employee_id is not None:
            statement = statement.where(
                or_(
                    DelegationModel.delegator_employee_id == employee_id,
                    DelegationModel.delegate_employee_id == employee_id,
                )
            )
        if at is not None:
            statement = statement.where(
                DelegationModel.effective_from <= at,
                DelegationModel.effective_to > at,
                DelegationModel.status != DelegationStatus.REVOKED.value,
            )
        return statement

    async def list(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID | None,
        at: datetime | None,
        offset: int,
        limit: int,
        sort: str,
    ) -> builtins.list[Delegation]:
        sort_column: Any = {
            "effectiveFrom": DelegationModel.effective_from.asc(),
            "-effectiveFrom": DelegationModel.effective_from.desc(),
            "createdAt": DelegationModel.created_at.asc(),
            "-createdAt": DelegationModel.created_at.desc(),
            "status": DelegationModel.status.asc(),
            "-status": DelegationModel.status.desc(),
        }[sort]
        models = (
            await self._session.scalars(
                self._list_query(organization_id, employee_id, at)
                .order_by(sort_column, DelegationModel.id.asc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [_delegation(model) for model in models]

    async def count(
        self, *, organization_id: UUID, employee_id: UUID | None, at: datetime | None
    ) -> int:
        query = self._list_query(organization_id, employee_id, at).subquery()
        return int(await self._session.scalar(select(func.count()).select_from(query)) or 0)

    async def list_for_pair(
        self, delegator_id: UUID, delegate_id: UUID
    ) -> builtins.list[Delegation]:
        models = (
            await self._session.scalars(
                select(DelegationModel).where(
                    DelegationModel.delegator_employee_id == delegator_id,
                    DelegationModel.delegate_employee_id == delegate_id,
                )
            )
        ).all()
        return [_delegation(model) for model in models]

    async def add(self, delegation: Delegation) -> None:
        self._session.add(
            DelegationModel(
                id=delegation.id,
                delegator_employee_id=delegation.delegator_employee_id,
                delegate_employee_id=delegation.delegate_employee_id,
                scope_type=delegation.scope_type.value,
                scope_reference=delegation.scope_reference,
                delegated_permissions=list(delegation.delegated_permissions),
                effective_from=delegation.effective_from,
                effective_to=delegation.effective_to,
                reason=delegation.reason,
                source_document_id=delegation.source_document_id,
                status=delegation.status.value,
                created_by=delegation.created_by,
                created_at=delegation.created_at,
                revoked_at=delegation.revoked_at,
                revision=delegation.revision,
                extra_metadata=delegation.metadata,
            )
        )

    async def update(self, delegation: Delegation, expected_revision: int) -> None:
        result = await self._session.execute(
            update(DelegationModel)
            .where(
                DelegationModel.id == delegation.id,
                DelegationModel.revision == expected_revision,
            )
            .values(
                status=delegation.status.value,
                revoked_at=delegation.revoked_at,
                revision=delegation.revision,
            )
        )
        _ensure_updated(result)


class SqlAlchemyEmployeeUnitOfWork(EmployeeUnitOfWork):
    def __init__(
        self,
        session: AsyncSession,
        staffing_slots: StaffingSlotReader,
        policies: EmployeePolicyReader,
        audit: AuditSink,
        outbox: OutboxSink,
    ) -> None:
        self._session = session
        self.people = SqlAlchemyPersonRepository(session)
        self.employees = SqlAlchemyEmployeeRepository(session)
        self.assignments = SqlAlchemyAssignmentRepository(session)
        self.assignment_reviews = SqlAlchemyAssignmentReviewRepository(session)
        self.absences = SqlAlchemyAbsenceRepository(session)
        self.delegations = SqlAlchemyDelegationRepository(session)
        self.staffing_slots = staffing_slots
        self.policies = policies
        self.audit = audit
        self.outbox = outbox

    async def __aenter__(self) -> SqlAlchemyEmployeeUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exc is not None:
                await self.rollback()
        finally:
            await self._session.close()
        if isinstance(exc, IntegrityError):
            raise self._integrity_error(exc) from exc

    async def commit(self) -> None:
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise self._integrity_error(exc) from exc

    async def rollback(self) -> None:
        await self._session.rollback()

    @staticmethod
    def _integrity_error(exc: IntegrityError) -> EmployeeDomainError:
        diagnostic = getattr(exc.orig, "diag", None)
        constraint = getattr(diagnostic, "constraint_name", None)
        if constraint == "ex_employee_assignments_one_primary_period":
            return EmployeeDomainError(
                "EMPLOYEE_ALREADY_ASSIGNED",
                "The employee already has a primary assignment for this period.",
                {"constraint": constraint},
            )
        if constraint == "uq_employees_organization_number":
            return EmployeeDomainError(
                "VALIDATION_FAILED",
                "Employee number already exists.",
                {"field": "employeeNumber"},
                422,
            )
        return EmployeeDomainError(
            "CONCURRENCY_CONFLICT",
            "The requested employee change conflicts with persisted data.",
            {"constraint": constraint} if constraint else {},
        )

    async def lock_assignment_resources(self, employee_id: UUID, staffing_slot_id: UUID) -> None:
        # A consistent employee-then-slot lock order serializes primary/FTE overlap checks.
        await self._session.execute(
            select(EmployeeModel.id).where(EmployeeModel.id == employee_id).with_for_update()
        )
        from app.modules.organization.infrastructure.models import StaffingSlotModel

        await self._session.execute(
            select(StaffingSlotModel.id)
            .where(StaffingSlotModel.id == staffing_slot_id)
            .with_for_update()
        )

    async def lock_delegation_resources(
        self, delegator_employee_id: UUID, delegate_employee_id: UUID
    ) -> None:
        employee_ids = sorted(
            (delegator_employee_id, delegate_employee_id), key=lambda value: value.hex
        )
        await self._session.execute(
            select(EmployeeModel.id)
            .where(EmployeeModel.id.in_(employee_ids))
            .order_by(EmployeeModel.id)
            .with_for_update()
        )


class SqlAlchemyEmployeeUnitOfWorkFactory(EmployeeUnitOfWorkFactory):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        staffing_slot_reader: Callable[[AsyncSession], StaffingSlotReader],
        policy_reader: Callable[[AsyncSession], EmployeePolicyReader],
        audit_sink: Callable[[AsyncSession], AuditSink],
        outbox_sink: Callable[[AsyncSession], OutboxSink],
    ) -> None:
        self._session_factory = session_factory
        self._staffing_slot_reader = staffing_slot_reader
        self._policy_reader = policy_reader
        self._audit_sink = audit_sink
        self._outbox_sink = outbox_sink

    def __call__(self) -> SqlAlchemyEmployeeUnitOfWork:
        session = self._session_factory()
        return SqlAlchemyEmployeeUnitOfWork(
            session,
            self._staffing_slot_reader(session),
            self._policy_reader(session),
            self._audit_sink(session),
            self._outbox_sink(session),
        )
