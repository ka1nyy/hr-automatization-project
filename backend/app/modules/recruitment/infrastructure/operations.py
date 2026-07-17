from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.audit.service import AuditService
from app.core.errors import ConcurrencyConflictError, ResourceNotFoundError, ValidationError
from app.core.errors.codes import ErrorCode
from app.core.events.domain import ApplicationEvent, EventName
from app.core.events.repository import SqlAlchemyTransactionalOutbox
from app.modules.documents.infrastructure.models import (
    DocumentChecklistItemModel,
    DocumentRecordModel,
)
from app.modules.employees.infrastructure.crypto import FernetSensitiveDataProtector
from app.modules.employees.infrastructure.models import (
    EmployeeAssignmentModel,
    EmployeeModel,
    PersonModel,
)
from app.modules.identity.infrastructure.models import UserAccountModel
from app.modules.organization.infrastructure.models import (
    OrganizationStructureVersionModel,
    StaffingSlotModel,
)
from app.modules.workflow.infrastructure.operations import SqlAlchemyWorkflowOperations
from app.shared.time import utc_now

from ..application.ports import RecruitmentView
from ..domain.rules import require_candidate_consent, require_commission_quorum, require_vacant_slot
from .models import (
    CandidateApplicationModel,
    CandidateModel,
    CommissionDecisionModel,
    CommissionMemberModel,
    CommissionModel,
    HiringCaseModel,
    InterviewEvaluationModel,
    InterviewModel,
    InterviewParticipantModel,
    JobOfferModel,
    OnboardingTaskModel,
    PublicationChannelModel,
    RecruitmentRequestModel,
    ScreeningModel,
    StaffingReviewModel,
    VacancyModel,
    VacancyPublicationModel,
)


class SqlAlchemyRecruitmentOperations:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], protector: FernetSensitiveDataProtector
    ) -> None:
        self._sessions = sessions
        self._protector = protector

    async def require_organization(
        self, resource: str, resource_id: UUID, organization_id: UUID
    ) -> None:
        async with self._sessions() as session:
            if resource == "request":
                actual = await session.scalar(
                    select(RecruitmentRequestModel.organization_id).where(
                        RecruitmentRequestModel.id == resource_id
                    )
                )
            elif resource == "vacancy":
                actual = await session.scalar(
                    select(VacancyModel.organization_id).where(VacancyModel.id == resource_id)
                )
            elif resource == "application":
                actual = await session.scalar(
                    select(VacancyModel.organization_id)
                    .join(
                        CandidateApplicationModel,
                        CandidateApplicationModel.vacancy_id == VacancyModel.id,
                    )
                    .where(CandidateApplicationModel.id == resource_id)
                )
            elif resource == "interview":
                actual = await session.scalar(
                    select(VacancyModel.organization_id)
                    .join(
                        CandidateApplicationModel,
                        CandidateApplicationModel.vacancy_id == VacancyModel.id,
                    )
                    .join(
                        InterviewModel,
                        InterviewModel.application_id == CandidateApplicationModel.id,
                    )
                    .where(InterviewModel.id == resource_id)
                )
            elif resource == "offer":
                actual = await session.scalar(
                    select(VacancyModel.organization_id)
                    .join(
                        CandidateApplicationModel,
                        CandidateApplicationModel.vacancy_id == VacancyModel.id,
                    )
                    .join(
                        JobOfferModel, JobOfferModel.application_id == CandidateApplicationModel.id
                    )
                    .where(JobOfferModel.id == resource_id)
                )
            elif resource == "hiring":
                actual = await session.scalar(
                    select(HiringCaseModel.organization_id).where(HiringCaseModel.id == resource_id)
                )
            elif resource == "onboarding":
                actual = await session.scalar(
                    select(HiringCaseModel.organization_id)
                    .join(
                        OnboardingTaskModel,
                        OnboardingTaskModel.hiring_case_id == HiringCaseModel.id,
                    )
                    .where(OnboardingTaskModel.id == resource_id)
                )
            else:
                raise ResourceNotFoundError("recruitment resource")
            if actual != organization_id:
                raise ResourceNotFoundError(resource, resource_id)

    async def list_my_interviews(
        self, organization_id: UUID, user_id: UUID, offset: int, limit: int
    ) -> tuple[Sequence[RecruitmentView], int]:
        async with self._sessions() as session:
            employee_id = await session.scalar(
                select(UserAccountModel.employee_id).where(
                    UserAccountModel.id == user_id,
                    UserAccountModel.active.is_(True),
                )
            )
            if employee_id is None:
                return (), 0
            stmt = (
                select(InterviewModel)
                .join(
                    InterviewParticipantModel,
                    InterviewParticipantModel.interview_id == InterviewModel.id,
                )
                .join(
                    CandidateApplicationModel,
                    CandidateApplicationModel.id == InterviewModel.application_id,
                )
                .join(VacancyModel, VacancyModel.id == CandidateApplicationModel.vacancy_id)
                .where(
                    InterviewParticipantModel.employee_id == employee_id,
                    VacancyModel.organization_id == organization_id,
                )
            )
            rows = (
                await session.scalars(
                    stmt.order_by(InterviewModel.scheduled_at.desc()).offset(offset).limit(limit)
                )
            ).all()
            total = int(
                await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            )
            return [_view(row) for row in rows], total

    async def list_resources(
        self,
        resource: str,
        organization_id: UUID,
        offset: int,
        limit: int,
        unit_id: UUID | None = None,
    ) -> tuple[Sequence[RecruitmentView], int]:
        model = {
            "requests": RecruitmentRequestModel,
            "vacancies": VacancyModel,
            "candidates": CandidateModel,
            "applications": CandidateApplicationModel,
            "offers": JobOfferModel,
            "hiring-cases": HiringCaseModel,
        }.get(resource)
        if model is None:
            raise ResourceNotFoundError("recruitment resource")
        async with self._sessions() as session:
            stmt = select(model)
            if model in {
                RecruitmentRequestModel,
                VacancyModel,
                CandidateModel,
                HiringCaseModel,
            }:
                stmt = stmt.where(model.__table__.c.organization_id == organization_id)
            elif model is CandidateApplicationModel:
                stmt = stmt.join(
                    VacancyModel, VacancyModel.id == CandidateApplicationModel.vacancy_id
                ).where(VacancyModel.organization_id == organization_id)
            elif model is JobOfferModel:
                stmt = (
                    stmt.join(
                        CandidateApplicationModel,
                        CandidateApplicationModel.id == JobOfferModel.application_id,
                    )
                    .join(VacancyModel, VacancyModel.id == CandidateApplicationModel.vacancy_id)
                    .where(VacancyModel.organization_id == organization_id)
                )
            if unit_id is not None:
                if model is RecruitmentRequestModel:
                    stmt = stmt.where(RecruitmentRequestModel.requesting_unit_id == unit_id)
                elif model is VacancyModel:
                    stmt = stmt.join(
                        RecruitmentRequestModel,
                        RecruitmentRequestModel.id == VacancyModel.recruitment_request_id,
                    ).where(RecruitmentRequestModel.requesting_unit_id == unit_id)
                elif model is CandidateModel:
                    stmt = (
                        stmt.join(
                            CandidateApplicationModel,
                            CandidateApplicationModel.candidate_id == CandidateModel.id,
                        )
                        .join(VacancyModel, VacancyModel.id == CandidateApplicationModel.vacancy_id)
                        .join(
                            RecruitmentRequestModel,
                            RecruitmentRequestModel.id == VacancyModel.recruitment_request_id,
                        )
                        .where(RecruitmentRequestModel.requesting_unit_id == unit_id)
                        .distinct()
                    )
                elif model in {CandidateApplicationModel, JobOfferModel}:
                    stmt = stmt.join(
                        RecruitmentRequestModel,
                        RecruitmentRequestModel.id == VacancyModel.recruitment_request_id,
                    ).where(RecruitmentRequestModel.requesting_unit_id == unit_id)
                elif model is HiringCaseModel:
                    stmt = stmt.join(
                        RecruitmentRequestModel,
                        RecruitmentRequestModel.id == HiringCaseModel.recruitment_request_id,
                    ).where(RecruitmentRequestModel.requesting_unit_id == unit_id)
            rows = (
                await session.scalars(
                    stmt.order_by(model.__table__.c.id).offset(offset).limit(limit)
                )
            ).all()
            total = int(
                await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            )
            return [_view(row) for row in rows], total

    async def create_request(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            unit_id, position_id = (
                _uuid(data, "requestingUnitId"),
                _uuid(data, "positionDefinitionId"),
            )
            slot_id = _optional_uuid(data.get("staffingSlotId"))
            await self._validate_scope(session, organization_id, unit_id, position_id, slot_id)
            requested_by = _uuid(data, "requestedByEmployeeId")
            account = await session.get(UserAccountModel, actor_id)
            if account is None or account.employee_id != requested_by:
                raise ValidationError(
                    "The requester must be the authenticated employee.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            row = RecruitmentRequestModel(
                organization_id=organization_id,
                requesting_unit_id=unit_id,
                requested_by_employee_id=requested_by,
                staffing_slot_id=slot_id,
                position_definition_id=position_id,
                requested_fte=Decimal(str(data["requestedFte"])),
                employment_type=str(data["employmentType"]),
                desired_start_date=_date(data["desiredStartDate"]),
                reason=str(data["reason"]),
                responsibilities=str(data["responsibilities"]),
                requirements=str(data["requirements"]),
                proposed_compensation=cast(dict[str, Any] | None, data.get("proposedCompensation")),
                status="hr_review",
            )
            session.add(row)
            await session.flush()
            process = await SqlAlchemyWorkflowOperations(self._sessions).start_linked_instance(
                session,
                organization_id,
                actor_id,
                {
                    "definitionCode": "recruitment",
                    "businessType": "recruitmentRequest",
                    "businessEntityId": row.id,
                    "context": {
                        "subjectEmployeeId": str(requested_by),
                        "unitId": str(unit_id),
                        "requestingUnitId": str(unit_id),
                    },
                },
            )
            row.process_instance_id = UUID(str(process["id"]))
            await self._change(
                session,
                actor_id,
                organization_id,
                "recruitment.request.submitted",
                row,
                EventName.RECRUITMENT_REQUEST_SUBMITTED,
            )
            await session.flush()
            return _view(row)

    async def correct_request(
        self, request_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            row = await _locked(session, RecruitmentRequestModel, request_id)
            _revision(row, revision)
            account = await session.get(UserAccountModel, actor_id)
            if (
                row.status != "returned"
                or account is None
                or account.employee_id != row.requested_by_employee_id
                or _uuid(data, "requestingUnitId") != row.requesting_unit_id
            ):
                raise ValidationError(
                    "Only the requester may correct a returned request in its original unit.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            before = _view(row)
            row.desired_start_date = _date(data["desiredStartDate"])
            row.reason = str(data["reason"])
            row.responsibilities = str(data["responsibilities"])
            row.requirements = str(data["requirements"])
            row.status = "hr_review"
            row.revision += 1
            if row.process_instance_id is None:
                raise ValidationError("Recruitment request has no linked workflow.")
            await SqlAlchemyWorkflowOperations(self._sessions).resume_linked_task(
                session,
                row.process_instance_id,
                actor_id,
                f"recruitment:{row.id}:resubmit:{revision}",
            )
            await self._audit(
                session,
                actor_id,
                row.organization_id,
                "recruitment.request.corrected",
                row,
                before,
            )
            return _view(row)

    async def review_request(
        self,
        request_id: UUID,
        actor_id: UUID,
        revision: int,
        decision: str,
        comment: str,
        staffing: Mapping[str, object] | None = None,
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            row = await _locked(session, RecruitmentRequestModel, request_id)
            workflow_key = (
                f"recruitment:{row.id}:"
                f"{'staffing' if staffing is not None else 'hr'}:{revision}:{decision}"
            )
            workflow = SqlAlchemyWorkflowOperations(self._sessions)
            if await workflow.linked_action_exists(session, workflow_key):
                return _view(row)
            _revision(row, revision)
            before = _view(row)
            if staffing is None:
                if row.status not in {"hr_review", "returned"}:
                    raise ValidationError("Request is not awaiting HR review.")
                row.status = {
                    "approve": "staffing_review",
                    "return": "returned",
                    "reject": "rejected",
                }.get(decision, "")
            else:
                if row.status != "staffing_review":
                    raise ValidationError("Request is not awaiting staffing review.")
                slot = await self._slot(session, row.staffing_slot_id)
                approved = (
                    decision == "approve"
                    and bool(staffing.get("vacantSlotConfirmed"))
                    and bool(staffing.get("budgetConfirmed"))
                )
                if approved:
                    if slot is None:
                        raise ValidationError(
                            "A staffing slot is required.", code=ErrorCode.STAFFING_SLOT_REQUIRED
                        )
                    occupied = await self._occupied(session, slot.id)
                    require_vacant_slot(
                        slot_status=slot.status,
                        requested_fte=row.requested_fte,
                        slot_fte=slot.full_time_equivalent,
                        occupied_fte=occupied,
                    )
                session.add(
                    StaffingReviewModel(
                        recruitment_request_id=row.id,
                        reviewer_user_id=actor_id,
                        vacant_slot_confirmed=bool(staffing.get("vacantSlotConfirmed")),
                        approved_fte=Decimal(str(staffing["approvedFte"]))
                        if staffing.get("approvedFte")
                        else None,
                        budget_confirmed=bool(staffing.get("budgetConfirmed")),
                        compensation_range=cast(
                            dict[str, Any] | None, staffing.get("compensationRange")
                        ),
                        decision=decision,
                        comment=comment,
                        reviewed_at=utc_now(),
                    )
                )
                row.status = (
                    "approved" if approved else ("returned" if decision == "return" else "rejected")
                )
            if not row.status:
                raise ValidationError("Unsupported decision.")
            row.revision += 1
            if row.process_instance_id is None:
                raise ValidationError("Recruitment request has no linked workflow.")
            await workflow.act_linked_task(
                session,
                row.process_instance_id,
                actor_id,
                decision,
                comment,
                workflow_key,
                expected_phase="staffing_review" if staffing is not None else "hr_review",
            )
            await self._audit(
                session,
                actor_id,
                row.organization_id,
                "recruitment.request.reviewed",
                row,
                before,
                comment,
            )
            if row.status == "approved":
                await self._event(session, EventName.RECRUITMENT_REQUEST_APPROVED, row)
            return _view(row)

    async def create_vacancy(
        self, request_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            request = await _locked(session, RecruitmentRequestModel, request_id)
            if request.status != "approved" or request.staffing_slot_id is None:
                raise ValidationError(
                    "Request is not approvable.", code=ErrorCode.RECRUITMENT_REQUEST_NOT_APPROVABLE
                )
            slot = await self._slot(session, request.staffing_slot_id)
            if slot is None:
                raise ValidationError(
                    "A staffing slot is required.", code=ErrorCode.STAFFING_SLOT_REQUIRED
                )
            require_vacant_slot(
                slot_status=slot.status,
                requested_fte=request.requested_fte,
                slot_fte=slot.full_time_equivalent,
                occupied_fte=await self._occupied(session, slot.id),
            )
            row = VacancyModel(
                organization_id=request.organization_id,
                recruitment_request_id=request.id,
                staffing_slot_id=slot.id,
                code=str(data["code"]),
                title=str(data["title"]),
                description=str(data.get("description", "")),
                responsibilities=request.responsibilities,
                requirements=request.requirements,
                employment_conditions=cast(dict[str, Any], data.get("employmentConditions", {})),
                publication_status="draft",
                application_deadline=_optional_date(data.get("applicationDeadline")),
            )
            session.add(row)
            request.status = "vacancy_created"
            request.revision += 1
            await session.flush()
            await self._audit(
                session, actor_id, request.organization_id, "recruitment.vacancy.created", row
            )
            return _view(row)

    async def publish_vacancy(
        self, vacancy_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            row = await _locked(session, VacancyModel, vacancy_id)
            _revision(row, revision)
            channel = await session.get(PublicationChannelModel, _uuid(data, "channelId"))
            if (
                channel is None
                or channel.organization_id != row.organization_id
                or not channel.active
            ):
                raise ResourceNotFoundError("publication channel")
            responsible_employee_id = _uuid(data, "responsibleEmployeeId")
            responsible = await session.get(EmployeeModel, responsible_employee_id)
            if responsible is None or responsible.organization_id != row.organization_id:
                raise ResourceNotFoundError("responsible employee")
            now = utc_now()
            external = channel.channel_type != "internal"
            session.add(
                VacancyPublicationModel(
                    vacancy_id=row.id,
                    channel_id=channel.id,
                    status="published",
                    external_reference=cast(str | None, data.get("externalReference")),
                    published_at=now,
                    responsible_employee_id=responsible_employee_id,
                    manual=True,
                )
            )
            row.publication_status = "open_external" if external else "open_internal"
            row.revision += 1
            if external:
                row.external_published_at = now
            else:
                row.internal_published_at = now
            await self._change(
                session,
                actor_id,
                row.organization_id,
                "recruitment.vacancy.published",
                row,
                EventName.VACANCY_PUBLISHED,
            )
            return _view(row)

    async def create_candidate(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        require_candidate_consent(str(data.get("consentStatus", "")))
        async with self._sessions.begin() as session:

            def protect(value: object) -> str | None:
                return self._protector.protect(str(value)).decode("ascii") if value else None

            row = CandidateModel(
                organization_id=organization_id,
                first_name=str(data["firstName"]),
                last_name=str(data["lastName"]),
                middle_name=cast(str | None, data.get("middleName")),
                display_name=str(data["displayName"]),
                protected_personal_email=protect(data.get("personalEmail")),
                protected_phone=protect(data.get("phone")),
                protected_identity=protect(data.get("identity")),
                source=str(data["source"]),
                consent_status="granted",
                consent_at=utc_now(),
                retention_until=_optional_date(data.get("retentionUntil")),
                status="active",
            )
            session.add(row)
            await session.flush()
            await self._audit(
                session, actor_id, organization_id, "recruitment.candidate.created", row
            )
            return _view(row)

    async def anonymize_candidate(
        self, candidate_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> RecruitmentView:
        if not reason.strip():
            raise ValidationError("An anonymization reason is required.")
        async with self._sessions.begin() as session:
            row = await _locked(session, CandidateModel, candidate_id)
            _revision(row, revision)
            if row.retention_until is None or row.retention_until >= date.today():
                raise ValidationError("The candidate retention period has not expired.")
            active_applications = int(
                await session.scalar(
                    select(func.count())
                    .select_from(CandidateApplicationModel)
                    .where(
                        CandidateApplicationModel.candidate_id == row.id,
                        CandidateApplicationModel.status.not_in(
                            ("rejected", "withdrawn", "cancelled")
                        ),
                    )
                )
                or 0
            )
            if active_applications:
                raise ValidationError(
                    "A candidate with an active application cannot be anonymized."
                )
            row.first_name = "Anonymized"
            row.last_name = "Candidate"
            row.middle_name = None
            row.display_name = f"Anonymized candidate {str(row.id)[:8]}"
            row.protected_personal_email = None
            row.protected_phone = None
            row.protected_identity = None
            row.consent_status = "withdrawn"
            row.status = "anonymized"
            row.anonymized_at = utc_now()
            row.revision += 1
            await self._audit(
                session,
                actor_id,
                row.organization_id,
                "recruitment.candidate.anonymized",
                row,
                reason=reason.strip(),
            )
            await self._event(session, EventName.CANDIDATE_ANONYMIZED, row)
            return _view(row)

    async def create_publication_channel(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            row = PublicationChannelModel(
                organization_id=organization_id,
                code=str(data["code"]),
                name=str(data["name"]),
                channel_type=str(data["channelType"]),
                active=True,
            )
            session.add(row)
            await session.flush()
            await self._audit(
                session, actor_id, organization_id, "recruitment.channel.created", row
            )
            return _view(row)

    async def create_commission(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            members = cast(Sequence[Mapping[str, object]], data.get("members", ()))
            quorum = int(str(data["quorumRequired"]))
            if quorum < 1 or quorum > len(members):
                raise ValidationError("Commission quorum is invalid.")
            employee_ids = [_uuid(member, "employeeId") for member in members]
            valid_members = int(
                await session.scalar(
                    select(func.count())
                    .select_from(EmployeeModel)
                    .where(
                        EmployeeModel.id.in_(employee_ids),
                        EmployeeModel.organization_id == organization_id,
                        EmployeeModel.active.is_(True),
                    )
                )
                or 0
            )
            if valid_members != len(employee_ids) or len(employee_ids) != len(set(employee_ids)):
                raise ValidationError(
                    "Commission members must be unique active employees of the organization.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            protocol_document_id = _optional_uuid(data.get("protocolDocumentId"))
            if protocol_document_id:
                protocol = await session.get(DocumentRecordModel, protocol_document_id)
                if protocol is None or protocol.organization_id != organization_id:
                    raise ResourceNotFoundError("commission protocol document")
            row = CommissionModel(
                organization_id=organization_id,
                code=str(data["code"]),
                meeting_at=cast(Any, data["meetingAt"]),
                quorum_required=quorum,
                protocol_document_id=protocol_document_id,
                status="scheduled",
            )
            session.add(row)
            await session.flush()
            for member in members:
                session.add(
                    CommissionMemberModel(
                        commission_id=row.id,
                        employee_id=_uuid(member, "employeeId"),
                        role=str(member["role"]),
                        conflict_declared=bool(member.get("conflictDeclared", False)),
                        declaration=cast(str | None, member.get("declaration")),
                    )
                )
            await self._audit(
                session, actor_id, organization_id, "recruitment.commission.created", row
            )
            return _view(row)

    async def create_onboarding_task(
        self, case_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            case = await _locked(session, HiringCaseModel, case_id)
            if case.status in {"completed", "cancelled"}:
                raise ValidationError("Hiring case no longer accepts onboarding tasks.")
            assigned_employee_id = _optional_uuid(data.get("assignedEmployeeId"))
            if assigned_employee_id:
                employee = await session.get(EmployeeModel, assigned_employee_id)
                if employee is None or employee.organization_id != case.organization_id:
                    raise ResourceNotFoundError("assigned employee")
            row = OnboardingTaskModel(
                hiring_case_id=case.id,
                task_type=str(data["taskType"]),
                assigned_unit_id=_optional_uuid(data.get("assignedUnitId")),
                assigned_employee_id=assigned_employee_id,
                status="pending",
                due_at=cast(Any, data.get("dueAt")),
                completion_evidence={},
            )
            session.add(row)
            await session.flush()
            await self._audit(
                session, actor_id, case.organization_id, "recruitment.onboarding.task.created", row
            )
            return _view(row)

    async def complete_onboarding_task(
        self, task_id: UUID, actor_id: UUID, revision: int, evidence: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            row = await _locked(session, OnboardingTaskModel, task_id)
            _revision(row, revision)
            if row.status == "completed":
                return _view(row)
            if row.status != "pending":
                raise ValidationError("Onboarding task cannot be completed.")
            row.status = "completed"
            row.completed_at = utc_now()
            row.completion_evidence = dict(evidence)
            row.revision += 1
            case = await session.get(HiringCaseModel, row.hiring_case_id)
            if case is None:
                raise ResourceNotFoundError("hiring case")
            await self._audit(
                session,
                actor_id,
                case.organization_id,
                "recruitment.onboarding.task.completed",
                row,
            )
            return _view(row)

    async def create_application(
        self, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            vacancy = await session.get(VacancyModel, _uuid(data, "vacancyId"))
            candidate = await session.get(CandidateModel, _uuid(data, "candidateId"))
            if (
                vacancy is None
                or candidate is None
                or vacancy.organization_id != candidate.organization_id
            ):
                raise ResourceNotFoundError("vacancy or candidate")
            if vacancy.publication_status not in {"open_internal", "open_external"}:
                raise ValidationError("Vacancy is not open.", code=ErrorCode.VACANCY_NOT_OPEN)
            require_candidate_consent(candidate.consent_status)
            row = CandidateApplicationModel(
                candidate_id=candidate.id,
                vacancy_id=vacancy.id,
                status="received",
                current_stage="screening",
                source=str(data["source"]),
                applied_at=utc_now(),
            )
            session.add(row)
            await session.flush()
            await self._change(
                session,
                actor_id,
                vacancy.organization_id,
                "recruitment.application.received",
                row,
                EventName.CANDIDATE_APPLICATION_RECEIVED,
            )
            return _view(row)

    async def screen(
        self, application_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            app = await _locked(session, CandidateApplicationModel, application_id)
            _revision(app, revision)
            decision = str(data["decision"])
            comment = str(data.get("comment", "")).strip()
            if decision == "reject" and not comment:
                raise ValidationError("Rejection reason is required.")
            session.add(
                ScreeningModel(
                    application_id=app.id,
                    reviewer_user_id=actor_id,
                    criteria_results=cast(list[dict[str, Any]], data.get("criteriaResults", [])),
                    decision=decision,
                    comment=comment,
                    reviewed_at=utc_now(),
                )
            )
            app.status = "rejected" if decision == "reject" else "shortlisted"
            app.current_stage = "closed" if decision == "reject" else "interview"
            app.revision += 1
            await self._audit(
                session,
                actor_id,
                await self._application_org(session, app),
                "recruitment.application.screened",
                app,
                reason=comment,
            )
            return _view(app)

    async def schedule_interview(
        self, application_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            app = await _locked(session, CandidateApplicationModel, application_id)
            if app.status not in {"shortlisted", "interview"}:
                raise ValidationError(
                    "Application stage is invalid.", code=ErrorCode.APPLICATION_STAGE_INVALID
                )
            row = InterviewModel(
                application_id=app.id,
                round_number=int(str(data.get("roundNumber", 1))),
                scheduled_at=cast(Any, data["scheduledAt"]),
                format=str(data["format"]),
                location_reference=cast(str | None, data.get("locationReference")),
                status="scheduled",
                restricted_notes=None,
            )
            session.add(row)
            await session.flush()
            participants = cast(list[Mapping[str, object]], data.get("participants", []))
            participant_ids = [_uuid(item, "employeeId") for item in participants]
            organization_id = await self._application_org(session, app)
            valid_participants = int(
                await session.scalar(
                    select(func.count())
                    .select_from(EmployeeModel)
                    .where(
                        EmployeeModel.id.in_(participant_ids),
                        EmployeeModel.organization_id == organization_id,
                        EmployeeModel.active.is_(True),
                    )
                )
                or 0
            )
            if valid_participants != len(participant_ids) or len(participant_ids) != len(
                set(participant_ids)
            ):
                raise ValidationError(
                    "Interview participants must be unique active employees of the organization.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            for item in participants:
                session.add(
                    InterviewParticipantModel(
                        interview_id=row.id,
                        employee_id=_uuid(item, "employeeId"),
                        role=str(item["role"]),
                        required=bool(item.get("required", True)),
                    )
                )
            app.status = "interview"
            app.current_stage = "interview"
            app.revision += 1
            await self._change(
                session,
                actor_id,
                await self._application_org(session, app),
                "recruitment.interview.scheduled",
                row,
                EventName.INTERVIEW_SCHEDULED,
            )
            return _view(row)

    async def evaluate_interview(
        self, interview_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            employee_id = _uuid(data, "interviewerEmployeeId")
            account = await session.get(UserAccountModel, actor_id)
            if account is None or account.employee_id != employee_id:
                raise ValidationError(
                    "The authenticated user is not this interviewer.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            participant = await session.scalar(
                select(InterviewParticipantModel).where(
                    InterviewParticipantModel.interview_id == interview_id,
                    InterviewParticipantModel.employee_id == employee_id,
                )
            )
            if participant is None:
                raise ValidationError(
                    "Interviewer is not assigned to this interview.",
                    code=ErrorCode.AUTH_SCOPE_VIOLATION,
                )
            existing = await session.scalar(
                select(InterviewEvaluationModel).where(
                    InterviewEvaluationModel.interview_id == interview_id,
                    InterviewEvaluationModel.interviewer_employee_id == employee_id,
                )
            )
            if existing is not None:
                raise ValidationError(
                    "Evaluation is immutable.",
                    code=ErrorCode.INTERVIEW_EVALUATION_ALREADY_SUBMITTED,
                )
            row = InterviewEvaluationModel(
                interview_id=interview_id,
                interviewer_employee_id=employee_id,
                version_number=1,
                criteria_results=cast(list[dict[str, Any]], data.get("criteriaResults", [])),
                recommendation=str(data["recommendation"]),
                comment=str(data.get("comment", "")),
                submitted_at=utc_now(),
            )
            session.add(row)
            await session.flush()
            interview = await session.get(InterviewModel, interview_id)
            if interview is None:
                raise ResourceNotFoundError("interview", interview_id)
            app = await session.get(CandidateApplicationModel, interview.application_id)
            if app is None:
                raise ResourceNotFoundError("application")
            await self._audit(
                session,
                actor_id,
                await self._application_org(session, app),
                "recruitment.interview.evaluation.submitted",
                row,
            )
            return _view(row)

    async def record_commission_decision(
        self, application_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            commission = await session.get(CommissionModel, _uuid(data, "commissionId"))
            app = await _locked(session, CandidateApplicationModel, application_id)
            if commission is None:
                raise ResourceNotFoundError("commission")
            application_org = await self._application_org(session, app)
            if commission.organization_id != application_org:
                raise ResourceNotFoundError("commission")
            eligible = int(
                await session.scalar(
                    select(func.count())
                    .select_from(CommissionMemberModel)
                    .where(
                        CommissionMemberModel.commission_id == commission.id,
                        CommissionMemberModel.conflict_declared.is_(False),
                    )
                )
                or 0
            )
            require_commission_quorum(
                eligible_members=eligible, quorum_required=commission.quorum_required
            )
            decision = str(data["decision"])
            row = CommissionDecisionModel(
                commission_id=commission.id,
                application_id=app.id,
                decision=decision,
                comment=str(data.get("comment", "")),
                decided_at=utc_now(),
            )
            session.add(row)
            app.status = {
                "recommended": "selected",
                "reserve": "reserve",
                "rejected": "rejected",
            }.get(decision, "commission_review")
            app.current_stage = "offer" if app.status == "selected" else "commission_review"
            app.revision += 1
            await session.flush()
            await self._change(
                session,
                actor_id,
                commission.organization_id,
                "recruitment.commission.decision.recorded",
                row,
                EventName.COMMISSION_DECISION_RECORDED,
            )
            return _view(row)

    async def create_offer(
        self, application_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            app = await _locked(session, CandidateApplicationModel, application_id)
            if app.status != "selected":
                raise ValidationError(
                    "Only a selected candidate may receive an offer.",
                    code=ErrorCode.APPLICATION_STAGE_INVALID,
                )
            vacancy = await session.get(VacancyModel, app.vacancy_id)
            if vacancy is None:
                raise ResourceNotFoundError("vacancy")
            request = await session.get(RecruitmentRequestModel, vacancy.recruitment_request_id)
            if request is None:
                raise ResourceNotFoundError("recruitment request")
            row = JobOfferModel(
                application_id=app.id,
                position_definition_id=request.position_definition_id,
                staffing_slot_id=vacancy.staffing_slot_id,
                proposed_conditions=cast(dict[str, Any], data.get("proposedConditions", {})),
                proposed_start_date=_date(data["proposedStartDate"]),
                expiration_date=_date(data["expirationDate"]),
                status="sent",
                document_id=_optional_uuid(data.get("documentId")),
            )
            session.add(row)
            app.status = "offer_pending"
            app.current_stage = "offer"
            app.revision += 1
            await session.flush()
            await self._change(
                session,
                actor_id,
                vacancy.organization_id,
                "recruitment.offer.sent",
                row,
                EventName.JOB_OFFER_SENT,
            )
            return _view(row)

    async def respond_offer(
        self, offer_id: UUID, actor_id: UUID, revision: int, accepted: bool, reason: str | None
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            row = await _locked(session, JobOfferModel, offer_id)
            _revision(row, revision)
            if row.status != "sent":
                raise ValidationError("Offer is not awaiting response.")
            now = utc_now()
            row.status = "accepted" if accepted else "declined"
            row.accepted_at = now if accepted else None
            row.declined_at = None if accepted else now
            row.decline_reason = reason
            row.revision += 1
            app = await _locked(session, CandidateApplicationModel, row.application_id)
            app.status = "offer_accepted" if accepted else "offer_declined"
            app.revision += 1
            org = await self._application_org(session, app)
            await self._change(
                session,
                actor_id,
                org,
                "recruitment.offer.responded",
                row,
                EventName.JOB_OFFER_ACCEPTED if accepted else EventName.JOB_OFFER_DECLINED,
            )
            return _view(row)

    async def start_hiring(
        self, application_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            app = await _locked(session, CandidateApplicationModel, application_id)
            offer = await session.scalar(
                select(JobOfferModel).where(JobOfferModel.application_id == app.id)
            )
            if offer is None or offer.status != "accepted":
                raise ValidationError(
                    "An accepted offer is required.", code=ErrorCode.OFFER_NOT_ACCEPTED
                )
            vacancy = await session.get(VacancyModel, app.vacancy_id)
            if vacancy is None:
                raise ResourceNotFoundError("vacancy")
            row = HiringCaseModel(
                organization_id=vacancy.organization_id,
                candidate_application_id=app.id,
                recruitment_request_id=vacancy.recruitment_request_id,
                staffing_slot_id=offer.staffing_slot_id,
                proposed_start_date=offer.proposed_start_date,
                status="document_collection",
                created_at=utc_now(),
            )
            session.add(row)
            await session.flush()
            request = await session.get(RecruitmentRequestModel, row.recruitment_request_id)
            if request is None:
                raise ResourceNotFoundError("recruitment request")
            process = await SqlAlchemyWorkflowOperations(self._sessions).start_linked_instance(
                session,
                row.organization_id,
                actor_id,
                {
                    "definitionCode": "hiring",
                    "businessType": "hiringCase",
                    "businessEntityId": row.id,
                    "context": {"unitId": str(request.requesting_unit_id)},
                },
            )
            row.process_instance_id = UUID(str(process["id"]))
            await self._change(
                session,
                actor_id,
                row.organization_id,
                "recruitment.hiring.started",
                row,
                EventName.HIRING_CASE_STARTED,
            )
            await session.flush()
            return _view(row)

    async def complete_hiring(
        self, case_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            case = await _locked(session, HiringCaseModel, case_id)
            _revision(case, revision)
            mandatory = int(
                await session.scalar(
                    select(func.count())
                    .select_from(DocumentChecklistItemModel)
                    .where(
                        DocumentChecklistItemModel.business_entity_type == "hiringCase",
                        DocumentChecklistItemModel.business_entity_id == case.id,
                        DocumentChecklistItemModel.organization_id == case.organization_id,
                        DocumentChecklistItemModel.mandatory.is_(True),
                    )
                )
                or 0
            )
            missing = int(
                await session.scalar(
                    select(func.count())
                    .select_from(DocumentChecklistItemModel)
                    .where(
                        DocumentChecklistItemModel.business_entity_type == "hiringCase",
                        DocumentChecklistItemModel.business_entity_id == case.id,
                        DocumentChecklistItemModel.organization_id == case.organization_id,
                        DocumentChecklistItemModel.mandatory.is_(True),
                        DocumentChecklistItemModel.status != "validated",
                    )
                )
                or 0
            )
            incomplete_tasks = int(
                await session.scalar(
                    select(func.count())
                    .select_from(OnboardingTaskModel)
                    .where(
                        OnboardingTaskModel.hiring_case_id == case.id,
                        OnboardingTaskModel.status != "completed",
                    )
                )
                or 0
            )
            if not mandatory or missing or incomplete_tasks:
                raise ValidationError(
                    "Hiring documents are incomplete.", code=ErrorCode.HIRING_DOCUMENTS_INCOMPLETE
                )
            app = await session.get(CandidateApplicationModel, case.candidate_application_id)
            if app is None:
                raise ResourceNotFoundError("application")
            candidate = await session.get(CandidateModel, app.candidate_id)
            if candidate is None:
                raise ResourceNotFoundError("candidate")
            if case.employee_id is not None:
                return _view(case)
            employee_number = str(data["employeeNumber"])
            if await session.scalar(
                select(EmployeeModel.id).where(
                    EmployeeModel.organization_id == case.organization_id,
                    EmployeeModel.employee_number == employee_number,
                )
            ):
                raise ValidationError(
                    "Employee already exists.", code=ErrorCode.EMPLOYEE_ALREADY_EXISTS
                )
            slot = await self._slot(session, case.staffing_slot_id)
            if slot is None:
                raise ResourceNotFoundError("staffing slot")
            fte = Decimal(str(data.get("fullTimeEquivalent", "1.0")))
            require_vacant_slot(
                slot_status=slot.status,
                requested_fte=fte,
                slot_fte=slot.full_time_equivalent,
                occupied_fte=await self._occupied(session, slot.id),
            )
            now = utc_now()
            person = PersonModel(
                id=uuid4(),
                first_name=candidate.first_name,
                last_name=candidate.last_name,
                middle_name=candidate.middle_name,
                display_name=candidate.display_name,
                protected_iin=None,
                birth_date=None,
                personal_email=None,
                phone=None,
                status="active",
                created_at=now,
                updated_at=now,
                revision=1,
            )
            employee = EmployeeModel(
                id=uuid4(),
                organization_id=case.organization_id,
                created_by=actor_id,
                person_id=person.id,
                employee_number=employee_number,
                employment_status="active",
                hire_date=case.proposed_start_date,
                termination_date=None,
                corporate_email=cast(str | None, data.get("corporateEmail")),
                active=True,
                created_at=now,
                updated_at=now,
                revision=1,
            )
            assignment = EmployeeAssignmentModel(
                id=uuid4(),
                employee_id=employee.id,
                staffing_slot_id=slot.id,
                assignment_type="primary",
                full_time_equivalent=fte,
                effective_from=case.proposed_start_date,
                effective_to=None,
                primary=True,
                acting=False,
                status="planned" if case.proposed_start_date > date.today() else "active",
                source_document_id=_optional_uuid(data.get("sourceDocumentId")),
                created_at=now,
                updated_at=now,
                revision=1,
            )
            session.add(person)
            await session.flush()
            session.add(employee)
            await session.flush()
            session.add(assignment)
            await session.flush()
            case.person_id = person.id
            case.employee_id = employee.id
            case.assignment_id = assignment.id
            case.status = "completed"
            case.completed_at = now
            case.revision += 1
            app.status = "hired"
            app.current_stage = "completed"
            app.revision += 1
            vacancy = await _locked(session, VacancyModel, app.vacancy_id)
            vacancy.publication_status = "filled"
            vacancy.closed_at = now
            vacancy.revision += 1
            request = await _locked(
                session, RecruitmentRequestModel, vacancy.recruitment_request_id
            )
            request.status = "completed"
            request.revision += 1
            if case.process_instance_id is None:
                raise ValidationError("Hiring case has no linked workflow.")
            await SqlAlchemyWorkflowOperations(self._sessions).complete_linked_instance(
                session,
                case.process_instance_id,
                actor_id,
                "Hiring completed after document and onboarding validation.",
            )
            for task in (
                await session.scalars(
                    select(OnboardingTaskModel).where(
                        OnboardingTaskModel.hiring_case_id == case.id,
                        OnboardingTaskModel.status != "completed",
                    )
                )
            ).all():
                task.status = "cancelled"
                task.revision += 1
            await self._change(
                session,
                actor_id,
                case.organization_id,
                "recruitment.employee.hired",
                case,
                EventName.EMPLOYEE_HIRED,
            )
            return _view(case)

    async def cancel_hiring(
        self, case_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> RecruitmentView:
        async with self._sessions.begin() as session:
            row = await _locked(session, HiringCaseModel, case_id)
            _revision(row, revision)
            if row.status == "completed":
                raise ValidationError("Completed hiring cannot be cancelled.")
            row.status = "cancelled"
            row.revision += 1
            if row.process_instance_id is None:
                raise ValidationError("Hiring case has no linked workflow.")
            await SqlAlchemyWorkflowOperations(self._sessions).cancel_linked_instance(
                session, row.process_instance_id, actor_id, reason
            )
            for task in (
                await session.scalars(
                    select(OnboardingTaskModel).where(
                        OnboardingTaskModel.hiring_case_id == row.id,
                        OnboardingTaskModel.status != "completed",
                    )
                )
            ).all():
                task.status = "cancelled"
                task.revision += 1
            app = await _locked(session, CandidateApplicationModel, row.candidate_application_id)
            app.status = "hiring_cancelled"
            app.current_stage = "closed"
            app.revision += 1
            vacancy = await _locked(session, VacancyModel, app.vacancy_id)
            vacancy.publication_status = (
                "open_external" if vacancy.external_published_at else "open_internal"
            )
            vacancy.closed_at = None
            vacancy.revision += 1
            request = await _locked(
                session, RecruitmentRequestModel, vacancy.recruitment_request_id
            )
            request.status = "vacancy_created"
            request.revision += 1
            await self._change(
                session,
                actor_id,
                row.organization_id,
                "recruitment.hiring.cancelled",
                row,
                EventName.HIRING_CASE_CANCELLED,
            )
            await self._audit(
                session,
                actor_id,
                row.organization_id,
                "recruitment.hiring.cancellation.reason",
                row,
                reason=reason,
            )
            return _view(row)

    async def _validate_scope(
        self,
        session: AsyncSession,
        organization_id: UUID,
        unit_id: UUID,
        position_id: UUID,
        slot_id: UUID | None,
    ) -> None:
        from app.modules.organization.infrastructure.models import (
            OrganizationUnitModel,
            PositionDefinitionModel,
        )

        unit = await session.get(OrganizationUnitModel, unit_id)
        position = await session.get(PositionDefinitionModel, position_id)
        version = (
            await session.get(OrganizationStructureVersionModel, unit.structure_version_id)
            if unit
            else None
        )
        if (
            unit is None
            or version is None
            or version.organization_id != organization_id
            or position is None
            or position.organization_id != organization_id
        ):
            raise ValidationError(
                "Unit and position must belong to the organization.",
                code=ErrorCode.AUTH_SCOPE_VIOLATION,
            )
        if slot_id:
            slot = await session.get(StaffingSlotModel, slot_id)
            if (
                slot is None
                or slot.organization_unit_id != unit_id
                or slot.position_definition_id != position_id
            ):
                raise ValidationError(
                    "Staffing slot is incompatible.", code=ErrorCode.STAFFING_SLOT_NOT_VACANT
                )

    async def _slot(self, session: AsyncSession, slot_id: UUID | None) -> StaffingSlotModel | None:
        return await session.get(StaffingSlotModel, slot_id) if slot_id else None

    async def _occupied(self, session: AsyncSession, slot_id: UUID) -> Decimal:
        return Decimal(
            await session.scalar(
                select(
                    func.coalesce(func.sum(EmployeeAssignmentModel.full_time_equivalent), 0)
                ).where(
                    EmployeeAssignmentModel.staffing_slot_id == slot_id,
                    EmployeeAssignmentModel.status.in_(("planned", "active", "scheduled_end")),
                )
            )
            or 0
        )

    async def _application_org(self, session: AsyncSession, app: CandidateApplicationModel) -> UUID:
        vacancy = await session.get(VacancyModel, app.vacancy_id)
        if vacancy is None:
            raise ResourceNotFoundError("vacancy")
        return vacancy.organization_id

    async def _audit(
        self,
        session: AsyncSession,
        actor: UUID,
        org: UUID,
        action: str,
        row: Any,
        before: Mapping[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        await AuditService(SqlAlchemyAuditLog(session)).record(
            actor_id=actor,
            organization_id=org,
            action=action,
            entity_type=row.__tablename__,
            entity_id=row.id,
            before_state=before,
            after_state=_audit_view(row),
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
        self, session: AsyncSession, actor: UUID, org: UUID, action: str, row: Any, event: EventName
    ) -> None:
        await self._audit(session, actor, org, action, row)
        await self._event(session, event, row)


def _view(row: Any) -> dict[str, Any]:
    blocked = {
        "protected_personal_email",
        "protected_phone",
        "protected_identity",
        "proposed_compensation",
        "compensation_range",
        "restricted_notes",
    }
    return {
        column.key: getattr(row, column.key)
        for column in row.__table__.columns
        if column.key not in blocked
    }


def _audit_view(row: Any) -> dict[str, Any]:
    result = _view(row)
    for field in ("completion_evidence", "criteria_results"):
        if field in result:
            result[field] = "[redacted]"
    return result


def _uuid(data: Mapping[str, object], key: str) -> UUID:
    return UUID(str(data[key]))


def _optional_uuid(value: object) -> UUID | None:
    return UUID(str(value)) if value else None


def _date(value: object) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _optional_date(value: object) -> date | None:
    return _date(value) if value else None


def _revision(row: Any, expected: int) -> None:
    if row.revision != expected:
        raise ConcurrencyConflictError()


async def _locked(session: AsyncSession, model: Any, row_id: UUID) -> Any:
    row = await session.scalar(select(model).where(model.id == row_id).with_for_update())
    if row is None:
        raise ResourceNotFoundError(model.__tablename__, row_id)
    return row
