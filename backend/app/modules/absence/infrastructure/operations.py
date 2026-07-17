from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.audit.service import AuditService
from app.core.errors import ConcurrencyConflictError, ResourceNotFoundError, ValidationError
from app.core.errors.codes import ErrorCode
from app.core.events.domain import ApplicationEvent, EventName
from app.core.events.repository import SqlAlchemyTransactionalOutbox
from app.modules.employees.infrastructure.models import (
    EmployeeAbsenceModel,
    EmployeeAssignmentModel,
    EmployeeModel,
)
from app.modules.organization.infrastructure.models import StaffingSlotModel
from app.modules.workflow.infrastructure.operations import SqlAlchemyWorkflowOperations
from app.shared.time import utc_now

from .models import (
    BusinessTripRequestModel,
    LeaveBalanceModel,
    LeaveRequestModel,
    LeaveTypeModel,
)

View = Mapping[str, object]


class SqlAlchemyAbsenceOperations:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._workflow = SqlAlchemyWorkflowOperations(sessions)

    async def list_leave_types(self, organization_id: UUID) -> Sequence[View]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(LeaveTypeModel)
                    .where(
                        LeaveTypeModel.organization_id == organization_id,
                        LeaveTypeModel.active.is_(True),
                    )
                    .order_by(LeaveTypeModel.name)
                )
            ).all()
            return [_view(row) for row in rows]

    async def list_balances(self, organization_id: UUID, employee_id: UUID) -> Sequence[View]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(LeaveBalanceModel)
                    .where(
                        LeaveBalanceModel.organization_id == organization_id,
                        LeaveBalanceModel.employee_id == employee_id,
                    )
                    .order_by(LeaveBalanceModel.year.desc())
                )
            ).all()
            return [_balance_view(row) for row in rows]

    async def list_requests(
        self,
        resource: str,
        organization_id: UUID,
        offset: int,
        limit: int,
        *,
        employee_id: UUID | None = None,
        unit_id: UUID | None = None,
    ) -> tuple[Sequence[View], int]:
        model = LeaveRequestModel if resource == "leave" else BusinessTripRequestModel
        async with self._sessions() as session:
            statement = select(model).where(model.organization_id == organization_id)
            if employee_id is not None:
                statement = statement.where(model.employee_id == employee_id)
            if unit_id is not None:
                statement = statement.where(model.unit_id == unit_id)
            rows = (
                await session.scalars(
                    statement.order_by(model.created_at.desc()).offset(offset).limit(limit)
                )
            ).all()
            total = int(
                await session.scalar(select(func.count()).select_from(statement.subquery())) or 0
            )
            return [_view(row) for row in rows], total

    async def require_organization(
        self, resource: str, item_id: UUID, organization_id: UUID
    ) -> None:
        model = LeaveRequestModel if resource == "leave" else BusinessTripRequestModel
        async with self._sessions() as session:
            actual = await session.scalar(select(model.organization_id).where(model.id == item_id))
            if actual != organization_id:
                raise ResourceNotFoundError(f"{resource} request", item_id)

    async def create_leave(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> View:
        async with self._sessions.begin() as session:
            employee_id = _uuid(data, "employeeId")
            if await self._actor_employee(session, actor_id) != employee_id:
                raise ValidationError(
                    "Employees may only request their own leave.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            unit_id = await self._employee_unit(session, organization_id, employee_id)
            start, end = _dates(data)
            days = _leave_days(start, end)
            await self._ensure_no_overlap(session, employee_id, start, end)
            leave_type = await session.get(LeaveTypeModel, _uuid(data, "leaveTypeId"))
            if (
                leave_type is None
                or leave_type.organization_id != organization_id
                or not leave_type.active
            ):
                raise ResourceNotFoundError("leave type")
            balance = None
            if leave_type.requires_balance:
                balance = await session.scalar(
                    select(LeaveBalanceModel)
                    .where(
                        LeaveBalanceModel.employee_id == employee_id,
                        LeaveBalanceModel.leave_type_id == leave_type.id,
                        LeaveBalanceModel.year == start.year,
                    )
                    .with_for_update()
                )
                if balance is None:
                    raise ValidationError(
                        "The employee has no leave balance for the requested year.",
                        code=ErrorCode.LEAVE_BALANCE_INSUFFICIENT,
                    )
                available = (
                    balance.entitled_days
                    + balance.carried_days
                    - balance.reserved_days
                    - balance.used_days
                )
                if available < days:
                    raise ValidationError(
                        "The employee has insufficient leave balance.",
                        code=ErrorCode.LEAVE_BALANCE_INSUFFICIENT,
                    )
                balance.reserved_days += days
            row = LeaveRequestModel(
                organization_id=organization_id,
                employee_id=employee_id,
                unit_id=unit_id,
                leave_type_id=leave_type.id,
                start_date=start,
                end_date=end,
                requested_days=days,
                reason=_optional_text(data.get("reason")),
                status="manager_review",
                submitted_at=utc_now(),
            )
            session.add(row)
            await session.flush()
            process = await self._workflow.start_linked_instance(
                session,
                organization_id,
                actor_id,
                {
                    "definitionCode": "leave",
                    "businessType": "leaveRequest",
                    "businessEntityId": row.id,
                    "context": {
                        "subjectEmployeeId": str(employee_id),
                        "unitId": str(unit_id),
                    },
                },
            )
            row.process_instance_id = UUID(str(process["id"]))
            await self._change(
                session,
                actor_id,
                organization_id,
                "leave.request.submitted",
                row,
                EventName.LEAVE_REQUEST_SUBMITTED,
            )
            await session.flush()
            return _view(row)

    async def decide_leave(
        self,
        request_id: UUID,
        actor_id: UUID,
        revision: int,
        stage: str,
        decision: str,
        comment: str,
    ) -> View:
        async with self._sessions.begin() as session:
            row = await _locked(session, LeaveRequestModel, request_id)
            key = f"leave:{row.id}:{stage}:{revision}:{decision}"
            if await self._workflow.linked_action_exists(session, key):
                return _view(row)
            _revision(row.revision, revision)
            if row.status != stage or row.process_instance_id is None:
                raise ValidationError(
                    "Leave request is not awaiting this review.",
                    code=ErrorCode.ABSENCE_ACTION_NOT_ALLOWED,
                )
            if decision in {"return", "reject"} and not comment.strip():
                raise ValidationError("A decision reason is required.")
            before = _view(row)
            if decision == "approve" and stage == "manager_review":
                row.status = "hr_review"
            elif decision == "approve":
                row.status = "approved"
                row.approved_at = utc_now()
                await self._consume_balance(session, row)
                await self._register_calendar_absence(session, row, actor_id, "vacation")
            elif decision == "return":
                row.returned_from_stage = stage
                row.status = "returned"
            else:
                row.status = "rejected"
                await self._release_balance(session, row)
            row.revision += 1
            await self._workflow.act_linked_task(
                session,
                row.process_instance_id,
                actor_id,
                decision,
                comment,
                key,
                expected_phase=stage,
            )
            await self._audit(
                session,
                actor_id,
                row.organization_id,
                "leave.request.reviewed",
                row,
                before,
                comment,
            )
            if row.status == "approved":
                await self._event(session, EventName.LEAVE_REQUEST_APPROVED, row)
            elif row.status == "rejected":
                await self._event(session, EventName.LEAVE_REQUEST_REJECTED, row)
            return _view(row)

    async def resubmit_leave(
        self, request_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> View:
        async with self._sessions.begin() as session:
            row = await _locked(session, LeaveRequestModel, request_id)
            _revision(row.revision, revision)
            if await self._actor_employee(session, actor_id) != row.employee_id:
                raise ValidationError(
                    "Only the employee may resubmit leave.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            if row.status != "returned" or row.process_instance_id is None:
                raise ValidationError("Only a returned leave request may be resubmitted.")
            account_employee = await self._actor_employee(session, actor_id)
            if account_employee != row.employee_id:
                raise ValidationError(
                    "Only the employee may resubmit leave.", code=ErrorCode.AUTH_SCOPE_VIOLATION
                )
            start, end = _dates(data)
            old_days = row.requested_days
            new_days = _leave_days(start, end)
            await self._ensure_no_overlap(session, row.employee_id, start, end, exclude_id=row.id)
            await self._resize_reservation(session, row, old_days, new_days)
            row.start_date, row.end_date, row.requested_days = start, end, new_days
            row.reason = _optional_text(data.get("reason"))
            row.status = row.returned_from_stage or "manager_review"
            row.returned_from_stage = None
            row.revision += 1
            await self._workflow.resume_linked_task(
                session, row.process_instance_id, actor_id, f"leave:{row.id}:resubmit:{revision}"
            )
            await self._audit(
                session, actor_id, row.organization_id, "leave.request.resubmitted", row
            )
            return _view(row)

    async def cancel_leave(
        self, request_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> View:
        async with self._sessions.begin() as session:
            row = await _locked(session, LeaveRequestModel, request_id)
            _revision(row.revision, revision)
            if await self._actor_employee(session, actor_id) != row.employee_id:
                raise ValidationError(
                    "Only the employee may cancel leave.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            if row.status in {"cancelled", "rejected"} or row.start_date <= date.today():
                raise ValidationError("Leave can no longer be cancelled.")
            before = _view(row)
            await self._release_balance(session, row, approved=row.status == "approved")
            await self._cancel_calendar_absence(session, "leave_request", row.id)
            row.status = "cancelled"
            row.cancelled_at = utc_now()
            row.cancellation_reason = _required_text(reason)
            row.revision += 1
            if row.process_instance_id is None:
                raise ValidationError("Leave request has no linked workflow.")
            await self._workflow.cancel_linked_instance(
                session, row.process_instance_id, actor_id, reason
            )
            await self._audit(
                session,
                actor_id,
                row.organization_id,
                "leave.request.cancelled",
                row,
                before,
                reason,
            )
            await self._event(session, EventName.LEAVE_REQUEST_CANCELLED, row)
            return _view(row)

    async def create_trip(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> View:
        async with self._sessions.begin() as session:
            employee_id = _uuid(data, "employeeId")
            if await self._actor_employee(session, actor_id) != employee_id:
                raise ValidationError(
                    "Employees may only request their own trips.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            unit_id = await self._employee_unit(session, organization_id, employee_id)
            start, end = _dates(data)
            await self._ensure_no_overlap(session, employee_id, start, end)
            row = BusinessTripRequestModel(
                organization_id=organization_id,
                employee_id=employee_id,
                unit_id=unit_id,
                destination=_required_text(data.get("destination")),
                start_date=start,
                end_date=end,
                purpose=_required_text(data.get("purpose")),
                estimated_cost=Decimal(str(data.get("estimatedCost", 0))),
                currency=_currency(data.get("currency")),
                funding_details=dict(cast(Mapping[str, Any], data.get("fundingDetails", {}))),
                status="manager_review",
                submitted_at=utc_now(),
            )
            session.add(row)
            await session.flush()
            process = await self._workflow.start_linked_instance(
                session,
                organization_id,
                actor_id,
                {
                    "definitionCode": "business_trip",
                    "businessType": "businessTripRequest",
                    "businessEntityId": row.id,
                    "context": {"subjectEmployeeId": str(employee_id), "unitId": str(unit_id)},
                },
            )
            row.process_instance_id = UUID(str(process["id"]))
            await self._change(
                session,
                actor_id,
                organization_id,
                "business_trip.submitted",
                row,
                EventName.BUSINESS_TRIP_SUBMITTED,
            )
            await session.flush()
            return _view(row)

    async def decide_trip(
        self,
        request_id: UUID,
        actor_id: UUID,
        revision: int,
        stage: str,
        decision: str,
        comment: str,
    ) -> View:
        async with self._sessions.begin() as session:
            row = await _locked(session, BusinessTripRequestModel, request_id)
            key = f"business-trip:{row.id}:{stage}:{revision}:{decision}"
            if await self._workflow.linked_action_exists(session, key):
                return _view(row)
            _revision(row.revision, revision)
            if row.status != stage or row.process_instance_id is None:
                raise ValidationError("Trip is not awaiting this review.")
            if decision in {"return", "reject"} and not comment.strip():
                raise ValidationError("A decision reason is required.")
            before = _view(row)
            next_stage = {"manager_review": "finance_review", "finance_review": "hr_registration"}
            if decision == "approve" and stage in next_stage:
                row.status = next_stage[stage]
                if stage == "finance_review":
                    row.approved_at = utc_now()
                action = "approve"
            elif decision == "approve":
                row.status = "registered"
                row.approved_at = row.approved_at or utc_now()
                row.registered_at = utc_now()
                await self._register_calendar_absence(session, row, actor_id, "business_trip")
                action = "complete"
            elif decision == "return":
                row.returned_from_stage = stage
                row.status = "returned"
                action = "return"
            else:
                row.status = "rejected"
                action = "reject"
            row.revision += 1
            await self._workflow.act_linked_task(
                session,
                row.process_instance_id,
                actor_id,
                action,
                comment,
                key,
                expected_phase=stage,
            )
            await self._audit(
                session,
                actor_id,
                row.organization_id,
                "business_trip.reviewed",
                row,
                before,
                comment,
            )
            event = {
                "registered": EventName.BUSINESS_TRIP_REGISTERED,
                "rejected": EventName.BUSINESS_TRIP_REJECTED,
                "hr_registration": EventName.BUSINESS_TRIP_APPROVED,
            }.get(row.status)
            if event:
                await self._event(session, event, row)
            return _view(row)

    async def resubmit_trip(
        self, request_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> View:
        async with self._sessions.begin() as session:
            row = await _locked(session, BusinessTripRequestModel, request_id)
            _revision(row.revision, revision)
            if await self._actor_employee(session, actor_id) != row.employee_id:
                raise ValidationError(
                    "Only the employee may resubmit a trip.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            if row.status != "returned" or row.process_instance_id is None:
                raise ValidationError("Only a returned trip may be resubmitted.")
            if await self._actor_employee(session, actor_id) != row.employee_id:
                raise ValidationError(
                    "Only the employee may resubmit a trip.", code=ErrorCode.AUTH_SCOPE_VIOLATION
                )
            start, end = _dates(data)
            await self._ensure_no_overlap(session, row.employee_id, start, end, exclude_id=row.id)
            row.destination = _required_text(data.get("destination"))
            row.start_date, row.end_date = start, end
            row.purpose = _required_text(data.get("purpose"))
            row.estimated_cost = Decimal(str(data.get("estimatedCost", 0)))
            row.currency = _currency(data.get("currency"))
            row.funding_details = dict(cast(Mapping[str, Any], data.get("fundingDetails", {})))
            row.status = row.returned_from_stage or "manager_review"
            row.returned_from_stage = None
            row.revision += 1
            await self._workflow.resume_linked_task(
                session,
                row.process_instance_id,
                actor_id,
                f"business-trip:{row.id}:resubmit:{revision}",
            )
            await self._audit(
                session, actor_id, row.organization_id, "business_trip.resubmitted", row
            )
            return _view(row)

    async def cancel_trip(
        self, request_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> View:
        async with self._sessions.begin() as session:
            row = await _locked(session, BusinessTripRequestModel, request_id)
            _revision(row.revision, revision)
            if await self._actor_employee(session, actor_id) != row.employee_id:
                raise ValidationError(
                    "Only the employee may cancel a trip.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            if row.status in {"cancelled", "rejected"} or row.start_date <= date.today():
                raise ValidationError("Trip can no longer be cancelled.")
            before = _view(row)
            await self._cancel_calendar_absence(session, "business_trip_request", row.id)
            row.status = "cancelled"
            row.cancelled_at = utc_now()
            row.cancellation_reason = _required_text(reason)
            row.revision += 1
            if row.process_instance_id is None:
                raise ValidationError("Trip has no linked workflow.")
            await self._workflow.cancel_linked_instance(
                session, row.process_instance_id, actor_id, reason
            )
            await self._audit(
                session,
                actor_id,
                row.organization_id,
                "business_trip.cancelled",
                row,
                before,
                reason,
            )
            await self._event(session, EventName.BUSINESS_TRIP_CANCELLED, row)
            return _view(row)

    async def _employee_unit(
        self, session: AsyncSession, organization_id: UUID, employee_id: UUID
    ) -> UUID:
        unit_id = await session.scalar(
            select(StaffingSlotModel.organization_unit_id)
            .join(
                EmployeeAssignmentModel,
                EmployeeAssignmentModel.staffing_slot_id == StaffingSlotModel.id,
            )
            .join(EmployeeModel, EmployeeModel.id == EmployeeAssignmentModel.employee_id)
            .where(
                EmployeeModel.id == employee_id,
                EmployeeModel.organization_id == organization_id,
                EmployeeModel.active.is_(True),
                EmployeeAssignmentModel.primary.is_(True),
                EmployeeAssignmentModel.status.in_(("active", "planned")),
            )
            .order_by(EmployeeAssignmentModel.effective_from.desc())
        )
        if unit_id is None:
            raise ResourceNotFoundError("active employee assignment")
        return unit_id

    async def _actor_employee(self, session: AsyncSession, actor_id: UUID) -> UUID | None:
        from app.modules.identity.infrastructure.models import UserAccountModel

        return await session.scalar(
            select(UserAccountModel.employee_id).where(UserAccountModel.id == actor_id)
        )

    async def _ensure_no_overlap(
        self,
        session: AsyncSession,
        employee_id: UUID,
        start: date,
        end: date,
        exclude_id: UUID | None = None,
    ) -> None:
        leave = select(LeaveRequestModel.id).where(
            LeaveRequestModel.employee_id == employee_id,
            LeaveRequestModel.status.not_in(("rejected", "cancelled")),
            LeaveRequestModel.start_date <= end,
            LeaveRequestModel.end_date >= start,
        )
        trip = select(BusinessTripRequestModel.id).where(
            BusinessTripRequestModel.employee_id == employee_id,
            BusinessTripRequestModel.status.not_in(("rejected", "cancelled")),
            BusinessTripRequestModel.start_date <= end,
            BusinessTripRequestModel.end_date >= start,
        )
        if exclude_id:
            leave = leave.where(LeaveRequestModel.id != exclude_id)
            trip = trip.where(BusinessTripRequestModel.id != exclude_id)
        calendar = select(EmployeeAbsenceModel.id).where(
            EmployeeAbsenceModel.employee_id == employee_id,
            EmployeeAbsenceModel.status != "cancelled",
            EmployeeAbsenceModel.date_from <= end,
            EmployeeAbsenceModel.date_to >= start,
        )
        if exclude_id:
            calendar = calendar.where(
                or_(
                    EmployeeAbsenceModel.source_id.is_(None),
                    EmployeeAbsenceModel.source_id != exclude_id,
                )
            )
        if (
            await session.scalar(leave)
            or await session.scalar(trip)
            or await session.scalar(calendar)
        ):
            raise ValidationError(
                "Absence dates overlap an existing request.", code=ErrorCode.ABSENCE_DATE_CONFLICT
            )

    async def _balance(
        self, session: AsyncSession, row: LeaveRequestModel
    ) -> LeaveBalanceModel | None:
        return await session.scalar(  # type: ignore[no-any-return]
            select(LeaveBalanceModel)
            .where(
                LeaveBalanceModel.employee_id == row.employee_id,
                LeaveBalanceModel.leave_type_id == row.leave_type_id,
                LeaveBalanceModel.year == row.start_date.year,
            )
            .with_for_update()
        )

    async def _consume_balance(self, session: AsyncSession, row: LeaveRequestModel) -> None:
        balance = await self._balance(session, row)
        if balance:
            balance.reserved_days -= row.requested_days
            balance.used_days += row.requested_days

    async def _release_balance(
        self, session: AsyncSession, row: LeaveRequestModel, *, approved: bool = False
    ) -> None:
        balance = await self._balance(session, row)
        if balance:
            if approved:
                balance.used_days -= row.requested_days
            else:
                balance.reserved_days -= row.requested_days

    async def _resize_reservation(
        self, session: AsyncSession, row: LeaveRequestModel, old: Decimal, new: Decimal
    ) -> None:
        balance = await self._balance(session, row)
        if balance:
            available = (
                balance.entitled_days
                + balance.carried_days
                - balance.reserved_days
                - balance.used_days
                + old
            )
            if available < new:
                raise ValidationError(
                    "The employee has insufficient leave balance.",
                    code=ErrorCode.LEAVE_BALANCE_INSUFFICIENT,
                )
            balance.reserved_days += new - old

    async def _register_calendar_absence(
        self,
        session: AsyncSession,
        row: LeaveRequestModel | BusinessTripRequestModel,
        actor_id: UUID,
        absence_type: str,
    ) -> None:
        source_type = (
            "leave_request" if isinstance(row, LeaveRequestModel) else "business_trip_request"
        )
        existing = await session.scalar(
            select(EmployeeAbsenceModel.id).where(
                EmployeeAbsenceModel.source_type == source_type,
                EmployeeAbsenceModel.source_id == row.id,
            )
        )
        if existing is not None:
            return
        conflict = await session.scalar(
            select(EmployeeAbsenceModel.id).where(
                EmployeeAbsenceModel.employee_id == row.employee_id,
                EmployeeAbsenceModel.status != "cancelled",
                EmployeeAbsenceModel.date_from <= row.end_date,
                EmployeeAbsenceModel.date_to >= row.start_date,
            )
        )
        if conflict is not None:
            raise ValidationError(
                "The approved absence overlaps a registered employee absence.",
                code=ErrorCode.ABSENCE_DATE_CONFLICT,
            )
        reason = row.reason if isinstance(row, LeaveRequestModel) else row.purpose
        details = None if isinstance(row, LeaveRequestModel) else row.destination
        session.add(
            EmployeeAbsenceModel(
                id=uuid4(),
                employee_id=row.employee_id,
                absence_type=absence_type,
                date_from=row.start_date,
                date_to=row.end_date,
                reason=(reason or "Approved absence")[:1000],
                details=details[:300] if details else None,
                status="scheduled",
                created_by=actor_id,
                source_document_id=None,
                source_type=source_type,
                source_id=row.id,
                created_at=utc_now(),
                updated_at=utc_now(),
                revision=1,
            )
        )

    async def _cancel_calendar_absence(
        self, session: AsyncSession, source_type: str, source_id: UUID
    ) -> None:
        absence = await session.scalar(
            select(EmployeeAbsenceModel)
            .where(
                EmployeeAbsenceModel.source_type == source_type,
                EmployeeAbsenceModel.source_id == source_id,
            )
            .with_for_update()
        )
        if absence is not None and absence.status != "cancelled":
            absence.status = "cancelled"
            absence.updated_at = utc_now()
            absence.revision += 1

    async def _audit(
        self,
        session: AsyncSession,
        actor_id: UUID,
        organization_id: UUID,
        action: str,
        row: Any,
        before: Mapping[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        await AuditService(SqlAlchemyAuditLog(session)).record(
            actor_id=actor_id,
            organization_id=organization_id,
            action=action,
            entity_type=row.__tablename__,
            entity_id=row.id,
            before_state=before,
            after_state=_view(row),
            reason=reason,
        )

    async def _event(self, session: AsyncSession, name: EventName, row: Any) -> None:
        await SqlAlchemyTransactionalOutbox(session).append(
            ApplicationEvent(
                name=name,
                aggregate_type=row.__tablename__,
                aggregate_id=row.id,
                payload={"id": str(row.id)},
            )
        )

    async def _change(
        self,
        session: AsyncSession,
        actor: UUID,
        organization: UUID,
        action: str,
        row: Any,
        event: EventName,
    ) -> None:
        await self._audit(session, actor, organization, action, row)
        await self._event(session, event, row)


async def _locked(session: AsyncSession, model: Any, item_id: UUID) -> Any:
    row = await session.get(model, item_id, with_for_update=True)
    if row is None:
        raise ResourceNotFoundError(model.__tablename__, item_id)
    return row


def _revision(actual: int, expected: int) -> None:
    if actual != expected:
        raise ConcurrencyConflictError(
            details={"expectedRevision": expected, "actualRevision": actual}
        )


def _dates(data: Mapping[str, object]) -> tuple[date, date]:
    start, end = data.get("startDate"), data.get("endDate")
    if (
        not isinstance(start, date)
        or not isinstance(end, date)
        or start < date.today()
        or end < start
    ):
        raise ValidationError("Absence dates are invalid.", code=ErrorCode.ABSENCE_DATE_INVALID)
    return start, end


def _leave_days(start: date, end: date) -> Decimal:
    return Decimal((end - start).days + 1)


def _uuid(data: Mapping[str, object], key: str) -> UUID:
    return UUID(str(data[key]))


def _required_text(value: object) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValidationError("A required value is missing.")
    return result


def _optional_text(value: object) -> str | None:
    result = str(value or "").strip()
    return result or None


def _currency(value: object) -> str:
    result = _required_text(value).upper()
    if len(result) != 3:
        raise ValidationError("Currency must be an ISO 4217 code.")
    return result


def _view(row: Any) -> dict[str, Any]:
    return {column.key: getattr(row, column.key) for column in row.__table__.columns}


def _balance_view(row: LeaveBalanceModel) -> dict[str, Any]:
    result = _view(row)
    result["available_days"] = (
        row.entitled_days + row.carried_days - row.reserved_days - row.used_days
    )
    return result
