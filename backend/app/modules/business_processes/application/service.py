"""Business rules for correspondence, tasks, hiring, and leave workflows."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.models import AuditEventModel
from app.core.audit.service import sanitize_audit_state
from app.core.errors import ConflictError, ForbiddenError, ResourceNotFoundError, ValidationError
from app.core.events.models import OutboxEventModel
from app.core.security.identity import Principal
from app.modules.access_control.infrastructure.models import RoleModel, UserRoleAssignmentModel
from app.modules.employees.infrastructure.models import (
    EmployeeAssignmentModel,
    EmployeeModel,
    PersonModel,
)
from app.modules.organization.infrastructure.models import (
    OrganizationUnitModel,
    PositionDefinitionModel,
    StaffingSlotModel,
)

from ..api.schemas import IncomingLetterRequest
from ..infrastructure.models import (
    CorrespondenceModel,
    HiringRequestModel,
    LeaveRequestModel,
    ProcessDefinitionModel,
    WorkTaskModel,
)

LEAVE_ROUTE = {
    "version": 1,
    "steps": ["employee", "manager", "hr", "signer", "accounting"],
    "negativeDecisionRequiresReason": True,
}
HIRING_ROUTE = {
    "version": 1,
    "steps": ["manager", "hr_check", "budget_check", "vacancy", "selection", "employment"],
    "negativeDecisionRequiresReason": True,
}

type EmployeeRow = tuple[
    EmployeeModel,
    PersonModel,
    EmployeeAssignmentModel | None,
    StaffingSlotModel | None,
    PositionDefinitionModel | None,
    OrganizationUnitModel | None,
]


def _now() -> datetime:
    return datetime.now(UTC)


def _audit_entry(actor: str, action: str, detail: str) -> dict[str, str]:
    return {
        "id": str(uuid4()),
        "at": _now().isoformat(),
        "actor": actor,
        "action": action,
        "detail": detail,
    }


def _actor_name(principal: Principal) -> str:
    return principal.subject.removeprefix("development:")


class BusinessProcessService:
    def __init__(self, session: AsyncSession, principal: Principal) -> None:
        self.session = session
        self.principal = principal

    async def _role_codes(self) -> frozenset[str]:
        now = _now()
        codes = await self.session.scalars(
            select(RoleModel.code)
            .join(UserRoleAssignmentModel, UserRoleAssignmentModel.role_id == RoleModel.id)
            .where(
                UserRoleAssignmentModel.user_id == self.principal.user_id,
                UserRoleAssignmentModel.revoked_at.is_(None),
                UserRoleAssignmentModel.effective_from <= now,
                or_(
                    UserRoleAssignmentModel.effective_to.is_(None),
                    UserRoleAssignmentModel.effective_to > now,
                ),
                RoleModel.active.is_(True),
            )
        )
        return frozenset(codes)

    async def _record_change(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: UUID,
        after: dict[str, object],
        event_name: str,
    ) -> None:
        organization_id = self.principal.organization_id
        self.session.add(
            AuditEventModel(
                id=uuid4(),
                organization_id=organization_id,
                actor_id=self.principal.user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                before_state=None,
                after_state=sanitize_audit_state(after),
                reason=None,
                request_id=None,
                occurred_at=_now(),
            )
        )
        self.session.add(
            OutboxEventModel(
                id=uuid4(),
                event_name=event_name,
                aggregate_type=entity_type,
                aggregate_id=entity_id,
                payload=sanitize_audit_state(after),
                schema_version=1,
                occurred_at=_now(),
                available_at=_now(),
                attempts=0,
            )
        )

    async def list_correspondence(self) -> list[CorrespondenceModel]:
        result = await self.session.scalars(
            select(CorrespondenceModel).order_by(CorrespondenceModel.received_at.desc())
        )
        return list(result)

    async def get_correspondence(self, item_id: UUID) -> CorrespondenceModel:
        item = await self.session.get(CorrespondenceModel, item_id)
        if item is None:
            raise ResourceNotFoundError("correspondence", item_id)
        return item

    async def find_duplicate(self, sender: str, sender_number: str) -> CorrespondenceModel | None:
        result = await self.session.scalar(
            select(CorrespondenceModel).where(
                func.lower(CorrespondenceModel.sender) == sender.strip().lower(),
                func.lower(CorrespondenceModel.sender_number) == sender_number.strip().lower(),
            )
        )
        return result

    async def register_correspondence(self, body: IncomingLetterRequest) -> CorrespondenceModel:
        if body.due_date < body.sender_date:
            raise ValidationError("Due date cannot precede the sender date.")
        duplicate = await self.find_duplicate(body.sender, body.sender_number)
        if duplicate is not None:
            raise ConflictError("A letter with this sender and sender number already exists.")
        await self.session.execute(
            text("LOCK TABLE correspondence_items IN SHARE ROW EXCLUSIVE MODE")
        )
        sequence = (
            int(
                await self.session.scalar(select(func.count()).select_from(CorrespondenceModel))
                or 0
            )
            + 1
        )
        item_id = uuid4()
        number = f"IN-{date.today().year}-{sequence:06d}"
        actor = _actor_name(self.principal)
        item = CorrespondenceModel(
            id=item_id,
            number=number,
            sender=body.sender,
            sender_number=body.sender_number,
            sender_date=body.sender_date,
            received_at=_now(),
            subject=body.subject,
            summary=body.summary,
            document_type=body.document_type,
            channel=body.channel,
            department=body.department,
            executive=body.executive,
            executor="Not assigned",
            due_date=body.due_date,
            priority=body.priority,
            status="registered",
            workflow_step="Registration completed",
            confidentiality=body.confidentiality,
            response_required=body.response_required,
            attachments=[],
            tags=[body.language, body.sender_type],
            audit_log=[_audit_entry(actor, "Registered", f"Registry assigned {number}")],
            created_at=_now(),
            updated_at=_now(),
            revision=1,
        )
        self.session.add(item)
        await self._record_change(
            action="correspondence.registered",
            entity_type="correspondence",
            entity_id=item.id,
            after={"number": number, "status": item.status},
            event_name="correspondenceRegistered",
        )
        await self.session.commit()
        return item

    async def send_for_resolution(self, item_id: UUID) -> CorrespondenceModel:
        item = await self.get_correspondence(item_id)
        if item.status != "registered":
            raise ConflictError("Only a registered letter can be sent for resolution.")
        actor = _actor_name(self.principal)
        item.status = "resolution"
        item.workflow_step = "Executive resolution"
        item.revision += 1
        item.audit_log = [
            _audit_entry(
                actor, "Sent for resolution", "A task was assigned to the designated executive."
            ),
            *item.audit_log,
        ]
        self.session.add(
            WorkTaskModel(
                id=uuid4(),
                title=f"Prepare resolution: {item.subject}",
                document_number=item.number,
                process="Incoming correspondence",
                role="Executive",
                department=item.department,
                due_date=item.due_date,
                priority=item.priority,
                state="available",
                assignee=None,
                source_type="correspondence",
                source_id=item.id,
                revision=1,
            )
        )
        await self._record_change(
            action="correspondence.sent_for_resolution",
            entity_type="correspondence",
            entity_id=item.id,
            after={"number": item.number, "status": item.status},
            event_name="correspondenceResolutionRequested",
        )
        await self.session.commit()
        return item

    async def list_tasks(self) -> list[WorkTaskModel]:
        result = await self.session.scalars(
            select(WorkTaskModel).order_by(WorkTaskModel.due_date, WorkTaskModel.created_at)
        )
        tasks = list(result)
        today = date.today()
        for task in tasks:
            if task.state in {"available", "claimed"} and task.due_date < today:
                task.state = "overdue"
        return tasks

    async def change_task(self, task_id: UUID, action: str) -> WorkTaskModel:
        task = await self.session.get(WorkTaskModel, task_id)
        if task is None:
            raise ResourceNotFoundError("task", task_id)
        actor = _actor_name(self.principal)
        if action == "claim" and task.state in {"available", "overdue"}:
            task.state = "claimed"
            task.assignee = actor
        elif action == "complete" and task.state == "claimed":
            task.state = "completed"
        else:
            raise ConflictError(f"Task cannot perform '{action}' from state '{task.state}'.")
        task.revision += 1
        await self._record_change(
            action=f"task.{action}",
            entity_type="work_task",
            entity_id=task.id,
            after={"state": task.state, "assignee": task.assignee or ""},
            event_name="workTaskChanged",
        )
        await self.session.commit()
        return task

    async def list_processes(self) -> list[ProcessDefinitionModel]:
        return list(
            await self.session.scalars(
                select(ProcessDefinitionModel).order_by(ProcessDefinitionModel.name)
            )
        )

    async def retry_process(self, process_id: str) -> ProcessDefinitionModel:
        process = await self.session.get(ProcessDefinitionModel, process_id)
        if process is None:
            raise ResourceNotFoundError("process_definition", process_id)
        if process.state != "incident":
            raise ConflictError("Only a process in incident state can be retried.")
        process.state = "published"
        process.updated_at = _now()
        process.revision += 1
        await self.session.commit()
        return process

    async def dashboard(self) -> dict[str, int]:
        today = date.today()
        incoming_today = int(
            await self.session.scalar(
                select(func.count())
                .select_from(CorrespondenceModel)
                .where(func.date(CorrespondenceModel.received_at) == today)
            )
            or 0
        )
        awaiting = int(
            await self.session.scalar(
                select(func.count())
                .select_from(CorrespondenceModel)
                .where(CorrespondenceModel.status == "resolution")
            )
            or 0
        )
        active_tasks = int(
            await self.session.scalar(
                select(func.count())
                .select_from(WorkTaskModel)
                .where(WorkTaskModel.state != "completed")
            )
            or 0
        )
        overdue = int(
            await self.session.scalar(
                select(func.count())
                .select_from(WorkTaskModel)
                .where(
                    or_(
                        WorkTaskModel.state == "overdue",
                        and_(WorkTaskModel.state != "completed", WorkTaskModel.due_date < today),
                    )
                )
            )
            or 0
        )
        signature = int(
            await self.session.scalar(
                select(func.count())
                .select_from(CorrespondenceModel)
                .where(CorrespondenceModel.status == "signature")
            )
            or 0
        )
        dispatch = int(
            await self.session.scalar(
                select(func.count())
                .select_from(CorrespondenceModel)
                .where(CorrespondenceModel.status == "dispatch")
            )
            or 0
        )
        return {
            "incoming_today": incoming_today,
            "awaiting_resolution": awaiting,
            "active_tasks": active_tasks,
            "overdue": overdue,
            "signature_queue": signature,
            "dispatch_queue": dispatch,
        }

    async def list_leaves(self) -> list[LeaveRequestModel]:
        return list(
            await self.session.scalars(
                select(LeaveRequestModel).order_by(LeaveRequestModel.created_at.desc())
            )
        )

    async def create_leave(
        self,
        *,
        employee_id: UUID,
        leave_type: str,
        start_date: date,
        end_date: date,
        comment: str,
        substitute: str,
    ) -> LeaveRequestModel:
        if end_date < start_date:
            raise ValidationError("Leave end date cannot precede its start date.")
        employee_row = await self.session.execute(
            select(EmployeeModel, PersonModel)
            .join(PersonModel, PersonModel.id == EmployeeModel.person_id)
            .where(EmployeeModel.id == employee_id, EmployeeModel.active.is_(True))
        )
        pair = employee_row.one_or_none()
        if pair is None:
            raise ResourceNotFoundError("employee", employee_id)
        employee, person = pair
        overlap = await self.session.scalar(
            select(LeaveRequestModel.id)
            .where(
                LeaveRequestModel.employee_id == employee_id,
                LeaveRequestModel.status.in_(["pending_manager", "hr_review", "approved"]),
                LeaveRequestModel.start_date <= end_date,
                LeaveRequestModel.end_date >= start_date,
            )
            .limit(1)
        )
        if overlap is not None:
            raise ConflictError("Leave dates overlap another active request.")
        days = (end_date - start_date).days + 1
        used = int(
            await self.session.scalar(
                select(func.coalesce(func.sum(LeaveRequestModel.days), 0)).where(
                    LeaveRequestModel.employee_id == employee_id,
                    LeaveRequestModel.status == "approved",
                    func.extract("year", LeaveRequestModel.start_date) == start_date.year,
                )
            )
            or 0
        )
        if days > max(0, 24 - used):
            raise ConflictError("Requested leave exceeds the available balance.")
        await self.session.execute(text("LOCK TABLE leave_requests IN SHARE ROW EXCLUSIVE MODE"))
        sequence = (
            int(await self.session.scalar(select(func.count()).select_from(LeaveRequestModel)) or 0)
            + 1
        )
        request_id = uuid4()
        document_number = f"HR-LV-{date.today().year}-{sequence:04d}"
        item = LeaveRequestModel(
            id=request_id,
            employee_id=employee.id,
            employee_name=person.display_name,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            days=days,
            comment=comment,
            substitute=substitute,
            status="pending_manager",
            document_number=document_number,
            workflow_step="Manager approval",
            route_snapshot=LEAVE_ROUTE,
            audit_log=[
                _audit_entry(
                    _actor_name(self.principal),
                    "Request created",
                    f"Created {document_number}; route version 1 was fixed.",
                )
            ],
            created_at=_now(),
            updated_at=_now(),
            revision=1,
        )
        self.session.add(item)
        self.session.add(
            WorkTaskModel(
                id=uuid4(),
                title=f"Approve leave for {person.display_name}",
                document_number=document_number,
                process="Leave",
                role="Direct manager",
                department="Employee department",
                due_date=start_date,
                priority="normal",
                state="available",
                assignee=None,
                source_type="leave",
                source_id=request_id,
                revision=1,
            )
        )
        await self._record_change(
            action="leave.created",
            entity_type="leave_request",
            entity_id=item.id,
            after={"documentNumber": document_number, "status": item.status},
            event_name="leaveRequestCreated",
        )
        await self.session.commit()
        return item

    async def review_leave(self, item_id: UUID, decision: str, reason: str) -> LeaveRequestModel:
        item = await self.session.get(LeaveRequestModel, item_id)
        if item is None:
            raise ResourceNotFoundError("leave_request", item_id)
        if decision == "reject" and not reason.strip():
            raise ValidationError("A rejection reason is required.")
        roles = await self._role_codes()
        is_admin = "system-administrator" in roles
        if item.status == "pending_manager":
            if not is_admin and "department-director" not in roles:
                raise ForbiddenError("Only the employee's manager may perform this step.")
            item.status = "hr_review" if decision == "approve" else "rejected"
            item.workflow_step = "HR review" if decision == "approve" else "Rejected by manager"
        elif item.status == "hr_review":
            if not is_admin and "hr-administrator" not in roles:
                raise ForbiddenError("Only HR may perform this step.")
            item.status = "approved" if decision == "approve" else "rejected"
            item.workflow_step = "Completed" if decision == "approve" else "Rejected by HR"
        else:
            raise ConflictError("This leave request is not reviewable in its current state.")
        item.audit_log = [
            _audit_entry(
                _actor_name(self.principal), f"Decision: {decision}", reason or item.workflow_step
            ),
            *item.audit_log,
        ]
        item.revision += 1
        await self._record_change(
            action=f"leave.{decision}",
            entity_type="leave_request",
            entity_id=item.id,
            after={"status": item.status, "reason": reason},
            event_name="leaveRequestChanged",
        )
        await self.session.commit()
        return item

    async def employee_rows(self) -> list[EmployeeRow]:
        statement = (
            select(
                EmployeeModel,
                PersonModel,
                EmployeeAssignmentModel,
                StaffingSlotModel,
                PositionDefinitionModel,
                OrganizationUnitModel,
            )
            .join(PersonModel, PersonModel.id == EmployeeModel.person_id)
            .outerjoin(
                EmployeeAssignmentModel,
                and_(
                    EmployeeAssignmentModel.employee_id == EmployeeModel.id,
                    EmployeeAssignmentModel.status.in_(["active", "planned", "scheduled_end"]),
                    EmployeeAssignmentModel.primary.is_(True),
                ),
            )
            .outerjoin(
                StaffingSlotModel, StaffingSlotModel.id == EmployeeAssignmentModel.staffing_slot_id
            )
            .outerjoin(
                PositionDefinitionModel,
                PositionDefinitionModel.id == StaffingSlotModel.position_definition_id,
            )
            .outerjoin(
                OrganizationUnitModel,
                OrganizationUnitModel.id == StaffingSlotModel.organization_unit_id,
            )
            .order_by(EmployeeModel.employee_number)
        )
        rows = (await self.session.execute(statement)).tuples().all()
        seen: set[UUID] = set()
        unique: list[EmployeeRow] = []
        for row in rows:
            if row[0].id not in seen:
                seen.add(row[0].id)
                unique.append(cast(EmployeeRow, row))
        return unique

    async def create_hiring_request(
        self, values: dict[str, object], attachments: list[dict[str, object]]
    ) -> HiringRequestModel:
        required = (
            "firstName",
            "lastName",
            "department",
            "position",
            "manager",
            "startDate",
            "justification",
            "requestText",
        )
        missing = [field for field in required if not str(values.get(field, "")).strip()]
        if missing:
            raise ValidationError(
                "Hiring request is incomplete.",
                problems=[{"field": field, "message": "Required"} for field in missing],
            )
        await self.session.execute(text("LOCK TABLE hiring_requests IN SHARE ROW EXCLUSIVE MODE"))
        sequence = (
            int(
                await self.session.scalar(select(func.count()).select_from(HiringRequestModel)) or 0
            )
            + 1
        )
        item_id = uuid4()
        number = f"HR-HIRE-{date.today().year}-{sequence:04d}"
        item = HiringRequestModel(
            id=item_id,
            number=number,
            payload=sanitize_audit_state(values),
            attachments=attachments,
            status="on_check",
            current_step="HR completeness check",
            route_snapshot=HIRING_ROUTE,
            audit_log=[
                _audit_entry(
                    _actor_name(self.principal),
                    "Hiring request submitted",
                    f"Created {number}; route version 1 was fixed.",
                )
            ],
            created_by=self.principal.user_id,
            created_at=_now(),
            updated_at=_now(),
            revision=1,
        )
        self.session.add(item)
        self.session.add(
            WorkTaskModel(
                id=uuid4(),
                title=f"Check hiring request: {values['position']}",
                document_number=number,
                process="Hiring",
                role="HR recruiter",
                department=str(values["department"]),
                due_date=date.today(),
                priority="normal",
                state="available",
                assignee=None,
                source_type="hiring",
                source_id=item_id,
                revision=1,
            )
        )
        await self._record_change(
            action="hiring.submitted",
            entity_type="hiring_request",
            entity_id=item.id,
            after={"number": number, "status": item.status},
            event_name="hiringRequestSubmitted",
        )
        await self.session.commit()
        return item
