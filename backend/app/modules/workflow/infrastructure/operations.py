from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.audit.service import AuditService
from app.core.errors import ConcurrencyConflictError, ResourceNotFoundError, ValidationError
from app.core.errors.codes import ErrorCode
from app.core.events.domain import ApplicationEvent, EventName
from app.core.events.repository import SqlAlchemyTransactionalOutbox
from app.modules.access_control.infrastructure.models import (
    AccessScopeModel,
    AccessScopeUnitModel,
    PermissionModel,
    RolePermissionModel,
    UserRoleAssignmentModel,
)
from app.modules.employees.infrastructure.models import DelegationModel
from app.modules.identity.infrastructure.models import UserAccountModel
from app.modules.workflow.application.ports import WorkflowView
from app.modules.workflow.domain.entities import (
    ConfigurationProblem,
    ProcessStepDefinition,
    ProcessTransitionDefinition,
    validate_definition,
)
from app.modules.workflow.domain.enums import CompletionMode, StepType
from app.shared.time import utc_now

from .models import (
    ActorRuleModel,
    FormDefinitionModel,
    FormDefinitionVersionModel,
    FormFieldDefinitionModel,
    FormSubmissionModel,
    ProcessDefinitionModel,
    ProcessDefinitionVersionModel,
    ProcessHistoryEntryModel,
    ProcessInstanceModel,
    ProcessStepDefinitionModel,
    ProcessTransitionDefinitionModel,
    WorkflowTaskModel,
)


class SqlAlchemyWorkflowOperations:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def start_linked_instance(
        self,
        session: AsyncSession,
        organization_id: UUID,
        actor_id: UUID,
        data: Mapping[str, Any],
    ) -> WorkflowView:
        definition = await session.scalar(
            select(ProcessDefinitionModel).where(
                ProcessDefinitionModel.organization_id == organization_id,
                ProcessDefinitionModel.code == str(data["definitionCode"]),
                ProcessDefinitionModel.active.is_(True),
            )
        )
        if definition is None:
            raise ResourceNotFoundError("process definition")
        version = await session.scalar(
            select(ProcessDefinitionVersionModel)
            .where(
                ProcessDefinitionVersionModel.process_definition_id == definition.id,
                ProcessDefinitionVersionModel.status == "published",
            )
            .order_by(ProcessDefinitionVersionModel.version_number.desc())
        )
        if version is None:
            raise ValidationError(
                "A published process definition is required.",
                code=ErrorCode.PROCESS_DEFINITION_NOT_PUBLISHED,
            )
        steps = (
            await session.scalars(
                select(ProcessStepDefinitionModel)
                .where(
                    ProcessStepDefinitionModel.definition_version_id == version.id,
                    ProcessStepDefinitionModel.active.is_(True),
                )
                .order_by(ProcessStepDefinitionModel.sequence)
            )
        ).all()
        if not steps:
            raise ValidationError(
                "The process has no active steps.", code=ErrorCode.PROCESS_CONFIGURATION_INVALID
            )
        detail = await self._version_detail(session, version)
        context = dict(cast(Mapping[str, Any], data.get("context", {})))
        row = ProcessInstanceModel(
            organization_id=organization_id,
            process_definition_id=definition.id,
            definition_version_id=version.id,
            business_type=str(data["businessType"]),
            business_entity_id=UUID(str(data["businessEntityId"])),
            initiator_user_id=actor_id,
            status="active",
            current_phase=steps[0].code,
            started_at=utc_now(),
            snapshot={
                "definition": _json_safe(dict(detail)),
                "context": _json_safe(context),
                "formVersionIds": sorted(
                    {
                        str(item.configuration["formVersionId"])
                        for item in steps
                        if item.configuration.get("formVersionId")
                    }
                ),
            },
        )
        session.add(row)
        await session.flush()
        if not await self._create_tasks(session, row, steps[0]):
            raise ValidationError(
                "Workflow actor could not be resolved.", code=ErrorCode.PROCESS_ACTOR_UNRESOLVED
            )
        await self._history(session, row.id, actor_id, "processStarted", "Process started.")
        await self._event(
            session,
            EventName.PROCESS_INSTANCE_STARTED,
            "processInstance",
            row.id,
            {
                "processInstanceId": str(row.id),
                "businessType": row.business_type,
                "businessEntityId": str(row.business_entity_id),
            },
        )
        return _instance_view(row)

    async def require_organization(
        self, resource: str, resource_id: UUID, organization_id: UUID
    ) -> None:
        async with self._sessions() as session:
            if resource == "definition":
                actual = await session.scalar(
                    select(ProcessDefinitionModel.organization_id).where(
                        ProcessDefinitionModel.id == resource_id
                    )
                )
            elif resource == "version":
                actual = await session.scalar(
                    select(ProcessDefinitionModel.organization_id)
                    .join(
                        ProcessDefinitionVersionModel,
                        ProcessDefinitionVersionModel.process_definition_id
                        == ProcessDefinitionModel.id,
                    )
                    .where(ProcessDefinitionVersionModel.id == resource_id)
                )
            elif resource == "instance":
                actual = await session.scalar(
                    select(ProcessInstanceModel.organization_id).where(
                        ProcessInstanceModel.id == resource_id
                    )
                )
            elif resource == "task":
                actual = await session.scalar(
                    select(ProcessInstanceModel.organization_id)
                    .join(
                        WorkflowTaskModel,
                        WorkflowTaskModel.process_instance_id == ProcessInstanceModel.id,
                    )
                    .where(WorkflowTaskModel.id == resource_id)
                )
            elif resource == "form":
                actual = await session.scalar(
                    select(FormDefinitionModel.organization_id).where(
                        FormDefinitionModel.id == resource_id
                    )
                )
            elif resource == "form_version":
                actual = await session.scalar(
                    select(FormDefinitionModel.organization_id)
                    .join(
                        FormDefinitionVersionModel,
                        FormDefinitionVersionModel.form_definition_id == FormDefinitionModel.id,
                    )
                    .where(FormDefinitionVersionModel.id == resource_id)
                )
            else:
                raise ResourceNotFoundError("workflow resource")
            if actual != organization_id:
                raise ResourceNotFoundError(resource, resource_id)

    async def list_definitions(self, organization_id: UUID) -> Sequence[WorkflowView]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ProcessDefinitionModel)
                    .where(ProcessDefinitionModel.organization_id == organization_id)
                    .order_by(ProcessDefinitionModel.code)
                )
            ).all()
            return [_definition_view(row) for row in rows]

    async def create_form_definition(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, Any]
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            row = FormDefinitionModel(
                organization_id=organization_id,
                code=str(data["code"]),
                name=str(data["name"]),
                active=True,
            )
            session.add(row)
            await session.flush()
            view = _form_definition_view(row)
            await self._record(
                session,
                actor_id,
                organization_id,
                "workflow.form.created",
                "formDefinition",
                row.id,
                view,
            )
            return view

    async def create_form_draft(
        self, form_id: UUID, actor_id: UUID, based_on_version_id: UUID | None
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            form = await session.get(FormDefinitionModel, form_id)
            if form is None:
                raise ResourceNotFoundError("form definition", form_id)
            latest = await session.scalar(
                select(func.max(FormDefinitionVersionModel.version_number)).where(
                    FormDefinitionVersionModel.form_definition_id == form.id
                )
            )
            row = FormDefinitionVersionModel(
                form_definition_id=form.id,
                version_number=int(latest or 0) + 1,
                status="draft",
                based_on_version_id=based_on_version_id,
                created_by=actor_id,
                created_at=utc_now(),
            )
            session.add(row)
            await session.flush()
            if based_on_version_id:
                source = await session.get(FormDefinitionVersionModel, based_on_version_id)
                if source is None or source.form_definition_id != form.id:
                    raise ValidationError("The base form version is invalid.")
                fields = (
                    await session.scalars(
                        select(FormFieldDefinitionModel).where(
                            FormFieldDefinitionModel.form_version_id == source.id
                        )
                    )
                ).all()
                for field in fields:
                    session.add(
                        FormFieldDefinitionModel(
                            form_version_id=row.id,
                            code=field.code,
                            label=field.label,
                            field_type=field.field_type,
                            required=field.required,
                            validation_rules=field.validation_rules,
                            reference_data_source=field.reference_data_source,
                            visibility_rule=field.visibility_rule,
                            editability_rule=field.editability_rule,
                            confidentiality=field.confidentiality,
                            ordering=field.ordering,
                            help_text=field.help_text,
                        )
                    )
            view = _form_version_view(row)
            await self._record(
                session,
                actor_id,
                form.organization_id,
                "workflow.form.version.created",
                "formDefinitionVersion",
                row.id,
                view,
            )
            return view

    async def save_form_field(
        self, version_id: UUID, actor_id: UUID, data: Mapping[str, Any]
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            version, form = await self._form_version(session, version_id)
            if version.status != "draft":
                raise ValidationError(
                    "Only draft form versions are editable.",
                    code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED,
                )
            field_type = str(data["fieldType"])
            if field_type not in {
                "text",
                "multiline",
                "number",
                "boolean",
                "date",
                "datetime",
                "select",
                "multi_select",
                "reference",
            }:
                raise ValidationError("The form field type is unsupported.")
            validation_rules = cast(dict[str, Any], data.get("validationRules", {}))
            if set(validation_rules) - {"minLength", "maxLength", "minimum", "maximum", "options"}:
                raise ValidationError("The form validation rule is unsupported.")
            for rule_name in ("visibilityRule", "editabilityRule"):
                rule = data.get(rule_name)
                if rule is not None and not isinstance(rule, Mapping):
                    raise ValidationError(f"{rule_name} must be declarative data.")
            row = FormFieldDefinitionModel(
                form_version_id=version.id,
                code=str(data["code"]),
                label=str(data["label"]),
                field_type=field_type,
                required=bool(data.get("required", False)),
                validation_rules=validation_rules,
                reference_data_source=cast(str | None, data.get("referenceDataSource")),
                visibility_rule=cast(dict[str, Any] | None, data.get("visibilityRule")),
                editability_rule=cast(dict[str, Any] | None, data.get("editabilityRule")),
                confidentiality=str(data.get("confidentiality", "internal")),
                ordering=int(data["ordering"]),
                help_text=cast(str | None, data.get("helpText")),
            )
            session.add(row)
            await session.flush()
            version.revision += 1
            view = _form_field_view(row)
            await self._record(
                session,
                actor_id,
                form.organization_id,
                "workflow.form.field.created",
                "formFieldDefinition",
                row.id,
                view,
            )
            return view

    async def publish_form_version(
        self, version_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            version, form = await self._form_version(session, version_id)
            self._revision(version.revision, revision)
            if version.status != "draft":
                raise ValidationError(
                    "Only a draft form can be published.",
                    code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED,
                )
            field_count = await session.scalar(
                select(func.count())
                .select_from(FormFieldDefinitionModel)
                .where(FormFieldDefinitionModel.form_version_id == version.id)
            )
            if not field_count:
                raise ValidationError("A form must contain at least one field.")
            version.status = "published"
            version.published_by = actor_id
            version.published_at = utc_now()
            version.revision += 1
            view = _form_version_view(version)
            await self._record(
                session,
                actor_id,
                form.organization_id,
                "workflow.form.version.published",
                "formDefinitionVersion",
                version.id,
                view,
                reason,
            )
            return view

    async def submit_form(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, Any]
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            version, form = await self._form_version(session, UUID(str(data["formVersionId"])))
            if form.organization_id != organization_id or version.status != "published":
                raise ResourceNotFoundError("published form version", version.id)
            process_id = (
                UUID(str(data["processInstanceId"])) if data.get("processInstanceId") else None
            )
            if process_id:
                instance = await session.get(ProcessInstanceModel, process_id)
                if instance is None or instance.organization_id != organization_id:
                    raise ResourceNotFoundError("process instance", process_id)
                configured = cast(Sequence[object], instance.snapshot.get("formVersionIds", []))
                if str(version.id) not in {str(item) for item in configured}:
                    raise ValidationError(
                        "The form version does not match the process snapshot.",
                        code=ErrorCode.PROCESS_CONFIGURATION_INVALID,
                    )
            submitted = cast(dict[str, Any], data.get("data", {}))
            fields = (
                await session.scalars(
                    select(FormFieldDefinitionModel).where(
                        FormFieldDefinitionModel.form_version_id == version.id
                    )
                )
            ).all()
            self._validate_form_submission(fields, submitted)
            row = FormSubmissionModel(
                organization_id=organization_id,
                form_version_id=version.id,
                process_instance_id=process_id,
                business_entity_type=str(data["businessEntityType"]),
                business_entity_id=UUID(str(data["businessEntityId"])),
                submitted_by=actor_id,
                data=submitted,
                submitted_at=utc_now(),
            )
            session.add(row)
            await session.flush()
            view = _form_submission_view(row)
            await self._record(
                session,
                actor_id,
                organization_id,
                "workflow.form.submitted",
                "formSubmission",
                row.id,
                {**view, "data": "[redacted]"},
            )
            return view

    async def _form_version(
        self, session: AsyncSession, version_id: UUID
    ) -> tuple[FormDefinitionVersionModel, FormDefinitionModel]:
        version = await session.get(FormDefinitionVersionModel, version_id)
        if version is None:
            raise ResourceNotFoundError("form definition version", version_id)
        form = await session.get(FormDefinitionModel, version.form_definition_id)
        if form is None:
            raise ResourceNotFoundError("form definition", version.form_definition_id)
        return version, form

    def _validate_form_submission(
        self, fields: Sequence[FormFieldDefinitionModel], submitted: Mapping[str, Any]
    ) -> None:
        by_code = {field.code: field for field in fields}
        unknown = set(submitted) - set(by_code)
        if unknown:
            raise ValidationError("The submission contains unknown form fields.")
        for field in fields:
            value = submitted.get(field.code)
            if field.required and (value is None or value == "" or value == []):
                raise ValidationError(f"The form field '{field.code}' is required.")
            if value is None:
                continue
            rules = field.validation_rules
            if field.field_type in {"text", "multiline"}:
                if not isinstance(value, str):
                    raise ValidationError(f"The form field '{field.code}' must be text.")
                if "minLength" in rules and len(value) < int(rules["minLength"]):
                    raise ValidationError(f"The form field '{field.code}' is too short.")
                if "maxLength" in rules and len(value) > int(rules["maxLength"]):
                    raise ValidationError(f"The form field '{field.code}' is too long.")
            if field.field_type == "boolean" and not isinstance(value, bool):
                raise ValidationError(f"The form field '{field.code}' must be boolean.")
            if "options" in rules and value not in cast(Sequence[object], rules["options"]):
                raise ValidationError(f"The form field '{field.code}' has an invalid option.")

    async def create_definition(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, Any]
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            row = ProcessDefinitionModel(
                organization_id=organization_id,
                code=str(data["code"]),
                name=str(data["name"]),
                description=cast(str | None, data.get("description")),
                active=True,
            )
            session.add(row)
            await session.flush()
            await self._record(
                session,
                actor_id,
                organization_id,
                "workflow.definition.created",
                "processDefinition",
                row.id,
                _definition_view(row),
            )
            return _definition_view(row)

    async def create_draft(
        self, definition_id: UUID, actor_id: UUID, based_on_version_id: UUID | None, name: str
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            definition = await session.get(ProcessDefinitionModel, definition_id)
            if definition is None:
                raise ResourceNotFoundError("process definition", definition_id)
            number = (
                await session.scalar(
                    select(
                        func.coalesce(func.max(ProcessDefinitionVersionModel.version_number), 0)
                    ).where(ProcessDefinitionVersionModel.process_definition_id == definition_id)
                )
            ) or 0
            base = (
                await session.get(ProcessDefinitionVersionModel, based_on_version_id)
                if based_on_version_id
                else None
            )
            row = ProcessDefinitionVersionModel(
                process_definition_id=definition_id,
                version_number=number + 1,
                name=name,
                status="draft",
                based_on_version_id=base.id if base else None,
                created_by=actor_id,
                created_at=utc_now(),
            )
            session.add(row)
            await session.flush()
            if base:
                await self._clone(session, base.id, row.id)
            await self._record(
                session,
                actor_id,
                definition.organization_id,
                "workflow.definition.draft.created",
                "processDefinitionVersion",
                row.id,
                _version_view(row),
            )
            return _version_view(row)

    async def get_version(self, version_id: UUID) -> WorkflowView:
        async with self._sessions() as session:
            row = await self._version(session, version_id)
            return await self._version_detail(session, row)

    async def save_actor_rule(
        self, version_id: UUID, actor_id: UUID, data: Mapping[str, Any]
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            version = await self._draft(session, version_id)
            row = ActorRuleModel(
                definition_version_id=version_id,
                code=str(data["code"]),
                name=str(data["name"]),
                rule_type=str(data["ruleType"]),
                configuration=dict(cast(Mapping[str, Any], data.get("configuration", {}))),
                active=True,
            )
            session.add(row)
            await session.flush()
            await self._touch(version)
            await self._record_for_version(
                session,
                actor_id,
                version,
                "workflow.actor_rule.created",
                "actorRule",
                row.id,
                _actor_rule_view(row),
            )
            return _actor_rule_view(row)

    async def save_step(
        self, version_id: UUID, actor_id: UUID, data: Mapping[str, Any]
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            version = await self._draft(session, version_id)
            row = ProcessStepDefinitionModel(
                definition_version_id=version_id,
                stable_key=UUID(str(data.get("stableKey")))
                if data.get("stableKey")
                else UUID(int=0),
                code=str(data["code"]),
                name=str(data["name"]),
                step_type=str(data["stepType"]),
                sequence=int(data["sequence"]),
                actor_rule_id=UUID(str(data["actorRuleId"])) if data.get("actorRuleId") else None,
                allowed_actions=list(cast(Sequence[str], data["allowedActions"])),
                due_duration_seconds=int(data["dueDurationSeconds"])
                if data.get("dueDurationSeconds") is not None
                else None,
                required_document_type_ids=[
                    str(item)
                    for item in cast(Sequence[object], data.get("requiredDocumentTypeIds", ()))
                ],
                configuration=dict(cast(Mapping[str, Any], data.get("configuration", {}))),
                completion_mode=str(data.get("completionMode", "all")),
                required_approvers=int(data.get("requiredApprovers", 1)),
                active=True,
            )
            session.add(row)
            await session.flush()
            if row.stable_key.int == 0:
                row.stable_key = row.id
            await self._touch(version)
            await self._record_for_version(
                session,
                actor_id,
                version,
                "workflow.step.created",
                "processStepDefinition",
                row.id,
                _step_view(row),
            )
            return _step_view(row)

    async def save_transition(
        self, version_id: UUID, actor_id: UUID, data: Mapping[str, Any]
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            version = await self._draft(session, version_id)
            row = ProcessTransitionDefinitionModel(
                definition_version_id=version_id,
                source_step_id=UUID(str(data["sourceStepId"])),
                target_step_id=UUID(str(data["targetStepId"])),
                action=str(data["action"]),
                condition=dict(cast(Mapping[str, Any], data["condition"]))
                if data.get("condition")
                else None,
                priority=int(data.get("priority", 0)),
                active=True,
            )
            session.add(row)
            await session.flush()
            await self._touch(version)
            await self._record_for_version(
                session,
                actor_id,
                version,
                "workflow.transition.created",
                "processTransitionDefinition",
                row.id,
                _transition_view(row),
            )
            return _transition_view(row)

    async def validate_version(
        self, version_id: UUID, actor_id: UUID
    ) -> tuple[ConfigurationProblem, ...]:
        async with self._sessions.begin() as session:
            version = await self._version(session, version_id)
            problems = await self._problems(session, version_id)
            await self._record_for_version(
                session,
                actor_id,
                version,
                "workflow.definition.validated",
                "processDefinitionVersion",
                version.id,
                {"valid": not problems, "problems": [asdict(problem) for problem in problems]},
            )
            return problems

    async def submit_review(
        self, version_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> WorkflowView:
        return await self._transition_version(
            version_id,
            actor_id,
            revision,
            reason,
            "draft",
            "in_review",
            "workflow.definition.review.submitted",
        )

    async def return_draft(
        self, version_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> WorkflowView:
        return await self._transition_version(
            version_id,
            actor_id,
            revision,
            reason,
            "in_review",
            "draft",
            "workflow.definition.review.returned",
        )

    async def publish(
        self, version_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            version = await self._version(session, version_id)
            self._revision(version.revision, revision)
            if version.status not in {"draft", "in_review"}:
                raise ValidationError(
                    "Only draft or reviewed definitions can be published.",
                    code=ErrorCode.PROCESS_CONFIGURATION_INVALID,
                )
            problems = await self._problems(session, version_id)
            if problems:
                raise ValidationError(
                    "Process configuration is invalid.",
                    code=ErrorCode.PROCESS_CONFIGURATION_INVALID,
                    problems=[asdict(problem) for problem in problems],
                )
            now = utc_now()
            previous = (
                await session.scalars(
                    select(ProcessDefinitionVersionModel).where(
                        ProcessDefinitionVersionModel.process_definition_id
                        == version.process_definition_id,
                        ProcessDefinitionVersionModel.status == "published",
                    )
                )
            ).all()
            for item in previous:
                item.status = "archived"
                item.effective_to = now
            version.status = "published"
            version.effective_from = now
            version.published_by = actor_id
            version.published_at = now
            version.revision += 1
            definition = await session.get(ProcessDefinitionModel, version.process_definition_id)
            if definition is None:
                raise ResourceNotFoundError("process definition", version.process_definition_id)
            await self._record(
                session,
                actor_id,
                definition.organization_id,
                "workflow.definition.published",
                "processDefinitionVersion",
                version.id,
                _version_view(version),
                reason,
            )
            return _version_view(version)

    async def compare_versions(self, left_id: UUID, right_id: UUID) -> WorkflowView:
        async with self._sessions() as session:
            left = (
                await session.scalars(
                    select(ProcessStepDefinitionModel).where(
                        ProcessStepDefinitionModel.definition_version_id == left_id
                    )
                )
            ).all()
            right = (
                await session.scalars(
                    select(ProcessStepDefinitionModel).where(
                        ProcessStepDefinitionModel.definition_version_id == right_id
                    )
                )
            ).all()
            left_map = {item.stable_key: item for item in left}
            right_map = {item.stable_key: item for item in right}
            return {
                "added": [str(key) for key in right_map.keys() - left_map.keys()],
                "removed": [str(key) for key in left_map.keys() - right_map.keys()],
                "changed": [
                    str(key)
                    for key in left_map.keys() & right_map.keys()
                    if _step_view(left_map[key]) != _step_view(right_map[key])
                ],
            }

    async def start_instance(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, Any]
    ) -> WorkflowView:
        actor_unresolved = False
        result: WorkflowView | None = None
        async with self._sessions.begin() as session:
            code = str(data["definitionCode"])
            definition = await session.scalar(
                select(ProcessDefinitionModel).where(
                    ProcessDefinitionModel.organization_id == organization_id,
                    ProcessDefinitionModel.code == code,
                    ProcessDefinitionModel.active.is_(True),
                )
            )
            if definition is None:
                raise ResourceNotFoundError("process definition")
            version = await session.scalar(
                select(ProcessDefinitionVersionModel)
                .where(
                    ProcessDefinitionVersionModel.process_definition_id == definition.id,
                    ProcessDefinitionVersionModel.status == "published",
                )
                .order_by(ProcessDefinitionVersionModel.version_number.desc())
            )
            if version is None:
                raise ValidationError(
                    "A published process definition is required.",
                    code=ErrorCode.PROCESS_DEFINITION_NOT_PUBLISHED,
                )
            detail = await self._version_detail(session, version)
            steps = (
                await session.scalars(
                    select(ProcessStepDefinitionModel)
                    .where(
                        ProcessStepDefinitionModel.definition_version_id == version.id,
                        ProcessStepDefinitionModel.active.is_(True),
                    )
                    .order_by(ProcessStepDefinitionModel.sequence)
                )
            ).all()
            if not steps:
                raise ValidationError(
                    "The process has no active steps.", code=ErrorCode.PROCESS_CONFIGURATION_INVALID
                )
            row = ProcessInstanceModel(
                organization_id=organization_id,
                process_definition_id=definition.id,
                definition_version_id=version.id,
                business_type=str(data["businessType"]),
                business_entity_id=UUID(str(data["businessEntityId"])),
                initiator_user_id=actor_id,
                status="active",
                current_phase=steps[0].code,
                started_at=utc_now(),
                snapshot={
                    "definition": _json_safe(dict(detail)),
                    "context": _json_safe(dict(cast(Mapping[str, Any], data.get("context", {})))),
                    "formVersionIds": sorted(
                        {
                            str(item.configuration["formVersionId"])
                            for item in steps
                            if item.configuration.get("formVersionId")
                        }
                        | {
                            str(item)
                            for item in cast(
                                Sequence[object],
                                cast(Mapping[str, Any], data.get("context", {})).get(
                                    "formVersionIds", []
                                ),
                            )
                        }
                    ),
                },
            )
            session.add(row)
            await session.flush()
            tasks = await self._create_tasks(session, row, steps[0])
            actor_unresolved = not tasks
            await self._history(session, row.id, actor_id, "processStarted", "Process started.")
            await self._event(
                session,
                EventName.PROCESS_INSTANCE_STARTED,
                "processInstance",
                row.id,
                {
                    "processInstanceId": str(row.id),
                    "businessType": row.business_type,
                    "businessEntityId": str(row.business_entity_id),
                },
            )
            result = _instance_view(row)
        if actor_unresolved:
            raise ValidationError(
                "Workflow actor could not be resolved.", code=ErrorCode.PROCESS_ACTOR_UNRESOLVED
            )
        if result is None:  # pragma: no cover - defensive transaction invariant
            raise RuntimeError("Workflow instance transaction produced no result.")
        return result

    async def list_instances(
        self, organization_id: UUID, offset: int, limit: int
    ) -> tuple[Sequence[WorkflowView], int]:
        async with self._sessions() as session:
            query = select(ProcessInstanceModel).where(
                ProcessInstanceModel.organization_id == organization_id
            )
            rows = (
                await session.scalars(
                    query.order_by(ProcessInstanceModel.started_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
            return [_instance_view(row) for row in rows], total

    async def get_instance(self, instance_id: UUID) -> WorkflowView:
        async with self._sessions() as session:
            row = await session.get(ProcessInstanceModel, instance_id)
            if row is None:
                raise ResourceNotFoundError("process instance", instance_id)
            return _instance_view(row)

    async def history(self, instance_id: UUID) -> Sequence[WorkflowView]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ProcessHistoryEntryModel)
                    .where(ProcessHistoryEntryModel.process_instance_id == instance_id)
                    .order_by(ProcessHistoryEntryModel.occurred_at)
                )
            ).all()
            return [_history_view(row) for row in rows]

    async def my_tasks(
        self, user_id: UUID, offset: int, limit: int
    ) -> tuple[Sequence[WorkflowView], int]:
        async with self._sessions() as session:
            query = select(WorkflowTaskModel).where(WorkflowTaskModel.assigned_user_id == user_id)
            rows = (
                await session.scalars(
                    query.order_by(WorkflowTaskModel.created_at.desc()).offset(offset).limit(limit)
                )
            ).all()
            total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
            return [_task_view(row) for row in rows], total

    async def act_task(
        self,
        task_id: UUID,
        actor_id: UUID,
        revision: int,
        action: str,
        comment: str | None,
        idempotency_key: str,
    ) -> WorkflowView:
        actor_unresolved = False
        result: WorkflowView | None = None
        async with self._sessions.begin() as session:
            existing = await session.scalar(
                select(WorkflowTaskModel).where(
                    WorkflowTaskModel.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                return _task_view(existing)
            task = await session.get(WorkflowTaskModel, task_id, with_for_update=True)
            if task is None:
                raise ResourceNotFoundError("workflow task", task_id)
            self._revision(task.revision, revision)
            if task.assigned_user_id != actor_id:
                raise ValidationError(
                    "The task is assigned to another actor.",
                    code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED,
                )
            if task.status not in {"active", "pending"}:
                raise ValidationError(
                    "The task was already completed.", code=ErrorCode.PROCESS_TASK_ALREADY_COMPLETED
                )
            if action in {"return", "reject", "cancel"} and not (comment or "").strip():
                raise ValidationError(
                    "A decision reason is required.", code=ErrorCode.PROCESS_RETURN_REASON_REQUIRED
                )
            step = await session.get(ProcessStepDefinitionModel, task.step_definition_id)
            if step is None:
                raise ResourceNotFoundError("process step", task.step_definition_id)
            if action not in step.allowed_actions:
                raise ValidationError(
                    "The action is not allowed for this task.",
                    code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED,
                )
            task.status = {"return": "returned", "reject": "rejected", "cancel": "cancelled"}.get(
                action, "completed"
            )
            task.decision = action
            task.decision_comment = comment
            task.completed_at = utc_now()
            task.idempotency_key = idempotency_key
            task.revision += 1
            instance = await session.get(
                ProcessInstanceModel, task.process_instance_id, with_for_update=True
            )
            if instance is None:
                raise ResourceNotFoundError("process instance", task.process_instance_id)
            await self._history(session, instance.id, actor_id, action, f"Task {action} recorded.")
            await self._event(
                session,
                EventName.WORKFLOW_TASK_COMPLETED,
                "workflowTask",
                task.id,
                {"taskId": str(task.id), "processInstanceId": str(instance.id), "action": action},
            )
            siblings = (
                await session.scalars(
                    select(WorkflowTaskModel).where(
                        WorkflowTaskModel.process_instance_id == instance.id,
                        WorkflowTaskModel.step_definition_id == step.id,
                        WorkflowTaskModel.id != task.id,
                    )
                )
            ).all()
            if action not in {"return", "reject", "cancel"}:
                approvals = 1 + sum(item.status == "completed" for item in siblings)
                ready = approvals >= step.required_approvers
                if step.completion_mode == "all":
                    ready = ready and not any(
                        item.status in {"active", "pending"} for item in siblings
                    )
                if not ready:
                    return _task_view(task)
                if step.completion_mode == "any":
                    for sibling in siblings:
                        if sibling.status in {"active", "pending"}:
                            sibling.status = "cancelled"
                            sibling.revision += 1
            transitions = (
                await session.scalars(
                    select(ProcessTransitionDefinitionModel)
                    .where(
                        ProcessTransitionDefinitionModel.definition_version_id
                        == instance.definition_version_id,
                        ProcessTransitionDefinitionModel.source_step_id == step.id,
                        ProcessTransitionDefinitionModel.action == action,
                        ProcessTransitionDefinitionModel.active.is_(True),
                    )
                    .order_by(ProcessTransitionDefinitionModel.priority.desc())
                )
            ).all()
            context = cast(Mapping[str, Any], instance.snapshot.get("context", {}))
            transition = next(
                (item for item in transitions if _condition_matches(item.condition, context)), None
            )
            if transition is None:
                instance.status = "cancelled" if action == "cancel" else "completed"
                instance.completed_at = utc_now() if instance.status == "completed" else None
                instance.cancelled_at = utc_now() if instance.status == "cancelled" else None
                instance.revision += 1
                event = (
                    EventName.PROCESS_INSTANCE_CANCELLED
                    if instance.status == "cancelled"
                    else EventName.PROCESS_INSTANCE_COMPLETED
                )
                await self._event(
                    session,
                    event,
                    "processInstance",
                    instance.id,
                    {"processInstanceId": str(instance.id)},
                )
            else:
                target = await session.get(ProcessStepDefinitionModel, transition.target_step_id)
                if target is None:
                    raise ResourceNotFoundError("process step", transition.target_step_id)
                tasks = await self._create_tasks(session, instance, target)
                actor_unresolved = not tasks
                instance.current_phase = target.code
                instance.revision += 1
            result = _task_view(task)
        if actor_unresolved:
            raise ValidationError(
                "Workflow actor could not be resolved.", code=ErrorCode.PROCESS_ACTOR_UNRESOLVED
            )
        if result is None:  # pragma: no cover - defensive transaction invariant
            raise RuntimeError("Workflow task transaction produced no result.")
        return result

    async def act_linked_task(
        self,
        session: AsyncSession,
        process_instance_id: UUID,
        actor_id: UUID,
        action: str,
        comment: str | None,
        idempotency_key: str,
        *,
        expected_phase: str | None = None,
    ) -> WorkflowView:
        """Advance a linked process inside the caller's business transaction."""
        existing = await session.scalar(
            select(WorkflowTaskModel).where(WorkflowTaskModel.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return _task_view(existing)
        instance = await session.get(
            ProcessInstanceModel, process_instance_id, with_for_update=True
        )
        if instance is None:
            raise ResourceNotFoundError("process instance", process_instance_id)
        if expected_phase is not None and instance.current_phase != expected_phase:
            raise ValidationError(
                "The linked workflow is not at the expected business stage.",
                code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED,
            )
        task = await session.scalar(
            select(WorkflowTaskModel)
            .where(
                WorkflowTaskModel.process_instance_id == instance.id,
                WorkflowTaskModel.status.in_(("active", "pending")),
                WorkflowTaskModel.assigned_user_id == actor_id,
            )
            .order_by(WorkflowTaskModel.created_at)
            .with_for_update()
        )
        if task is None:
            candidate = await session.scalar(
                select(WorkflowTaskModel)
                .where(
                    WorkflowTaskModel.process_instance_id == instance.id,
                    WorkflowTaskModel.status.in_(("active", "pending")),
                )
                .order_by(WorkflowTaskModel.created_at)
                .with_for_update()
            )
            candidate_step = (
                await session.get(ProcessStepDefinitionModel, candidate.step_definition_id)
                if candidate is not None
                else None
            )
            eligible = (
                await self._resolve_users(session, instance, candidate_step)
                if candidate_step is not None
                else []
            )
            if candidate is None or actor_id not in eligible:
                raise ValidationError(
                    "No active linked workflow task is assigned to the actor.",
                    code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED,
                )
            account = await session.get(UserAccountModel, actor_id)
            candidate.assigned_user_id = actor_id
            candidate.assigned_employee_id = account.employee_id if account else None
            candidate.revision += 1
            task = candidate
        step = await session.get(ProcessStepDefinitionModel, task.step_definition_id)
        if step is None:
            raise ResourceNotFoundError("process step", task.step_definition_id)
        if action not in step.allowed_actions:
            raise ValidationError(
                "The action is not allowed for the linked workflow task.",
                code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED,
            )
        if action in {"return", "reject", "cancel"} and not (comment or "").strip():
            raise ValidationError(
                "A decision reason is required.", code=ErrorCode.PROCESS_RETURN_REASON_REQUIRED
            )
        task.status = {"return": "returned", "reject": "rejected", "cancel": "cancelled"}.get(
            action, "completed"
        )
        task.decision = action
        task.decision_comment = comment
        task.completed_at = utc_now()
        task.idempotency_key = idempotency_key
        task.revision += 1
        await self._history(session, instance.id, actor_id, action, f"Task {action} recorded.")
        await self._event(
            session,
            EventName.WORKFLOW_TASK_COMPLETED,
            "workflowTask",
            task.id,
            {"taskId": str(task.id), "processInstanceId": str(instance.id), "action": action},
        )
        siblings = list(
            (
                await session.scalars(
                    select(WorkflowTaskModel).where(
                        WorkflowTaskModel.process_instance_id == instance.id,
                        WorkflowTaskModel.step_definition_id == step.id,
                        WorkflowTaskModel.id != task.id,
                    )
                )
            ).all()
        )
        if action not in {"return", "reject", "cancel"}:
            approvals = 1 + sum(item.status == "completed" for item in siblings)
            ready = approvals >= step.required_approvers
            if step.completion_mode == "all":
                ready = ready and not any(item.status in {"active", "pending"} for item in siblings)
            if not ready:
                return _task_view(task)
            if step.completion_mode == "any":
                for sibling in siblings:
                    if sibling.status in {"active", "pending"}:
                        sibling.status = "cancelled"
                        sibling.completed_at = utc_now()
                        sibling.revision += 1
        transitions = list(
            (
                await session.scalars(
                    select(ProcessTransitionDefinitionModel)
                    .where(
                        ProcessTransitionDefinitionModel.definition_version_id
                        == instance.definition_version_id,
                        ProcessTransitionDefinitionModel.source_step_id == step.id,
                        ProcessTransitionDefinitionModel.action == action,
                        ProcessTransitionDefinitionModel.active.is_(True),
                    )
                    .order_by(ProcessTransitionDefinitionModel.priority.desc())
                )
            ).all()
        )
        context = cast(Mapping[str, Any], instance.snapshot.get("context", {}))
        transition = next(
            (item for item in transitions if _condition_matches(item.condition, context)), None
        )
        if transition is not None:
            target = await session.get(ProcessStepDefinitionModel, transition.target_step_id)
            if target is None:
                raise ResourceNotFoundError("process step", transition.target_step_id)
            tasks = await self._create_tasks(session, instance, target)
            if not tasks:
                raise ValidationError(
                    "Workflow actor could not be resolved.",
                    code=ErrorCode.PROCESS_ACTOR_UNRESOLVED,
                )
            instance.current_phase = target.code
            instance.revision += 1
        elif action == "return":
            instance.status = "active"
            instance.revision += 1
        else:
            final_status = (
                "cancelled"
                if action == "cancel"
                else ("rejected" if action == "reject" else "completed")
            )
            instance.status = final_status
            now = utc_now()
            instance.completed_at = now if final_status in {"completed", "rejected"} else None
            instance.cancelled_at = now if final_status == "cancelled" else None
            instance.revision += 1
            for pending in await session.scalars(
                select(WorkflowTaskModel).where(
                    WorkflowTaskModel.process_instance_id == instance.id,
                    WorkflowTaskModel.status.in_(("active", "pending")),
                )
            ):
                pending.status = "cancelled"
                pending.completed_at = now
                pending.revision += 1
            await self._event(
                session,
                EventName.PROCESS_INSTANCE_CANCELLED
                if final_status == "cancelled"
                else EventName.PROCESS_INSTANCE_COMPLETED,
                "processInstance",
                instance.id,
                {"processInstanceId": str(instance.id), "status": final_status},
            )
        return _task_view(task)

    async def linked_action_exists(self, session: AsyncSession, idempotency_key: str) -> bool:
        return bool(
            await session.scalar(
                select(WorkflowTaskModel.id).where(
                    WorkflowTaskModel.idempotency_key == idempotency_key
                )
            )
        )

    async def resume_linked_task(
        self,
        session: AsyncSession,
        process_instance_id: UUID,
        actor_id: UUID,
        idempotency_key: str,
    ) -> WorkflowView:
        """Re-open the returned workflow step when its business record is resubmitted."""
        instance = await session.get(
            ProcessInstanceModel, process_instance_id, with_for_update=True
        )
        if instance is None:
            raise ResourceNotFoundError("process instance", process_instance_id)
        task = await session.scalar(
            select(WorkflowTaskModel)
            .where(
                WorkflowTaskModel.process_instance_id == instance.id,
                WorkflowTaskModel.status == "returned",
            )
            .order_by(WorkflowTaskModel.completed_at.desc())
            .with_for_update()
        )
        if task is None:
            active = await session.scalar(
                select(WorkflowTaskModel).where(
                    WorkflowTaskModel.process_instance_id == instance.id,
                    WorkflowTaskModel.status.in_(("active", "pending")),
                )
            )
            if active is not None:
                return _task_view(active)
            raise ValidationError(
                "The linked workflow has no returned task to resume.",
                code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED,
            )
        task.status = "active"
        task.decision = None
        task.decision_comment = None
        task.completed_at = None
        task.idempotency_key = None
        task.revision += 1
        instance.status = "active"
        instance.revision += 1
        await self._history(
            session, instance.id, actor_id, "resubmit", "Business case resubmitted."
        )
        await self._event(
            session,
            EventName.WORKFLOW_TASK_ASSIGNED,
            "workflowTask",
            task.id,
            {
                "taskId": str(task.id),
                "processInstanceId": str(instance.id),
                "idempotencyKey": idempotency_key,
            },
        )
        return _task_view(task)

    async def cancel_linked_instance(
        self,
        session: AsyncSession,
        process_instance_id: UUID,
        actor_id: UUID,
        reason: str,
    ) -> None:
        """Cancel a business-owned process and every unfinished generic task atomically."""
        instance = await session.get(
            ProcessInstanceModel, process_instance_id, with_for_update=True
        )
        if instance is None:
            raise ResourceNotFoundError("process instance", process_instance_id)
        if instance.status == "cancelled":
            return
        now = utc_now()
        tasks = (
            await session.scalars(
                select(WorkflowTaskModel)
                .where(
                    WorkflowTaskModel.process_instance_id == instance.id,
                    WorkflowTaskModel.status.in_(("active", "pending")),
                )
                .with_for_update()
            )
        ).all()
        for task in tasks:
            task.status = "cancelled"
            task.decision = "cancel"
            task.decision_comment = reason
            task.completed_at = now
            task.revision += 1
        instance.status = "cancelled"
        instance.cancelled_at = now
        instance.revision += 1
        await self._history(session, instance.id, actor_id, "cancel", reason)
        await self._event(
            session,
            EventName.PROCESS_INSTANCE_CANCELLED,
            "processInstance",
            instance.id,
            {"processInstanceId": str(instance.id), "reason": reason},
        )

    async def complete_linked_instance(
        self,
        session: AsyncSession,
        process_instance_id: UUID,
        actor_id: UUID,
        summary: str,
    ) -> None:
        """Finish a linked process when the terminal business invariant is satisfied."""
        instance = await session.get(
            ProcessInstanceModel, process_instance_id, with_for_update=True
        )
        if instance is None:
            raise ResourceNotFoundError("process instance", process_instance_id)
        if instance.status == "completed":
            return
        now = utc_now()
        tasks = (
            await session.scalars(
                select(WorkflowTaskModel)
                .where(
                    WorkflowTaskModel.process_instance_id == instance.id,
                    WorkflowTaskModel.status.in_(("active", "pending")),
                )
                .with_for_update()
            )
        ).all()
        for task in tasks:
            task.status = "completed"
            task.decision = "complete"
            task.decision_comment = summary
            task.completed_at = now
            task.revision += 1
            await self._event(
                session,
                EventName.WORKFLOW_TASK_COMPLETED,
                "workflowTask",
                task.id,
                {"taskId": str(task.id), "processInstanceId": str(instance.id)},
            )
        instance.status = "completed"
        instance.completed_at = now
        instance.revision += 1
        await self._history(session, instance.id, actor_id, "complete", summary)
        await self._event(
            session,
            EventName.PROCESS_INSTANCE_COMPLETED,
            "processInstance",
            instance.id,
            {"processInstanceId": str(instance.id)},
        )

    async def reassign_task(
        self, task_id: UUID, actor_id: UUID, revision: int, assigned_user_id: UUID, reason: str
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            task = await session.get(WorkflowTaskModel, task_id, with_for_update=True)
            if task is None:
                raise ResourceNotFoundError("workflow task", task_id)
            self._revision(task.revision, revision)
            if task.assigned_user_id != actor_id:
                raise ValidationError(
                    "Only the assigned actor may delegate the task.",
                    code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED,
                )
            current = await session.scalar(
                select(UserAccountModel).where(UserAccountModel.id == actor_id)
            )
            target = await session.scalar(
                select(UserAccountModel).where(UserAccountModel.id == assigned_user_id)
            )
            if (
                current is None
                or target is None
                or current.employee_id is None
                or target.employee_id is None
            ):
                raise ValidationError(
                    "Delegate cannot be resolved.", code=ErrorCode.PROCESS_ACTOR_UNRESOLVED
                )
            now = utc_now()
            delegation = await session.scalar(
                select(DelegationModel).where(
                    DelegationModel.delegator_employee_id == current.employee_id,
                    DelegationModel.delegate_employee_id == target.employee_id,
                    DelegationModel.status != "revoked",
                    DelegationModel.effective_from <= now,
                    DelegationModel.effective_to > now,
                    DelegationModel.delegated_permissions.contains(["workflow.task.act"]),
                )
            )
            if delegation is None:
                raise ValidationError(
                    "No valid delegation exists.", code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED
                )
            task.assigned_user_id = assigned_user_id
            task.revision += 1
            await self._history(
                session,
                task.process_instance_id,
                actor_id,
                "taskReassigned",
                "Task reassigned.",
                {"reason": reason},
            )
            return _task_view(task)

    async def _create_tasks(
        self,
        session: AsyncSession,
        instance: ProcessInstanceModel,
        step: ProcessStepDefinitionModel,
    ) -> list[WorkflowTaskModel]:
        users = await self._resolve_users(session, instance, step)
        if len(users) < step.required_approvers:
            instance.status = "configuration_error"
            instance.revision += 1
            await self._history(
                session,
                instance.id,
                instance.initiator_user_id,
                "configurationError",
                "Workflow actor could not be resolved.",
            )
            await self._record(
                session,
                instance.initiator_user_id,
                instance.organization_id,
                "workflow.actor.unresolved",
                "processInstance",
                instance.id,
                {"stepId": str(step.id)},
            )
            return []
        selected = (
            users
            if step.step_type == StepType.PARALLEL_TASK.value
            else users[: max(1, step.required_approvers)]
        )
        rows: list[WorkflowTaskModel] = []
        for user_id in selected:
            account = await session.get(UserAccountModel, user_id)
            row = WorkflowTaskModel(
                process_instance_id=instance.id,
                step_definition_id=step.id,
                assigned_user_id=user_id,
                assigned_employee_id=account.employee_id if account else None,
                status="active",
                due_at=utc_now() + timedelta(seconds=step.due_duration_seconds)
                if step.due_duration_seconds
                else None,
                created_at=utc_now(),
            )
            session.add(row)
            rows.append(row)
        await session.flush()
        for row in rows:
            await self._event(
                session,
                EventName.WORKFLOW_TASK_ASSIGNED,
                "workflowTask",
                row.id,
                {"taskId": str(row.id), "processInstanceId": str(instance.id)},
            )
        return rows

    async def _resolve_users(
        self,
        session: AsyncSession,
        instance: ProcessInstanceModel,
        step: ProcessStepDefinitionModel,
    ) -> list[UUID]:
        if step.actor_rule_id is None:
            return [instance.initiator_user_id]
        rule = await session.get(ActorRuleModel, step.actor_rule_id)
        if rule is None or not rule.active:
            return []
        context = cast(Mapping[str, Any], instance.snapshot.get("context", {}))
        if rule.rule_type == "process_initiator":
            return [instance.initiator_user_id]
        if rule.rule_type == "explicit_user":
            configured = [
                UUID(str(value))
                for value in cast(Sequence[object], rule.configuration.get("userIds", []))
            ]
            if not configured:
                return []
            return list(
                (
                    await session.scalars(
                        select(UserAccountModel.id)
                        .where(
                            UserAccountModel.id.in_(configured),
                            UserAccountModel.active.is_(True),
                        )
                        .order_by(UserAccountModel.id)
                    )
                ).all()
            )
        if rule.rule_type == "subject_employee":
            employee_id = context.get("subjectEmployeeId")
            if employee_id:
                user = await session.scalar(
                    select(UserAccountModel.id).where(
                        UserAccountModel.employee_id == UUID(str(employee_id)),
                        UserAccountModel.active.is_(True),
                    )
                )
                return [user] if user else []
            return []
        permission = rule.configuration.get("permissionCode")
        if (
            rule.rule_type
            in {"permission_holder", "functional_role", "signing_authority", "organization_role"}
            and permission
        ):
            now = utc_now()
            target_unit = context.get("unitId") or context.get("requestingUnitId")
            scope_conditions = [
                AccessScopeModel.scope_type == "organization",
                AccessScopeModel.scope_type == "global",
            ]
            if target_unit:
                scope_conditions.append(AccessScopeUnitModel.unit_id == UUID(str(target_unit)))
            statement = (
                select(UserRoleAssignmentModel.user_id)
                .join(
                    RolePermissionModel,
                    RolePermissionModel.role_id == UserRoleAssignmentModel.role_id,
                )
                .join(PermissionModel, PermissionModel.id == RolePermissionModel.permission_id)
                .join(AccessScopeModel, AccessScopeModel.id == UserRoleAssignmentModel.scope_id)
                .outerjoin(
                    AccessScopeUnitModel,
                    AccessScopeUnitModel.scope_id == AccessScopeModel.id,
                )
                .where(
                    PermissionModel.code == str(permission),
                    PermissionModel.active.is_(True),
                    AccessScopeModel.organization_id == instance.organization_id,
                    or_(*scope_conditions),
                    UserRoleAssignmentModel.revoked_at.is_(None),
                    UserRoleAssignmentModel.effective_from <= now,
                    or_(
                        UserRoleAssignmentModel.effective_to.is_(None),
                        UserRoleAssignmentModel.effective_to > now,
                    ),
                )
                .distinct()
                .order_by(UserRoleAssignmentModel.user_id)
            )
            return list((await session.scalars(statement)).all())
        if rule.rule_type == "commission_members":
            configured = [
                UUID(str(value))
                for value in cast(Sequence[object], context.get("commissionUserIds", []))
            ]
            if not configured:
                return []
            return list(
                (
                    await session.scalars(
                        select(UserAccountModel.id)
                        .where(
                            UserAccountModel.id.in_(configured),
                            UserAccountModel.active.is_(True),
                        )
                        .order_by(UserAccountModel.id)
                    )
                ).all()
            )
        return []

    async def _clone(self, session: AsyncSession, source: UUID, target: UUID) -> None:
        rules = (
            await session.scalars(
                select(ActorRuleModel).where(ActorRuleModel.definition_version_id == source)
            )
        ).all()
        rule_map: dict[UUID, UUID] = {}
        for rule_item in rules:
            rule_clone = ActorRuleModel(
                definition_version_id=target,
                code=rule_item.code,
                name=rule_item.name,
                rule_type=rule_item.rule_type,
                configuration=rule_item.configuration,
                active=rule_item.active,
            )
            session.add(rule_clone)
            await session.flush()
            rule_map[rule_item.id] = rule_clone.id
        steps = (
            await session.scalars(
                select(ProcessStepDefinitionModel).where(
                    ProcessStepDefinitionModel.definition_version_id == source
                )
            )
        ).all()
        step_map: dict[UUID, UUID] = {}
        for step_item in steps:
            step_clone = ProcessStepDefinitionModel(
                definition_version_id=target,
                stable_key=step_item.stable_key,
                code=step_item.code,
                name=step_item.name,
                step_type=step_item.step_type,
                sequence=step_item.sequence,
                actor_rule_id=rule_map.get(step_item.actor_rule_id)
                if step_item.actor_rule_id
                else None,
                allowed_actions=step_item.allowed_actions,
                due_duration_seconds=step_item.due_duration_seconds,
                required_document_type_ids=step_item.required_document_type_ids,
                configuration=step_item.configuration,
                completion_mode=step_item.completion_mode,
                required_approvers=step_item.required_approvers,
                active=step_item.active,
            )
            session.add(step_clone)
            await session.flush()
            step_map[step_item.id] = step_clone.id
        transitions = (
            await session.scalars(
                select(ProcessTransitionDefinitionModel).where(
                    ProcessTransitionDefinitionModel.definition_version_id == source
                )
            )
        ).all()
        for transition_item in transitions:
            session.add(
                ProcessTransitionDefinitionModel(
                    definition_version_id=target,
                    source_step_id=step_map[transition_item.source_step_id],
                    target_step_id=step_map[transition_item.target_step_id],
                    action=transition_item.action,
                    condition=transition_item.condition,
                    priority=transition_item.priority,
                    active=transition_item.active,
                )
            )

    async def _problems(
        self, session: AsyncSession, version_id: UUID
    ) -> tuple[ConfigurationProblem, ...]:
        rows = (
            await session.scalars(
                select(ProcessStepDefinitionModel).where(
                    ProcessStepDefinitionModel.definition_version_id == version_id
                )
            )
        ).all()
        transitions = (
            await session.scalars(
                select(ProcessTransitionDefinitionModel).where(
                    ProcessTransitionDefinitionModel.definition_version_id == version_id
                )
            )
        ).all()
        steps = [
            ProcessStepDefinition(
                definition_version_id=row.definition_version_id,
                stable_key=row.stable_key,
                code=row.code,
                name=row.name,
                step_type=StepType(row.step_type),
                sequence=row.sequence,
                actor_rule_id=row.actor_rule_id,
                allowed_actions=tuple(row.allowed_actions),
                due_duration=timedelta(seconds=row.due_duration_seconds)
                if row.due_duration_seconds
                else None,
                required_document_type_ids=tuple(
                    UUID(item) for item in row.required_document_type_ids
                ),
                configuration=row.configuration,
                completion_mode=CompletionMode(row.completion_mode),
                required_approvers=row.required_approvers,
                active=row.active,
                revision=row.revision,
                id=row.id,
            )
            for row in rows
        ]
        domain_transitions = [
            ProcessTransitionDefinition(
                definition_version_id=row.definition_version_id,
                source_step_id=row.source_step_id,
                target_step_id=row.target_step_id,
                action=row.action,
                condition=row.condition,
                priority=row.priority,
                active=row.active,
                id=row.id,
            )
            for row in transitions
        ]
        return validate_definition(steps, domain_transitions)

    async def _transition_version(
        self,
        version_id: UUID,
        actor_id: UUID,
        revision: int,
        reason: str,
        source: str,
        target: str,
        action: str,
    ) -> WorkflowView:
        async with self._sessions.begin() as session:
            version = await self._version(session, version_id)
            self._revision(version.revision, revision)
            if version.status != source:
                raise ValidationError(
                    "The definition version is in the wrong state.",
                    code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED,
                )
            if target == "in_review" and await self._problems(session, version_id):
                raise ValidationError(
                    "Invalid workflow cannot be reviewed.",
                    code=ErrorCode.PROCESS_CONFIGURATION_INVALID,
                )
            version.status = target
            version.revision += 1
            await self._record_for_version(
                session,
                actor_id,
                version,
                action,
                "processDefinitionVersion",
                version.id,
                _version_view(version),
                reason,
            )
            return _version_view(version)

    async def _version(
        self, session: AsyncSession, version_id: UUID
    ) -> ProcessDefinitionVersionModel:
        row = await session.get(ProcessDefinitionVersionModel, version_id)
        if row is None:
            raise ResourceNotFoundError("process definition version", version_id)
        return row

    async def _draft(
        self, session: AsyncSession, version_id: UUID
    ) -> ProcessDefinitionVersionModel:
        row = await self._version(session, version_id)
        if row.status != "draft":
            raise ValidationError(
                "Only drafts are editable.", code=ErrorCode.PROCESS_ACTION_NOT_ALLOWED
            )
        return row

    async def _version_detail(
        self, session: AsyncSession, version: ProcessDefinitionVersionModel
    ) -> WorkflowView:
        result = _version_view(version)
        result["actorRules"] = [
            _actor_rule_view(item)
            for item in (
                await session.scalars(
                    select(ActorRuleModel).where(ActorRuleModel.definition_version_id == version.id)
                )
            ).all()
        ]
        result["steps"] = [
            _step_view(item)
            for item in (
                await session.scalars(
                    select(ProcessStepDefinitionModel)
                    .where(ProcessStepDefinitionModel.definition_version_id == version.id)
                    .order_by(ProcessStepDefinitionModel.sequence)
                )
            ).all()
        ]
        result["transitions"] = [
            _transition_view(item)
            for item in (
                await session.scalars(
                    select(ProcessTransitionDefinitionModel).where(
                        ProcessTransitionDefinitionModel.definition_version_id == version.id
                    )
                )
            ).all()
        ]
        return result

    async def _touch(self, version: ProcessDefinitionVersionModel) -> None:
        version.revision += 1

    def _revision(self, actual: int, expected: int) -> None:
        if actual != expected:
            raise ConcurrencyConflictError(
                details={"expectedRevision": expected, "actualRevision": actual}
            )

    async def _record_for_version(
        self,
        session: AsyncSession,
        actor: UUID,
        version: ProcessDefinitionVersionModel,
        action: str,
        entity_type: str,
        entity_id: UUID,
        after: Mapping[str, Any],
        reason: str | None = None,
    ) -> None:
        definition = await session.get(ProcessDefinitionModel, version.process_definition_id)
        if definition is None:
            raise ResourceNotFoundError("process definition", version.process_definition_id)
        await self._record(
            session,
            actor,
            definition.organization_id,
            action,
            entity_type,
            entity_id,
            after,
            reason,
        )

    async def _record(
        self,
        session: AsyncSession,
        actor: UUID,
        organization: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        after: Mapping[str, Any],
        reason: str | None = None,
    ) -> None:
        await AuditService(SqlAlchemyAuditLog(session)).record(
            actor_id=actor,
            organization_id=organization,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            after_state=after,
            reason=reason,
        )

    async def _event(
        self,
        session: AsyncSession,
        name: EventName,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: Mapping[str, Any],
    ) -> None:
        await SqlAlchemyTransactionalOutbox(session).append(
            ApplicationEvent(
                name=name, aggregate_type=aggregate_type, aggregate_id=aggregate_id, payload=payload
            )
        )

    async def _history(
        self,
        session: AsyncSession,
        instance_id: UUID,
        actor: UUID | None,
        event_type: str,
        summary: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        session.add(
            ProcessHistoryEntryModel(
                process_instance_id=instance_id,
                event_type=event_type,
                actor_user_id=actor,
                summary=summary,
                metadata_=dict(metadata or {}),
                occurred_at=utc_now(),
            )
        )


def _definition_view(row: ProcessDefinitionModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "active": row.active,
    }


def _version_view(row: ProcessDefinitionVersionModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "processDefinitionId": row.process_definition_id,
        "versionNumber": row.version_number,
        "name": row.name,
        "status": row.status,
        "basedOnVersionId": row.based_on_version_id,
        "effectiveFrom": row.effective_from,
        "effectiveTo": row.effective_to,
        "revision": row.revision,
    }


def _actor_rule_view(row: ActorRuleModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "definitionVersionId": row.definition_version_id,
        "code": row.code,
        "name": row.name,
        "ruleType": row.rule_type,
        "configuration": row.configuration,
        "active": row.active,
        "revision": row.revision,
    }


def _step_view(row: ProcessStepDefinitionModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "definitionVersionId": row.definition_version_id,
        "stableKey": row.stable_key,
        "code": row.code,
        "name": row.name,
        "stepType": row.step_type,
        "sequence": row.sequence,
        "actorRuleId": row.actor_rule_id,
        "allowedActions": row.allowed_actions,
        "dueDurationSeconds": row.due_duration_seconds,
        "requiredDocumentTypeIds": row.required_document_type_ids,
        "configuration": row.configuration,
        "completionMode": row.completion_mode,
        "requiredApprovers": row.required_approvers,
        "active": row.active,
        "revision": row.revision,
    }


def _transition_view(row: ProcessTransitionDefinitionModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "definitionVersionId": row.definition_version_id,
        "sourceStepId": row.source_step_id,
        "targetStepId": row.target_step_id,
        "action": row.action,
        "condition": row.condition,
        "priority": row.priority,
        "active": row.active,
    }


def _instance_view(row: ProcessInstanceModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "processDefinitionId": row.process_definition_id,
        "definitionVersionId": row.definition_version_id,
        "businessType": row.business_type,
        "businessEntityId": row.business_entity_id,
        "initiatorUserId": row.initiator_user_id,
        "status": row.status,
        "currentPhase": row.current_phase,
        "startedAt": row.started_at,
        "completedAt": row.completed_at,
        "cancelledAt": row.cancelled_at,
        "revision": row.revision,
    }


def _task_view(row: WorkflowTaskModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "processInstanceId": row.process_instance_id,
        "stepDefinitionId": row.step_definition_id,
        "assignedUserId": row.assigned_user_id,
        "assignedEmployeeId": row.assigned_employee_id,
        "assignedUnitId": row.assigned_unit_id,
        "status": row.status,
        "dueAt": row.due_at,
        "decision": row.decision,
        "decisionComment": row.decision_comment,
        "createdAt": row.created_at,
        "completedAt": row.completed_at,
        "revision": row.revision,
    }


def _history_view(row: ProcessHistoryEntryModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "processInstanceId": row.process_instance_id,
        "eventType": row.event_type,
        "actorUserId": row.actor_user_id,
        "summary": row.summary,
        "metadata": row.metadata_,
        "occurredAt": row.occurred_at,
    }


def _form_definition_view(row: FormDefinitionModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "code": row.code,
        "name": row.name,
        "active": row.active,
    }


def _form_version_view(row: FormDefinitionVersionModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "formDefinitionId": row.form_definition_id,
        "versionNumber": row.version_number,
        "status": row.status,
        "basedOnVersionId": row.based_on_version_id,
        "revision": row.revision,
        "createdBy": row.created_by,
        "publishedBy": row.published_by,
        "createdAt": row.created_at,
        "publishedAt": row.published_at,
    }


def _form_field_view(row: FormFieldDefinitionModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "formVersionId": row.form_version_id,
        "code": row.code,
        "label": row.label,
        "fieldType": row.field_type,
        "required": row.required,
        "validationRules": row.validation_rules,
        "referenceDataSource": row.reference_data_source,
        "visibilityRule": row.visibility_rule,
        "editabilityRule": row.editability_rule,
        "confidentiality": row.confidentiality,
        "ordering": row.ordering,
        "helpText": row.help_text,
        "revision": row.revision,
    }


def _form_submission_view(row: FormSubmissionModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "organizationId": row.organization_id,
        "formVersionId": row.form_version_id,
        "processInstanceId": row.process_instance_id,
        "businessEntityType": row.business_entity_type,
        "businessEntityId": row.business_entity_id,
        "submittedBy": row.submitted_by,
        "data": row.data,
        "submittedAt": row.submitted_at,
        "revision": row.revision,
    }


def _condition_matches(condition: Mapping[str, Any] | None, context: Mapping[str, Any]) -> bool:
    if condition is None:
        return True
    operator, expression = next(iter(condition.items()))
    if operator in {"and", "or"}:
        values = [_condition_matches(cast(Mapping[str, Any], item), context) for item in expression]
        return all(values) if operator == "and" else any(values)
    field = str(expression["field"])
    current: Any = context
    for part in field.split("."):
        if not isinstance(current, Mapping) or part not in current:
            current = None
            break
        current = current[part]
    if operator == "exists":
        return current is not None
    expected = expression.get("value")
    if operator == "eq":
        return bool(current == expected)
    if operator == "ne":
        return bool(current != expected)
    if operator == "in":
        return current in expected if isinstance(expected, Sequence) else False
    if operator == "not_in":
        return current not in expected if isinstance(expected, Sequence) else False
    if current is None:
        return False
    if operator == "gt":
        return bool(current > expected)
    if operator == "gte":
        return bool(current >= expected)
    if operator == "lt":
        return bool(current < expected)
    if operator == "lte":
        return bool(current <= expected)
    return False


def _json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    return value
