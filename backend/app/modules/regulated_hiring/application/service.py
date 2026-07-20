from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit.models import AuditEventModel
from app.core.errors import ConflictError, ForbiddenError, ResourceNotFoundError, ValidationError
from app.core.events.models import OutboxEventModel
from app.core.security.identity import Principal
from app.modules.organization.infrastructure.models import StaffingSlotModel
from app.modules.recruitment.infrastructure.models import RecruitmentRequestModel
from app.shared.identifiers import new_uuid
from app.shared.time import utc_now

from ..domain.catalog import FORM_POLICIES, STAGE_POLICIES, FormPolicy, StagePolicy
from ..domain.enums import CaseStatus, FormStatus, StageStatus
from ..domain.rules import require_confirmed_authority, validate_stage_evidence
from ..infrastructure.models import (
    AuthorityBindingModel,
    HiringFormDefinitionModel,
    HiringFormRecordModel,
    HiringProcessCaseModel,
    HiringStageActionModel,
    HiringStageDefinitionModel,
    HiringStageExecutionModel,
    NormativeSourceModel,
)


class RegulatedHiringService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def stage_catalog() -> list[dict[str, Any]]:
        return [
            {
                "sequence": item.sequence,
                "code": item.code.value,
                "name": item.name,
                "ownerRoleCode": item.owner_role_code,
                "slaMinDays": item.sla_min_days,
                "slaMaxDays": item.sla_max_days,
                "workingDays": item.working_days,
            }
            for item in STAGE_POLICIES
        ]

    @staticmethod
    def form_catalog() -> list[dict[str, Any]]:
        return [
            {
                "sequence": item.sequence,
                "code": item.code,
                "name": item.name,
                "ownerRoleCode": item.owner_role_code,
                "signerRoleCodes": list(item.signer_role_codes),
            }
            for item in FORM_POLICIES
        ]

    async def start_case(
        self,
        principal: Principal,
        *,
        organization_id: UUID,
        recruitment_request_id: UUID,
        staffing_slot_id: UUID,
        business_key: str,
        process_engine: str,
        camunda_process_instance_key: str | None,
    ) -> dict[str, Any]:
        now = utc_now()
        async with self._session_factory() as session, session.begin():
            request = await session.get(RecruitmentRequestModel, recruitment_request_id)
            if request is None or request.organization_id != organization_id:
                raise ResourceNotFoundError("recruitment request", recruitment_request_id)
            if request.staffing_slot_id != staffing_slot_id:
                raise ValidationError("The staffing slot does not match the recruitment request.")
            if request.status not in {"approved", "vacancy_created"}:
                raise ConflictError(
                    "A regulated hiring case requires an approved recruitment request.",
                    details={"status": request.status},
                )
            await self._require_confirmed_binding(
                session, organization_id, "staffing_slot", staffing_slot_id, date.today()
            )
            existing = await session.scalar(
                select(HiringProcessCaseModel).where(
                    HiringProcessCaseModel.organization_id == organization_id,
                    HiringProcessCaseModel.business_key == business_key,
                )
            )
            if existing is not None:
                return self._case_view(existing)

            first_policy = STAGE_POLICIES[0]
            definition = await self._stage_definition(session, organization_id, first_policy)
            case = HiringProcessCaseModel(
                id=new_uuid(),
                organization_id=organization_id,
                recruitment_request_id=recruitment_request_id,
                staffing_slot_id=staffing_slot_id,
                candidate_application_id=None,
                business_key=business_key,
                status=CaseStatus.ACTIVE,
                current_stage_code=first_policy.code,
                current_stage_sequence=first_policy.sequence,
                process_engine=process_engine,
                camunda_process_instance_key=camunda_process_instance_key,
                initiated_by_user_id=principal.user_id,
                started_at=now,
                completed_at=None,
                cancelled_at=None,
                terminal_reason=None,
            )
            execution = self._new_execution(case.id, definition.id, first_policy, now, 1)
            session.add_all([case, execution])
            self._record_change(
                session,
                organization_id=organization_id,
                actor_id=principal.user_id,
                case_id=case.id,
                action="regulated_hiring.started",
                safe_state={"businessKey": business_key, "stage": first_policy.code.value},
            )
            await session.flush()
            return self._case_view(case)

    async def act_on_stage(
        self,
        principal: Principal,
        *,
        case_id: UUID,
        organization_id: UUID,
        expected_revision: int,
        action: str,
        idempotency_key: str,
        reason: str | None,
        evidence: Mapping[str, Any],
        return_to_sequence: int | None,
    ) -> dict[str, Any]:
        now = utc_now()
        async with self._session_factory() as session, session.begin():
            duplicate = await session.scalar(
                select(HiringStageActionModel).where(
                    HiringStageActionModel.idempotency_key == idempotency_key
                )
            )
            if duplicate is not None:
                existing_case = await session.get(HiringProcessCaseModel, duplicate.case_id)
                if existing_case is None:
                    raise ResourceNotFoundError("regulated hiring case", duplicate.case_id)
                return self._case_view(existing_case)

            case = await session.scalar(
                select(HiringProcessCaseModel)
                .where(HiringProcessCaseModel.id == case_id)
                .with_for_update()
            )
            if case is None or case.organization_id != organization_id:
                raise ResourceNotFoundError("regulated hiring case", case_id)
            if case.revision != expected_revision:
                raise ConflictError(
                    "The regulated hiring case was changed by another operation.",
                    details={
                        "expectedRevision": expected_revision,
                        "actualRevision": case.revision,
                    },
                )
            if case.status not in {CaseStatus.ACTIVE, CaseStatus.RETURNED}:
                raise ConflictError("The regulated hiring case is already terminal.")

            policy = STAGE_POLICIES[case.current_stage_sequence]
            self._require_stage_actor(principal, policy)
            execution = await session.scalar(
                select(HiringStageExecutionModel)
                .where(
                    HiringStageExecutionModel.case_id == case.id,
                    HiringStageExecutionModel.status == StageStatus.ACTIVE,
                )
                .with_for_update()
            )
            if execution is None:
                raise ConflictError("The regulated hiring case has no active stage.")
            if action in {"return", "reject", "cancel"} and not (reason or "").strip():
                raise ValidationError(f"A reason is required for {action}.")

            if action in {"approve", "complete"}:
                if policy.code.value == "unit_check":
                    slot = await session.get(StaffingSlotModel, case.staffing_slot_id)
                    if slot is None or slot.status != "vacant":
                        raise ConflictError(
                            "The staffing slot is not vacant and cannot proceed to selection.",
                            details={"staffingSlotId": str(case.staffing_slot_id)},
                        )
                    await self._require_confirmed_binding(
                        session,
                        organization_id,
                        "staffing_slot",
                        case.staffing_slot_id,
                        date.today(),
                    )
                validate_stage_evidence(policy.code, evidence)
                execution.status = StageStatus.COMPLETED
                execution.decision = action
                execution.completed_at = now
                execution.evidence = dict(evidence)
                if policy.sequence == len(STAGE_POLICIES) - 1:
                    case.status = CaseStatus.COMPLETED
                    case.completed_at = now
                else:
                    next_policy = STAGE_POLICIES[policy.sequence + 1]
                    definition = await self._stage_definition(session, organization_id, next_policy)
                    case.status = CaseStatus.ACTIVE
                    case.current_stage_sequence = next_policy.sequence
                    case.current_stage_code = next_policy.code
                    session.add(self._new_execution(case.id, definition.id, next_policy, now, 1))
            elif action == "return":
                if return_to_sequence is None or return_to_sequence >= policy.sequence:
                    raise ValidationError("Return target must be an earlier stage.")
                target = STAGE_POLICIES[return_to_sequence]
                execution.status = StageStatus.RETURNED
                execution.decision = action
                execution.decision_comment = reason
                execution.completed_at = now
                cycle = (
                    await session.scalar(
                        select(func.count(HiringStageExecutionModel.id)).where(
                            HiringStageExecutionModel.case_id == case.id,
                            HiringStageExecutionModel.stage_code == target.code,
                        )
                    )
                    or 0
                ) + 1
                definition = await self._stage_definition(session, organization_id, target)
                case.status = CaseStatus.RETURNED
                case.current_stage_sequence = target.sequence
                case.current_stage_code = target.code
                session.add(self._new_execution(case.id, definition.id, target, now, cycle))
            else:
                terminal = CaseStatus.REJECTED if action == "reject" else CaseStatus.CANCELLED
                execution.status = (
                    StageStatus.REJECTED if action == "reject" else StageStatus.CANCELLED
                )
                execution.decision = action
                execution.decision_comment = reason
                execution.completed_at = now
                case.status = terminal
                case.terminal_reason = reason
                case.cancelled_at = now if terminal == CaseStatus.CANCELLED else None

            session.add(
                HiringStageActionModel(
                    id=new_uuid(),
                    case_id=case.id,
                    stage_execution_id=execution.id,
                    actor_user_id=principal.user_id,
                    action=action,
                    reason=reason,
                    safe_metadata={"stage": policy.code.value},
                    idempotency_key=idempotency_key,
                    occurred_at=now,
                )
            )
            self._record_change(
                session,
                organization_id=organization_id,
                actor_id=principal.user_id,
                case_id=case.id,
                action=f"regulated_hiring.{action}",
                safe_state={"stage": policy.code.value, "status": str(case.status)},
                reason=reason,
            )
            await session.flush()
            return self._case_view(case)

    async def record_form(
        self,
        principal: Principal,
        *,
        case_id: UUID,
        organization_id: UUID,
        form_code: str,
        data: Mapping[str, Any],
        signed: bool,
        signers: list[dict[str, Any]],
        correction_reason: str | None,
        document_id: UUID | None,
    ) -> dict[str, Any]:
        policy = next((item for item in FORM_POLICIES if item.code == form_code), None)
        if policy is None:
            raise ResourceNotFoundError("regulated hiring form", form_code)
        now = utc_now()
        async with self._session_factory() as session, session.begin():
            case = await session.get(HiringProcessCaseModel, case_id)
            if case is None or case.organization_id != organization_id:
                raise ResourceNotFoundError("regulated hiring case", case_id)
            if (
                "system-administrator" not in principal.role_codes
                and policy.owner_role_code not in principal.role_codes
            ):
                raise ForbiddenError(
                    "The actor does not own this regulated hiring form.",
                    details={"requiredRole": policy.owner_role_code},
                )
            definition = await self._form_definition(session, organization_id, policy)
            previous = await session.scalar(
                select(HiringFormRecordModel)
                .where(
                    HiringFormRecordModel.case_id == case_id,
                    HiringFormRecordModel.form_definition_id == definition.id,
                )
                .order_by(HiringFormRecordModel.record_version.desc())
                .limit(1)
                .with_for_update()
            )
            if previous is not None and previous.status == FormStatus.SIGNED:
                if not (correction_reason or "").strip():
                    raise ValidationError("Correction of a signed form requires a reason.")
                previous.status = FormStatus.SUPERSEDED
            if signed:
                supplied_roles = {str(item.get("roleCode")) for item in signers}
                missing_roles = sorted(set(policy.signer_role_codes) - supplied_roles)
                if missing_roles:
                    raise ValidationError(
                        "The form does not contain all required signatures.",
                        details={"missingSignerRoles": missing_roles},
                    )
            record = HiringFormRecordModel(
                id=new_uuid(),
                case_id=case_id,
                form_definition_id=definition.id,
                record_version=1 if previous is None else previous.record_version + 1,
                status=FormStatus.SIGNED if signed else FormStatus.DRAFT,
                data=dict(data),
                created_by_user_id=principal.user_id,
                signed_by=signers,
                signed_at=now if signed else None,
                document_id=document_id,
                supersedes_record_id=previous.id if previous is not None else None,
                correction_reason=correction_reason,
            )
            session.add(record)
            self._record_change(
                session,
                organization_id=organization_id,
                actor_id=principal.user_id,
                case_id=case_id,
                action="regulated_hiring.form_recorded",
                safe_state={
                    "formCode": form_code,
                    "recordVersion": record.record_version,
                    "signed": signed,
                },
                reason=correction_reason,
            )
            await session.flush()
            return {
                "id": str(record.id),
                "caseId": str(case_id),
                "formCode": form_code,
                "recordVersion": record.record_version,
                "status": str(record.status),
            }

    async def timeline(self, case_id: UUID, organization_id: UUID) -> dict[str, Any]:
        async with self._session_factory() as session:
            case = await session.get(HiringProcessCaseModel, case_id)
            if case is None or case.organization_id != organization_id:
                raise ResourceNotFoundError("regulated hiring case", case_id)
            executions = (
                await session.scalars(
                    select(HiringStageExecutionModel)
                    .where(HiringStageExecutionModel.case_id == case_id)
                    .order_by(HiringStageExecutionModel.created_at, HiringStageExecutionModel.cycle)
                )
            ).all()
            return {
                **self._case_view(case),
                "stages": [
                    {
                        "id": str(item.id),
                        "stageCode": item.stage_code,
                        "stageSequence": item.stage_sequence,
                        "cycle": item.cycle,
                        "status": item.status,
                        "dueAt": item.due_at,
                        "decision": item.decision,
                        "completedAt": item.completed_at,
                    }
                    for item in executions
                ],
            }

    async def create_authority_binding(
        self,
        principal: Principal,
        *,
        organization_id: UUID,
        entity_type: str,
        entity_id: UUID,
        authority_status: str,
        source_id: UUID | None,
        assertion: str,
        effective_from: date,
        effective_to: date | None,
        granted_permissions: list[str],
    ) -> dict[str, Any]:
        if effective_to is not None and effective_to < effective_from:
            raise ValidationError("Authority end date cannot precede its start date.")
        async with self._session_factory() as session, session.begin():
            source = await session.get(NormativeSourceModel, source_id) if source_id else None
            if authority_status == "confirmed":
                if source is None or source.organization_id != organization_id:
                    raise ValidationError("Confirmed authority requires a registered source.")
                if source.authority_status != "confirmed":
                    raise ValidationError(
                        "A model or unverified source cannot confirm legal authority.",
                        details={"sourceAuthorityStatus": source.authority_status},
                    )
            binding = AuthorityBindingModel(
                id=new_uuid(),
                organization_id=organization_id,
                entity_type=entity_type,
                entity_id=entity_id,
                authority_status=authority_status,
                source_id=source_id,
                assertion=assertion.strip(),
                effective_from=effective_from,
                effective_to=effective_to,
                granted_permissions=granted_permissions,
            )
            session.add(binding)
            self._record_change(
                session,
                organization_id=organization_id,
                actor_id=principal.user_id,
                case_id=binding.id,
                action="regulated_hiring.authority_bound",
                safe_state={
                    "entityType": entity_type,
                    "entityId": str(entity_id),
                    "authorityStatus": authority_status,
                },
            )
            await session.flush()
            return {
                "id": str(binding.id),
                "organizationId": str(organization_id),
                "entityType": entity_type,
                "entityId": str(entity_id),
                "authorityStatus": authority_status,
                "sourceId": str(source_id) if source_id else None,
                "effectiveFrom": effective_from,
                "effectiveTo": effective_to,
                "revision": binding.revision,
            }

    async def _require_confirmed_binding(
        self,
        session: AsyncSession,
        organization_id: UUID,
        entity_type: str,
        entity_id: UUID,
        on_date: date,
    ) -> None:
        binding = await session.scalar(
            select(AuthorityBindingModel)
            .where(
                AuthorityBindingModel.organization_id == organization_id,
                AuthorityBindingModel.entity_type == entity_type,
                AuthorityBindingModel.entity_id == entity_id,
                AuthorityBindingModel.effective_from <= on_date,
                (
                    AuthorityBindingModel.effective_to.is_(None)
                    | (AuthorityBindingModel.effective_to >= on_date)
                ),
            )
            .order_by(AuthorityBindingModel.effective_from.desc())
            .limit(1)
        )
        if binding is None:
            raise ValidationError(
                "No authority record exists for the staffing slot.",
                details={"entityType": entity_type, "entityId": str(entity_id)},
            )
        require_confirmed_authority(binding.authority_status, entity_type=entity_type)

    async def _stage_definition(
        self, session: AsyncSession, organization_id: UUID, policy: StagePolicy
    ) -> HiringStageDefinitionModel:
        row = await session.scalar(
            select(HiringStageDefinitionModel).where(
                HiringStageDefinitionModel.organization_id == organization_id,
                HiringStageDefinitionModel.code == policy.code,
                HiringStageDefinitionModel.version_number == 1,
            )
        )
        if row is None:
            raise ConflictError("The regulated hiring stage catalog has not been seeded.")
        return row

    async def _form_definition(
        self, session: AsyncSession, organization_id: UUID, policy: FormPolicy
    ) -> HiringFormDefinitionModel:
        row = await session.scalar(
            select(HiringFormDefinitionModel).where(
                HiringFormDefinitionModel.organization_id == organization_id,
                HiringFormDefinitionModel.code == policy.code,
                HiringFormDefinitionModel.version_number == 1,
            )
        )
        if row is None:
            raise ConflictError("The regulated hiring form catalog has not been seeded.")
        return row

    @staticmethod
    def _require_stage_actor(principal: Principal, policy: StagePolicy) -> None:
        if (
            "system-administrator" in principal.role_codes
            or policy.owner_role_code in principal.role_codes
        ):
            return
        raise ForbiddenError(
            "The actor does not hold the role required for the current hiring stage.",
            details={"requiredRole": policy.owner_role_code},
        )

    @staticmethod
    def _new_execution(
        case_id: UUID,
        definition_id: UUID,
        policy: StagePolicy,
        now: datetime,
        cycle: int,
    ) -> HiringStageExecutionModel:
        due_at = (
            RegulatedHiringService._add_working_days(now, policy.sla_max_days)
            if policy.sla_max_days and policy.working_days
            else now + timedelta(days=policy.sla_max_days)
            if policy.sla_max_days
            else None
        )
        return HiringStageExecutionModel(
            id=new_uuid(),
            case_id=case_id,
            stage_definition_id=definition_id,
            stage_code=policy.code,
            stage_sequence=policy.sequence,
            cycle=cycle,
            status=StageStatus.ACTIVE,
            assigned_user_id=None,
            assigned_employee_id=None,
            started_at=now,
            due_at=due_at,
            completed_at=None,
            decision=None,
            decision_comment=None,
            evidence={},
        )

    @staticmethod
    def _add_working_days(value: datetime, days: int) -> datetime:
        result = value
        remaining = days
        while remaining:
            result += timedelta(days=1)
            if result.weekday() < 5:
                remaining -= 1
        return result

    @staticmethod
    def _case_view(case: HiringProcessCaseModel) -> dict[str, Any]:
        return {
            "id": str(case.id),
            "organizationId": str(case.organization_id),
            "recruitmentRequestId": str(case.recruitment_request_id),
            "staffingSlotId": str(case.staffing_slot_id),
            "businessKey": case.business_key,
            "status": str(case.status),
            "currentStageCode": str(case.current_stage_code),
            "currentStageSequence": case.current_stage_sequence,
            "processEngine": case.process_engine,
            "camundaProcessInstanceKey": case.camunda_process_instance_key,
            "revision": case.revision,
        }

    @staticmethod
    def _record_change(
        session: AsyncSession,
        *,
        organization_id: UUID,
        actor_id: UUID,
        case_id: UUID,
        action: str,
        safe_state: dict[str, object],
        reason: str | None = None,
    ) -> None:
        now = utc_now()
        session.add(
            AuditEventModel(
                id=new_uuid(),
                organization_id=organization_id,
                actor_id=actor_id,
                action=action,
                entity_type="regulated_hiring_case",
                entity_id=case_id,
                before_state=None,
                after_state=safe_state,
                reason=reason,
                request_id=None,
                occurred_at=now,
            )
        )
        session.add(
            OutboxEventModel(
                id=new_uuid(),
                event_name=action,
                aggregate_type="regulated_hiring_case",
                aggregate_id=case_id,
                payload={"caseId": str(case_id), **safe_state},
                schema_version=1,
                occurred_at=now,
                available_at=now,
                processed_at=None,
                attempts=0,
                last_error=None,
            )
        )
