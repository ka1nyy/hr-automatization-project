from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.audit.service import AuditService
from app.core.errors import ConcurrencyConflictError, ResourceNotFoundError, ValidationError
from app.core.errors.codes import ErrorCode
from app.core.events.domain import ApplicationEvent, EventName
from app.core.events.repository import SqlAlchemyTransactionalOutbox
from app.modules.absence.infrastructure.models import BusinessTripRequestModel, LeaveRequestModel
from app.modules.documents.infrastructure.models import (
    DocumentChecklistItemModel,
    DocumentRecordModel,
)
from app.modules.employees.infrastructure.models import (
    DelegationModel,
    EmployeeAbsenceModel,
    EmployeeAssignmentModel,
    EmployeeModel,
)
from app.modules.identity.infrastructure.models import UserAccountModel
from app.modules.organization.infrastructure.models import (
    OrganizationStructureVersionModel,
    StaffingSlotModel,
)
from app.modules.workflow.infrastructure.models import ProcessInstanceModel, WorkflowTaskModel
from app.modules.workflow.infrastructure.operations import SqlAlchemyWorkflowOperations
from app.shared.time import utc_now

from .models import (
    OffboardingTaskModel,
    OffboardingWaiverModel,
    TerminationCaseModel,
    TerminationReasonModel,
)


class SqlAlchemyTerminationOperations:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def require_case_organization(self, case_id: UUID, organization_id: UUID) -> None:
        async with self._sessions() as session:
            actual = await session.scalar(
                select(TerminationCaseModel.organization_id).where(
                    TerminationCaseModel.id == case_id
                )
            )
            if actual != organization_id:
                raise ResourceNotFoundError("termination case", case_id)

    async def employee_unit(self, organization_id: UUID, employee_id: UUID) -> UUID:
        async with self._sessions() as session:
            unit_id = await session.scalar(
                select(StaffingSlotModel.organization_unit_id)
                .join(
                    EmployeeAssignmentModel,
                    EmployeeAssignmentModel.staffing_slot_id == StaffingSlotModel.id,
                )
                .join(EmployeeModel, EmployeeModel.id == EmployeeAssignmentModel.employee_id)
                .where(
                    EmployeeAssignmentModel.employee_id == employee_id,
                    EmployeeModel.organization_id == organization_id,
                    EmployeeAssignmentModel.primary.is_(True),
                    EmployeeAssignmentModel.status.in_(("active", "scheduled_end")),
                )
                .order_by(EmployeeAssignmentModel.effective_from.desc())
            )
            if unit_id is None:
                raise ResourceNotFoundError("employee unit", employee_id)
            return unit_id

    async def require_task_organization(self, task_id: UUID, organization_id: UUID) -> None:
        async with self._sessions() as session:
            actual = await session.scalar(
                select(TerminationCaseModel.organization_id)
                .join(
                    OffboardingTaskModel,
                    OffboardingTaskModel.termination_case_id == TerminationCaseModel.id,
                )
                .where(OffboardingTaskModel.id == task_id)
            )
            if actual != organization_id:
                raise ResourceNotFoundError("offboarding task", task_id)

    async def task_type(self, task_id: UUID) -> str:
        async with self._sessions() as session:
            value = await session.scalar(
                select(OffboardingTaskModel.task_type).where(OffboardingTaskModel.id == task_id)
            )
            if value is None:
                raise ResourceNotFoundError("offboarding task", task_id)
            return value

    async def list_reasons(self, organization_id: UUID) -> Sequence[Mapping[str, object]]:
        async with self._sessions() as s:
            rows = (
                await s.scalars(
                    select(TerminationReasonModel)
                    .where(
                        TerminationReasonModel.organization_id == organization_id,
                        TerminationReasonModel.active.is_(True),
                    )
                    .order_by(TerminationReasonModel.name)
                )
            ).all()
            return [
                {
                    "id": row.id,
                    "code": row.code,
                    "name": row.name,
                    "legalReviewRequired": row.legal_review_required,
                }
                for row in rows
            ]

    async def list_cases(
        self,
        organization_id: UUID,
        offset: int,
        limit: int,
        employee_id: UUID | None = None,
        unit_id: UUID | None = None,
    ) -> tuple[Sequence[Mapping[str, object]], int]:
        async with self._sessions() as s:
            stmt = select(TerminationCaseModel).where(
                TerminationCaseModel.organization_id == organization_id
            )
            if employee_id is not None:
                stmt = stmt.where(TerminationCaseModel.employee_id == employee_id)
            if unit_id is not None:
                stmt = (
                    stmt.join(
                        EmployeeAssignmentModel,
                        EmployeeAssignmentModel.id == TerminationCaseModel.primary_assignment_id,
                    )
                    .join(
                        StaffingSlotModel,
                        StaffingSlotModel.id == EmployeeAssignmentModel.staffing_slot_id,
                    )
                    .where(StaffingSlotModel.organization_unit_id == unit_id)
                )
            rows = (
                await s.scalars(
                    stmt.order_by(TerminationCaseModel.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            total = int(await s.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
            pending_by_case: dict[UUID, list[str]] = {row.id: [] for row in rows}
            if rows:
                pending_tasks = (
                    await s.execute(
                        select(
                            OffboardingTaskModel.termination_case_id,
                            OffboardingTaskModel.task_type,
                        ).where(
                            OffboardingTaskModel.termination_case_id.in_(pending_by_case),
                            OffboardingTaskModel.status == "pending",
                        )
                    )
                ).all()
                for pending_case_id, task_type in pending_tasks:
                    pending_by_case[pending_case_id].append(task_type)
            return [
                {**_view(row), "pending_task_types": pending_by_case[row.id]}
                for row in rows
            ], total

    async def get_case(
        self,
        case_id: UUID,
        organization_id: UUID,
        employee_id: UUID | None = None,
        unit_id: UUID | None = None,
    ) -> Mapping[str, object]:
        rows, _ = await self.list_cases(
            organization_id, 0, 1, employee_id=employee_id, unit_id=unit_id
        )
        result = next((item for item in rows if item["id"] == case_id), None)
        if result is None:
            async with self._sessions() as session:
                stmt = select(TerminationCaseModel).where(
                    TerminationCaseModel.id == case_id,
                    TerminationCaseModel.organization_id == organization_id,
                )
                if employee_id is not None:
                    stmt = stmt.where(TerminationCaseModel.employee_id == employee_id)
                if unit_id is not None:
                    stmt = (
                        stmt.join(
                            EmployeeAssignmentModel,
                            EmployeeAssignmentModel.id
                            == TerminationCaseModel.primary_assignment_id,
                        )
                        .join(
                            StaffingSlotModel,
                            StaffingSlotModel.id == EmployeeAssignmentModel.staffing_slot_id,
                        )
                        .where(StaffingSlotModel.organization_unit_id == unit_id)
                    )
                row = await session.scalar(stmt)
                if row is None:
                    raise ResourceNotFoundError("termination case", case_id)
                pending_tasks = (
                    await session.scalars(
                        select(OffboardingTaskModel.task_type).where(
                            OffboardingTaskModel.termination_case_id == row.id,
                            OffboardingTaskModel.status == "pending",
                        )
                    )
                ).all()
                return {**_view(row), "pending_task_types": list(pending_tasks)}
        return result

    async def initiate(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as s:
            employee_id = _uuid(data, "employeeId")
            employee = await s.get(EmployeeModel, employee_id)
            reason = await s.get(TerminationReasonModel, _uuid(data, "reasonId"))
            if (
                employee is None
                or employee.organization_id != organization_id
                or not employee.active
                or employee.employment_status == "ended"
                or reason is None
                or reason.organization_id != organization_id
                or not reason.active
            ):
                raise ResourceNotFoundError("employee or termination reason")
            existing = await s.scalar(
                select(TerminationCaseModel.id).where(
                    TerminationCaseModel.employee_id == employee.id,
                    TerminationCaseModel.status.not_in(("rejected", "cancelled", "completed")),
                )
            )
            if existing is not None:
                raise ValidationError("Employee already has an active termination case.")
            legal_basis = str(data.get("legalBasis", "")).strip()
            if not legal_basis:
                raise ValidationError(
                    "Termination basis is required.", code=ErrorCode.TERMINATION_BASIS_REQUIRED
                )
            requested = _date(data["requestedDate"])
            if requested < date.today():
                raise ValidationError(
                    "Termination date cannot be in the past.",
                    code=ErrorCode.TERMINATION_DATE_INVALID,
                )
            assignment = await s.scalar(
                select(EmployeeAssignmentModel)
                .where(
                    EmployeeAssignmentModel.employee_id == employee.id,
                    EmployeeAssignmentModel.primary.is_(True),
                    EmployeeAssignmentModel.status.in_(("active", "planned", "scheduled_end")),
                )
                .order_by(EmployeeAssignmentModel.effective_from.desc())
                .with_for_update()
            )
            if assignment is None:
                raise ValidationError("Employee has no active primary assignment.")
            slot = await s.get(StaffingSlotModel, assignment.staffing_slot_id)
            version = (
                await s.get(OrganizationStructureVersionModel, slot.structure_version_id)
                if slot is not None
                else None
            )
            requested_unit = _optional_uuid(data.get("unitId"))
            if (
                slot is None
                or version is None
                or version.organization_id != organization_id
                or (requested_unit is not None and slot.organization_unit_id != requested_unit)
            ):
                raise ValidationError(
                    "Employee is outside the authorized unit.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            row = TerminationCaseModel(
                organization_id=organization_id,
                employee_id=employee.id,
                initiated_by_user_id=actor_id,
                initiated_by_employee_id=_optional_uuid(data.get("initiatedByEmployeeId")),
                reason_id=reason.id,
                legal_basis=legal_basis,
                requested_date=requested,
                status="hr_review",
                primary_assignment_id=assignment.id,
                secondary_assignment_plan=[],
            )
            s.add(row)
            await s.flush()
            process = await SqlAlchemyWorkflowOperations(self._sessions).start_linked_instance(
                s,
                organization_id,
                actor_id,
                {
                    "definitionCode": "termination",
                    "businessType": "terminationCase",
                    "businessEntityId": row.id,
                    "context": {
                        "subjectEmployeeId": str(employee.id),
                        "unitId": str(slot.organization_unit_id),
                        "legalReviewRequired": bool(reason.legal_review_required),
                    },
                },
            )
            row.process_instance_id = UUID(str(process["id"]))
            await self._change(
                s,
                actor_id,
                organization_id,
                "termination.case.started",
                row,
                EventName.TERMINATION_CASE_STARTED,
            )
            await s.flush()
            return _view(row)

    async def decide(
        self, case_id: UUID, actor_id: UUID, revision: int, stage: str, decision: str, comment: str
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as s:
            row = await _locked(s, TerminationCaseModel, case_id)
            workflow_key = f"termination:{row.id}:{stage}:{revision}:{decision}"
            workflow = SqlAlchemyWorkflowOperations(self._sessions)
            if await workflow.linked_action_exists(s, workflow_key):
                return _view(row)
            _rev(row, revision)
            before = _view(row)
            if row.status != stage:
                raise ValidationError("Termination case is not awaiting this review.")
            if decision in {"return", "reject"} and not comment.strip():
                raise ValidationError("A reason is required.")
            if decision == "return":
                row.status = "returned"
            elif decision == "reject":
                row.status = "rejected"
            elif stage == "hr_review":
                row.status = "economic_review"
            elif stage == "economic_review":
                row.status = "legal_review"
            elif stage == "legal_review":
                row.status = "signature"
            elif stage == "signature":
                row.status = "registration"
            else:
                raise ValidationError("Unsupported review stage.")
            row.revision += 1
            if row.process_instance_id is None:
                raise ValidationError("Termination case has no linked workflow.")
            workflow_action: str | None = decision
            expected_phase = "hr_review"
            if stage in {"economic_review", "legal_review"} and decision == "approve":
                workflow_action = None
            elif stage in {"economic_review", "legal_review", "signature"}:
                expected_phase = "signature_registration"
                if stage == "signature" and decision == "approve":
                    workflow_action = "complete"
            if workflow_action is not None:
                await workflow.act_linked_task(
                    s,
                    row.process_instance_id,
                    actor_id,
                    workflow_action,
                    comment,
                    workflow_key,
                    expected_phase=expected_phase,
                )
            await self._audit(
                s, actor_id, row.organization_id, "termination.case.reviewed", row, before, comment
            )
            if decision == "approve" and stage == "hr_review":
                await self._event(s, EventName.TERMINATION_CASE_APPROVED, row)
            return _view(row)

    async def resubmit(
        self, case_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as s:
            row = await _locked(s, TerminationCaseModel, case_id)
            _rev(row, revision)
            if (
                row.status != "returned"
                or row.initiated_by_user_id != actor_id
                or _uuid(data, "employeeId") != row.employee_id
            ):
                raise ValidationError(
                    "Only the initiator may correct a returned termination case.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            assignment = await s.get(EmployeeAssignmentModel, row.primary_assignment_id)
            slot = (
                await s.get(StaffingSlotModel, assignment.staffing_slot_id) if assignment else None
            )
            if slot is None or slot.organization_unit_id != _uuid(data, "unitId"):
                raise ValidationError(
                    "Termination case unit does not match the actual assignment.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            requested = _date(data["requestedDate"])
            if requested < date.today():
                raise ValidationError(
                    "Termination date cannot be in the past.",
                    code=ErrorCode.TERMINATION_DATE_INVALID,
                )
            legal_basis = str(data["legalBasis"]).strip()
            if not legal_basis:
                raise ValidationError(
                    "Termination basis is required.",
                    code=ErrorCode.TERMINATION_BASIS_REQUIRED,
                )
            before = _view(row)
            row.legal_basis = legal_basis
            row.requested_date = requested
            row.status = "hr_review"
            row.revision += 1
            if row.process_instance_id is None:
                raise ValidationError("Termination case has no linked workflow.")
            await SqlAlchemyWorkflowOperations(self._sessions).resume_linked_task(
                s,
                row.process_instance_id,
                actor_id,
                f"termination:{row.id}:resubmit:{revision}",
            )
            await self._audit(
                s,
                actor_id,
                row.organization_id,
                "termination.case.corrected",
                row,
                before,
            )
            return _view(row)

    async def register_order(
        self, case_id: UUID, actor_id: UUID, revision: int, document_id: UUID
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as s:
            row = await _locked(s, TerminationCaseModel, case_id)
            _rev(row, revision)
            doc = await s.get(DocumentRecordModel, document_id)
            if (
                row.status != "registration"
                or doc is None
                or doc.organization_id != row.organization_id
                or doc.status != "registered"
            ):
                raise ValidationError(
                    "A registered termination order is required.", code=ErrorCode.DOCUMENT_REQUIRED
                )
            row.order_document_id = doc.id
            row.status = "offboarding"
            row.revision += 1
            checklist = await s.scalar(
                select(DocumentChecklistItemModel).where(
                    DocumentChecklistItemModel.business_entity_type == "terminationCase",
                    DocumentChecklistItemModel.business_entity_id == row.id,
                    DocumentChecklistItemModel.document_type_id == doc.document_type_id,
                )
            )
            if checklist is None:
                s.add(
                    DocumentChecklistItemModel(
                        organization_id=row.organization_id,
                        process_instance_id=row.process_instance_id,
                        business_entity_type="terminationCase",
                        business_entity_id=row.id,
                        document_type_id=doc.document_type_id,
                        document_id=doc.id,
                        mandatory=True,
                        status="validated",
                        rejection_comment=None,
                    )
                )
            else:
                checklist.document_id = doc.id
                checklist.mandatory = True
                checklist.status = "validated"
                checklist.rejection_comment = None
                checklist.revision += 1
            existing_types = set(
                (
                    await s.scalars(
                        select(OffboardingTaskModel.task_type).where(
                            OffboardingTaskModel.termination_case_id == row.id
                        )
                    )
                ).all()
            )
            for task_type in (
                "handover",
                "asset_return",
                "access_revocation",
                "settlement",
                "exit_interview",
            ):
                if task_type in existing_types:
                    continue
                task = OffboardingTaskModel(
                    termination_case_id=row.id,
                    task_type=task_type,
                    status="pending",
                    evidence={},
                    restricted_notes=None,
                )
                s.add(task)
                await s.flush()
                await self._event(s, EventName.OFFBOARDING_TASK_ASSIGNED, task)
            await self._change(
                s,
                actor_id,
                row.organization_id,
                "termination.order.registered",
                row,
                EventName.TERMINATION_ORDER_REGISTERED,
            )
            return _view(row)

    async def create_tasks(
        self, case_id: UUID, actor_id: UUID, tasks: Sequence[Mapping[str, object]]
    ) -> Sequence[Mapping[str, object]]:
        async with self._sessions.begin() as s:
            case = await _locked(s, TerminationCaseModel, case_id)
            if case.status not in {"offboarding", "scheduled"}:
                raise ValidationError("Case is not in offboarding.")
            result = []
            existing_types = set(
                (
                    await s.scalars(
                        select(OffboardingTaskModel.task_type).where(
                            OffboardingTaskModel.termination_case_id == case.id
                        )
                    )
                ).all()
            )
            for item in tasks:
                if str(item["taskType"]) in existing_types:
                    continue
                row = OffboardingTaskModel(
                    termination_case_id=case.id,
                    task_type=str(item["taskType"]),
                    assigned_user_id=_optional_uuid(item.get("assignedUserId")),
                    assigned_employee_id=_optional_uuid(item.get("assignedEmployeeId")),
                    assigned_unit_id=_optional_uuid(item.get("assignedUnitId")),
                    status="pending",
                    due_at=cast(Any, item.get("dueAt")),
                    evidence={},
                    restricted_notes=None,
                )
                s.add(row)
                await s.flush()
                result.append(_view(row))
                await self._event(s, EventName.OFFBOARDING_TASK_ASSIGNED, row)
                existing_types.add(row.task_type)
            await self._audit(
                s, actor_id, case.organization_id, "termination.offboarding.tasks.created", case
            )
            return result

    async def list_tasks(self, case_id: UUID) -> Sequence[Mapping[str, object]]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(OffboardingTaskModel)
                    .where(OffboardingTaskModel.termination_case_id == case_id)
                    .order_by(OffboardingTaskModel.created_at, OffboardingTaskModel.task_type)
                )
            ).all()
            return [_view(row) for row in rows]

    async def complete_task(
        self, task_id: UUID, actor_id: UUID, revision: int, evidence: Mapping[str, object]
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as s:
            row = await _locked(s, OffboardingTaskModel, task_id)
            _rev(row, revision)
            if row.status == "completed":
                return _view(row)
            if row.status != "pending":
                raise ValidationError("Task cannot be completed.")
            row.status = "completed"
            row.completed_at = utc_now()
            row.evidence = dict(evidence)
            row.revision += 1
            case = await s.get(TerminationCaseModel, row.termination_case_id)
            if case is None:
                raise ResourceNotFoundError("termination case")
            await self._audit(
                s, actor_id, case.organization_id, "termination.offboarding.task.completed", row
            )
            return _view(row)

    async def waive_task(
        self, task_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> Mapping[str, object]:
        if not reason.strip():
            raise ValidationError("Waiver reason is required.")
        async with self._sessions.begin() as s:
            row = await _locked(s, OffboardingTaskModel, task_id)
            _rev(row, revision)
            if row.status != "pending":
                raise ValidationError("Only a pending task may be waived.")
            s.add(
                OffboardingWaiverModel(
                    offboarding_task_id=row.id,
                    authorized_by_user_id=actor_id,
                    reason=reason,
                    created_at=utc_now(),
                )
            )
            row.status = "waived"
            row.revision += 1
            case = await s.get(TerminationCaseModel, row.termination_case_id)
            if case is None:
                raise ResourceNotFoundError("termination case")
            await self._audit(
                s,
                actor_id,
                case.organization_id,
                "termination.offboarding.task.waived",
                row,
                reason=reason,
            )
            return _view(row)

    async def schedule(
        self,
        case_id: UUID,
        actor_id: UUID,
        revision: int,
        effective_date: object,
        secondary_plan: list[dict[str, object]],
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as s:
            row = await _locked(s, TerminationCaseModel, case_id)
            _rev(row, revision)
            effective = _date(effective_date)
            if row.status != "offboarding" or effective < date.today():
                raise ValidationError(
                    "Termination date is invalid.", code=ErrorCode.TERMINATION_DATE_INVALID
                )
            if row.primary_assignment_id is None:
                raise ValidationError("Primary assignment is required.")
            primary = await _locked(s, EmployeeAssignmentModel, row.primary_assignment_id)
            primary.effective_to = effective
            primary.status = "scheduled_end"
            primary.revision += 1
            secondaries = (
                await s.scalars(
                    select(EmployeeAssignmentModel)
                    .where(
                        EmployeeAssignmentModel.employee_id == row.employee_id,
                        EmployeeAssignmentModel.id != primary.id,
                        EmployeeAssignmentModel.status.in_(("active", "planned", "scheduled_end")),
                    )
                    .with_for_update()
                )
            ).all()
            plan = {UUID(str(x["assignmentId"])): x for x in secondary_plan}
            if {x.id for x in secondaries} != {*plan}:
                raise ValidationError("Every secondary assignment requires an explicit plan.")
            for assignment in secondaries:
                action = str(plan[assignment.id].get("action"))
                if action == "end":
                    assignment.effective_to = effective
                    assignment.status = "scheduled_end"
                    assignment.revision += 1
                elif action != "retain":
                    raise ValidationError("Secondary assignment action must be end or retain.")
            row.effective_date = effective
            row.secondary_assignment_plan = secondary_plan
            row.scheduled_at = utc_now()
            row.status = "scheduled"
            row.revision += 1
            if row.process_instance_id is None:
                raise ValidationError("Termination case has no linked workflow.")
            await SqlAlchemyWorkflowOperations(self._sessions).act_linked_task(
                s,
                row.process_instance_id,
                actor_id,
                "complete",
                "Termination completed.",
                f"termination:{row.id}:complete:{revision}",
                expected_phase="offboarding",
            )
            await self._change(
                s,
                actor_id,
                row.organization_id,
                "termination.scheduled",
                row,
                EventName.TERMINATION_SCHEDULED,
            )
            return _view(row)

    async def complete(self, case_id: UUID, actor_id: UUID, revision: int) -> Mapping[str, object]:
        async with self._sessions.begin() as s:
            row = await _locked(s, TerminationCaseModel, case_id)
            _rev(row, revision)
            if (
                row.status not in {"scheduled", "effective"}
                or row.effective_date is None
                or row.effective_date > date.today()
            ):
                raise ValidationError(
                    "Termination is not yet effective.", code=ErrorCode.TERMINATION_DATE_INVALID
                )
            pending = int(
                await s.scalar(
                    select(func.count())
                    .select_from(OffboardingTaskModel)
                    .where(
                        OffboardingTaskModel.termination_case_id == row.id,
                        OffboardingTaskModel.status == "pending",
                    )
                )
                or 0
            )
            task_types = set(
                (
                    await s.scalars(
                        select(OffboardingTaskModel.task_type).where(
                            OffboardingTaskModel.termination_case_id == row.id,
                            OffboardingTaskModel.status.in_(("completed", "waived")),
                        )
                    )
                ).all()
            )
            missing = int(
                await s.scalar(
                    select(func.count())
                    .select_from(DocumentChecklistItemModel)
                    .where(
                        DocumentChecklistItemModel.business_entity_type == "terminationCase",
                        DocumentChecklistItemModel.business_entity_id == row.id,
                        DocumentChecklistItemModel.organization_id == row.organization_id,
                        DocumentChecklistItemModel.mandatory.is_(True),
                        DocumentChecklistItemModel.status != "validated",
                    )
                )
                or 0
            )
            mandatory_documents = int(
                await s.scalar(
                    select(func.count())
                    .select_from(DocumentChecklistItemModel)
                    .where(
                        DocumentChecklistItemModel.business_entity_type == "terminationCase",
                        DocumentChecklistItemModel.business_entity_id == row.id,
                        DocumentChecklistItemModel.organization_id == row.organization_id,
                        DocumentChecklistItemModel.mandatory.is_(True),
                    )
                )
                or 0
            )
            required_tasks = {"handover", "asset_return", "access_revocation", "settlement"}
            if pending or missing or mandatory_documents == 0 or not required_tasks <= task_types:
                raise ValidationError(
                    "Termination tasks are incomplete.", code=ErrorCode.TERMINATION_TASKS_INCOMPLETE
                )
            employee = await _locked(s, EmployeeModel, row.employee_id)
            assignments = (
                await s.scalars(
                    select(EmployeeAssignmentModel)
                    .where(EmployeeAssignmentModel.employee_id == employee.id)
                    .with_for_update()
                )
            ).all()
            for assignment in assignments:
                if assignment.effective_to and assignment.effective_to <= row.effective_date:
                    assignment.status = "ended"
                    assignment.revision += 1
            # "ended" is the only terminal EmploymentStatus the employees domain
            # can hydrate; anything else breaks every read of this employee.
            employee.employment_status = "ended"
            employee.termination_date = row.effective_date
            employee.active = False
            employee.updated_at = utc_now()
            employee.revision += 1
            absences = (
                await s.scalars(
                    select(EmployeeAbsenceModel)
                    .where(
                        EmployeeAbsenceModel.employee_id == employee.id,
                        EmployeeAbsenceModel.status != "cancelled",
                        EmployeeAbsenceModel.date_from > row.effective_date,
                    )
                    .with_for_update()
                )
            ).all()
            for absence in absences:
                absence.status = "cancelled"
                absence.updated_at = utc_now()
                absence.revision += 1
            for request_model in (LeaveRequestModel, BusinessTripRequestModel):
                requests = (
                    await s.scalars(
                        select(request_model)
                        .where(
                            request_model.employee_id == employee.id,
                            request_model.end_date >= row.effective_date,
                            request_model.status.not_in(
                                ("cancelled", "rejected", "completed")
                            ),
                        )
                        .with_for_update()
                    )
                ).all()
                for loaded_request in requests:
                    request = cast(Any, loaded_request)
                    request.status = "cancelled"
                    request.cancelled_at = utc_now()
                    request.cancellation_reason = "Employment terminated"
                    request.revision += 1
                    await self._close_linked_instance(s, request, "cancelled")
            delegations = (
                await s.scalars(
                    select(DelegationModel)
                    .where(
                        (
                            (DelegationModel.delegator_employee_id == employee.id)
                            | (DelegationModel.delegate_employee_id == employee.id)
                        ),
                        DelegationModel.status.in_(("scheduled", "active")),
                    )
                    .with_for_update()
                )
            ).all()
            for delegation in delegations:
                delegation.status = "revoked"
                delegation.revoked_at = utc_now()
                delegation.revision += 1
            accounts = (
                await s.scalars(
                    select(UserAccountModel)
                    .where(
                        UserAccountModel.employee_id == employee.id,
                        UserAccountModel.active.is_(True),
                    )
                    .with_for_update()
                )
            ).all()
            for account in accounts:
                account.active = False
                account.status = "disabled"
                account.updated_at = utc_now()
                account.revision += 1
            row.status = "completed"
            row.effective_at = utc_now()
            row.completed_at = utc_now()
            row.revision += 1
            await self._close_linked_instance(s, row, "completed")
            await self._change(
                s,
                actor_id,
                row.organization_id,
                "termination.case.completed",
                row,
                EventName.EMPLOYEE_TERMINATION_EFFECTIVE,
            )
            await self._event(s, EventName.TERMINATION_CASE_COMPLETED, row)
            return _view(row)

    async def cancel(
        self, case_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> Mapping[str, object]:
        if not reason.strip():
            raise ValidationError("Cancellation reason is required.")
        async with self._sessions.begin() as s:
            row = await _locked(s, TerminationCaseModel, case_id)
            _rev(row, revision)
            if (
                row.effective_at
                or row.status in {"effective", "completed"}
                or (row.effective_date and row.effective_date <= date.today())
            ):
                raise ValidationError(
                    "Effective termination cannot be cancelled.",
                    code=ErrorCode.TERMINATION_CANCELLATION_NOT_ALLOWED,
                )
            assignments = (
                await s.scalars(
                    select(EmployeeAssignmentModel)
                    .where(
                        EmployeeAssignmentModel.employee_id == row.employee_id,
                        EmployeeAssignmentModel.status == "scheduled_end",
                    )
                    .with_for_update()
                )
            ).all()
            for assignment in assignments:
                assignment.effective_to = None
                assignment.status = (
                    "active" if assignment.effective_from <= date.today() else "planned"
                )
                assignment.revision += 1
            for task in (
                await s.scalars(
                    select(OffboardingTaskModel).where(
                        OffboardingTaskModel.termination_case_id == row.id,
                        OffboardingTaskModel.status == "pending",
                    )
                )
            ).all():
                task.status = "cancelled"
                task.revision += 1
            row.status = "cancelled"
            row.cancelled_at = utc_now()
            row.cancellation_reason = reason
            row.revision += 1
            if row.process_instance_id is None:
                raise ValidationError("Termination case has no linked workflow.")
            await SqlAlchemyWorkflowOperations(self._sessions).cancel_linked_instance(
                s, row.process_instance_id, actor_id, reason
            )
            await self._change(
                s,
                actor_id,
                row.organization_id,
                "termination.case.cancelled",
                row,
                EventName.TERMINATION_CASE_CANCELLED,
            )
            return _view(row)

    @staticmethod
    async def _close_linked_instance(
        s: AsyncSession, row: Any, status: str
    ) -> None:
        """Finish the linked workflow instance so it stops occupying task queues."""

        if row.process_instance_id is None:
            return
        instance = await s.get(ProcessInstanceModel, row.process_instance_id, with_for_update=True)
        if instance is None or instance.status in {"completed", "cancelled"}:
            return
        instance.status = status
        if status == "completed":
            instance.completed_at = utc_now()
        else:
            instance.cancelled_at = utc_now()
        instance.revision += 1
        open_tasks = (
            await s.scalars(
                select(WorkflowTaskModel).where(
                    WorkflowTaskModel.process_instance_id == instance.id,
                    WorkflowTaskModel.status.in_(("pending", "active")),
                )
            )
        ).all()
        for task in open_tasks:
            task.status = "cancelled"
            task.revision += 1

    async def _audit(
        self,
        s: AsyncSession,
        actor: UUID,
        org: UUID,
        action: str,
        row: Any,
        before: Mapping[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        await AuditService(SqlAlchemyAuditLog(s)).record(
            actor_id=actor,
            organization_id=org,
            action=action,
            entity_type=row.__tablename__,
            entity_id=row.id,
            before_state=before,
            after_state=_view(row),
            reason=reason,
        )

    async def _event(self, s: AsyncSession, name: EventName, row: Any) -> None:
        await SqlAlchemyTransactionalOutbox(s).append(
            ApplicationEvent(
                name=name,
                aggregate_type=row.__tablename__,
                aggregate_id=row.id,
                payload={"id": str(row.id)},
            )
        )

    async def _change(
        self, s: AsyncSession, actor: UUID, org: UUID, action: str, row: Any, event: EventName
    ) -> None:
        await self._audit(s, actor, org, action, row)
        await self._event(s, event, row)


def _view(row: Any) -> dict[str, Any]:
    return {
        c.key: getattr(row, c.key)
        for c in row.__table__.columns
        if c.key not in {"legal_basis", "restricted_notes", "evidence"}
    }


def _uuid(data: Mapping[str, object], key: str) -> UUID:
    return UUID(str(data[key]))


def _optional_uuid(value: object) -> UUID | None:
    return UUID(str(value)) if value else None


def _date(value: object) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _rev(row: Any, expected: int) -> None:
    if row.revision != expected:
        raise ConcurrencyConflictError()


async def _locked(s: AsyncSession, model: Any, row_id: UUID) -> Any:
    row = await s.scalar(select(model).where(model.id == row_id).with_for_update())
    if row is None:
        raise ResourceNotFoundError(model.__tablename__, row_id)
    return row
