from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.core.errors import ResourceNotFoundError, ValidationError
from app.modules.documents.infrastructure.models import DocumentTypeModel
from app.modules.documents.infrastructure.operations import SqlAlchemyDocumentOperations
from app.modules.employees.infrastructure.crypto import FernetSensitiveDataProtector
from app.modules.recruitment.infrastructure.operations import SqlAlchemyRecruitmentOperations
from app.modules.termination.infrastructure.operations import SqlAlchemyTerminationOperations
from app.modules.workflow.infrastructure.models import ProcessInstanceModel, WorkflowTaskModel
from app.modules.workflow.infrastructure.operations import SqlAlchemyWorkflowOperations
from app.seed import ORGANIZATION_ID, _development_user_id, _seed_id
from cryptography.fernet import Fernet
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integration


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_seeded_workflow_routes_validate_and_run_sequentially(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyWorkflowOperations(factory)
    async with factory() as session:
        versions = (
            (
                await session.execute(
                    text("SELECT id FROM process_definition_versions WHERE status = 'published'")
                )
            )
            .scalars()
            .all()
        )
    for version_id in versions:
        assert (
            await operations.validate_version(UUID(str(version_id)), _development_user_id("admin"))
            == ()
        )

    instance = await operations.start_instance(
        ORGANIZATION_ID,
        _development_user_id("admin"),
        {
            "definitionCode": "recruitment",
            "businessType": "integrationRecruitment",
            "businessEntityId": uuid4(),
            "context": {},
        },
    )
    async with factory() as session:
        task = await session.scalar(
            select(WorkflowTaskModel).where(
                WorkflowTaskModel.process_instance_id == instance["id"],
                WorkflowTaskModel.status == "active",
            )
        )
        assert task is not None and task.assigned_user_id is not None
        actor_id, task_id, revision = task.assigned_user_id, task.id, task.revision
    completed = await operations.act_task(
        task_id, actor_id, revision, "approve", "complete", "workflow-integration-1"
    )
    duplicate = await operations.act_task(
        task_id, actor_id, revision, "approve", "complete", "workflow-integration-1"
    )
    assert completed["status"] == "completed"
    assert duplicate["id"] == completed["id"]
    refreshed = await operations.get_instance(UUID(str(instance["id"])))
    assert refreshed["definitionVersionId"] == instance["definitionVersionId"]
    assert refreshed["currentPhase"] == "staffing_review"


@pytest.mark.asyncio
async def test_parallel_workflow_waits_for_all_required_approvers(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyWorkflowOperations(factory)
    actor = _development_user_id("admin")
    definition = await operations.create_definition(
        ORGANIZATION_ID,
        actor,
        {"code": f"parallel-{uuid4().hex[:8]}", "name": "Parallel integration"},
    )
    version = await operations.create_draft(UUID(str(definition["id"])), actor, None, "Parallel v1")
    rule = await operations.save_actor_rule(
        UUID(str(version["id"])),
        actor,
        {
            "code": "parallel_approvers",
            "name": "Parallel approvers",
            "ruleType": "explicit_user",
            "configuration": {"userIds": [str(actor), str(_development_user_id("hr"))]},
        },
    )
    await operations.save_step(
        UUID(str(version["id"])),
        actor,
        {
            "code": "parallel",
            "name": "Parallel approval",
            "stepType": "parallel_task",
            "sequence": 0,
            "actorRuleId": rule["id"],
            "allowedActions": ["approve", "reject"],
            "completionMode": "all",
            "requiredApprovers": 2,
        },
    )
    detail = await operations.get_version(UUID(str(version["id"])))
    await operations.publish(
        UUID(str(version["id"])), actor, int(detail["revision"]), "integration publish"
    )
    instance = await operations.start_instance(
        ORGANIZATION_ID,
        actor,
        {
            "definitionCode": definition["code"],
            "businessType": "parallelIntegration",
            "businessEntityId": uuid4(),
        },
    )
    async with factory() as session:
        tasks = (
            await session.scalars(
                select(WorkflowTaskModel)
                .where(WorkflowTaskModel.process_instance_id == instance["id"])
                .order_by(WorkflowTaskModel.assigned_user_id)
            )
        ).all()
    assert len(tasks) == 2
    await operations.act_task(
        tasks[0].id,
        tasks[0].assigned_user_id,
        tasks[0].revision,
        "approve",
        None,
        f"parallel-{tasks[0].id}",
    )
    assert (await operations.get_instance(UUID(str(instance["id"]))))["status"] == "active"
    await operations.act_task(
        tasks[1].id,
        tasks[1].assigned_user_id,
        tasks[1].revision,
        "approve",
        None,
        f"parallel-{tasks[1].id}",
    )
    assert (await operations.get_instance(UUID(str(instance["id"]))))["status"] == "completed"


@pytest.mark.asyncio
async def test_unresolved_workflow_actor_persists_configuration_error_and_audit(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyWorkflowOperations(factory)
    actor = _development_user_id("admin")
    code = f"unresolved-{uuid4().hex[:8]}"
    definition = await operations.create_definition(
        ORGANIZATION_ID, actor, {"code": code, "name": "Unresolved actor integration"}
    )
    version = await operations.create_draft(
        UUID(str(definition["id"])), actor, None, "Unresolved v1"
    )
    rule = await operations.save_actor_rule(
        UUID(str(version["id"])),
        actor,
        {
            "code": "missing_user",
            "name": "Missing user",
            "ruleType": "explicit_user",
            "configuration": {"userIds": [str(uuid4())]},
        },
    )
    await operations.save_step(
        UUID(str(version["id"])),
        actor,
        {
            "code": "approval",
            "name": "Approval",
            "stepType": "approval",
            "sequence": 0,
            "actorRuleId": rule["id"],
            "allowedActions": ["approve"],
            "completionMode": "all",
            "requiredApprovers": 1,
        },
    )
    detail = await operations.get_version(UUID(str(version["id"])))
    await operations.publish(
        UUID(str(version["id"])), actor, int(detail["revision"]), "integration publish"
    )
    with pytest.raises(ValidationError) as error:
        await operations.start_instance(
            ORGANIZATION_ID,
            actor,
            {
                "definitionCode": code,
                "businessType": "unresolvedIntegration",
                "businessEntityId": uuid4(),
            },
        )
    assert error.value.code.value == "PROCESS_ACTOR_UNRESOLVED"
    async with factory() as session:
        status = await session.scalar(
            text(
                "SELECT i.status FROM process_instances i "
                "JOIN process_definitions d ON d.id=i.process_definition_id "
                "WHERE d.code=:code"
            ),
            {"code": code},
        )
        audit_count = await session.scalar(
            text("SELECT count(*) FROM audit_events WHERE action='workflow.actor.unresolved'")
        )
    assert status == "configuration_error"
    assert int(audit_count or 0) >= 1


@pytest.mark.asyncio
async def test_versioned_form_submission_uses_process_snapshot_and_validates_fields(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyWorkflowOperations(factory)
    actor = _development_user_id("admin")
    form = await operations.create_form_definition(
        ORGANIZATION_ID,
        actor,
        {"code": f"candidate-{uuid4().hex[:8]}", "name": "Candidate form"},
    )
    version = await operations.create_form_draft(UUID(str(form["id"])), actor, None)
    await operations.save_form_field(
        UUID(str(version["id"])),
        actor,
        {
            "code": "motivation",
            "label": "Motivation",
            "fieldType": "text",
            "required": True,
            "validationRules": {"minLength": 3, "maxLength": 100},
            "confidentiality": "confidential",
            "ordering": 0,
        },
    )
    version_detail_revision = int(version["revision"]) + 1
    published = await operations.publish_form_version(
        UUID(str(version["id"])), actor, version_detail_revision, "integration publish"
    )
    instance = await operations.start_instance(
        ORGANIZATION_ID,
        actor,
        {
            "definitionCode": "recruitment",
            "businessType": "formIntegration",
            "businessEntityId": uuid4(),
            "context": {"formVersionIds": [str(published["id"])]},
        },
    )
    payload = {
        "formVersionId": published["id"],
        "processInstanceId": instance["id"],
        "businessEntityType": "candidateApplication",
        "businessEntityId": uuid4(),
        "data": {"motivation": "Build useful systems"},
    }
    submission = await operations.submit_form(ORGANIZATION_ID, actor, payload)
    assert submission["formVersionId"] == published["id"]
    assert submission["processInstanceId"] == instance["id"]
    with pytest.raises(ValidationError):
        await operations.submit_form(
            ORGANIZATION_ID,
            actor,
            {**payload, "businessEntityId": uuid4(), "data": {}},
        )
    async with factory() as session:
        audit_after = await session.scalar(
            text(
                "SELECT after_state FROM audit_events "
                "WHERE action='workflow.form.submitted' ORDER BY occurred_at DESC LIMIT 1"
            )
        )
    assert audit_after["data"] == "[redacted]"


@pytest.mark.asyncio
async def test_recruitment_to_hiring_completion_is_transactional(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyRecruitmentOperations(
        factory, FernetSensitiveDataProtector(Fernet.generate_key().decode("ascii"))
    )
    director_user = _development_user_id("director")
    director_employee = _seed_id("employee", "development-director")
    slot_id = _seed_id("staffing-slot", "stabilization-specialist-vacancy")
    async with factory() as session:
        slot = (
            await session.execute(
                text(
                    "SELECT organization_unit_id, position_definition_id "
                    "FROM staffing_slots WHERE id=:id"
                ),
                {"id": slot_id},
            )
        ).one()
        channel_id = UUID(
            str(
                await session.scalar(
                    text("SELECT id FROM vacancy_publication_channels WHERE code='internal_board'")
                )
            )
        )
    request = await operations.create_request(
        ORGANIZATION_ID,
        director_user,
        {
            "requestingUnitId": slot.organization_unit_id,
            "requestedByEmployeeId": director_employee,
            "staffingSlotId": slot_id,
            "positionDefinitionId": slot.position_definition_id,
            "requestedFte": "1.0",
            "employmentType": "permanent",
            "desiredStartDate": date.today() + timedelta(days=14),
            "reason": "Integration vacancy",
            "responsibilities": "Integration responsibilities",
            "requirements": "Integration requirements",
        },
    )
    hr_revision = int(request["revision"])
    request = await operations.review_request(
        UUID(str(request["id"])),
        _development_user_id("hr"),
        hr_revision,
        "approve",
        "complete",
    )
    duplicate = await operations.review_request(
        UUID(str(request["id"])),
        _development_user_id("hr"),
        hr_revision,
        "approve",
        "complete",
    )
    assert duplicate["revision"] == request["revision"]
    async with factory() as session:
        process = await session.get(ProcessInstanceModel, request["process_instance_id"])
        tasks = (
            await session.scalars(
                select(WorkflowTaskModel)
                .where(WorkflowTaskModel.process_instance_id == request["process_instance_id"])
                .order_by(WorkflowTaskModel.created_at)
            )
        ).all()
    assert process is not None and process.current_phase == "staffing_review"
    assert [task.status for task in tasks] == ["completed", "active"]
    request = await operations.review_request(
        UUID(str(request["id"])),
        _development_user_id("admin"),
        int(request["revision"]),
        "approve",
        "capacity and budget confirmed",
        {"vacantSlotConfirmed": True, "approvedFte": "1.0", "budgetConfirmed": True},
    )
    vacancy = await operations.create_vacancy(
        UUID(str(request["id"])),
        _development_user_id("hr"),
        {
            "code": f"INT-{uuid4().hex[:10]}",
            "title": "Integration specialist",
            "description": "Integration",
        },
    )
    vacancy = await operations.publish_vacancy(
        UUID(str(vacancy["id"])),
        _development_user_id("hr"),
        int(vacancy["revision"]),
        {"channelId": channel_id, "responsibleEmployeeId": director_employee},
    )
    candidate = await operations.create_candidate(
        ORGANIZATION_ID,
        _development_user_id("hr"),
        {
            "firstName": "Integration",
            "lastName": "Candidate",
            "displayName": "Integration Candidate",
            "personalEmail": "candidate@example.invalid",
            "source": "integration",
            "consentStatus": "granted",
            "retentionUntil": date.today() + timedelta(days=365),
        },
    )
    application = await operations.create_application(
        _development_user_id("hr"),
        {"candidateId": candidate["id"], "vacancyId": vacancy["id"], "source": "integration"},
    )
    application = await operations.screen(
        UUID(str(application["id"])),
        _development_user_id("hr"),
        int(application["revision"]),
        {"decision": "advance", "criteriaResults": [{"code": "experience", "passed": True}]},
    )
    interview = await operations.schedule_interview(
        UUID(str(application["id"])),
        _development_user_id("hr"),
        {
            "roundNumber": 1,
            "scheduledAt": datetime.now(UTC) + timedelta(days=1),
            "format": "online",
            "participants": [
                {"employeeId": director_employee, "role": "manager", "required": True}
            ],
        },
    )
    await operations.evaluate_interview(
        UUID(str(interview["id"])),
        director_user,
        {
            "interviewerEmployeeId": director_employee,
            "criteriaResults": [{"code": "fit", "score": 5}],
            "recommendation": "recommended",
            "comment": "passed",
        },
    )
    with pytest.raises(Exception) as immutable_evaluation:
        await operations.evaluate_interview(
            UUID(str(interview["id"])),
            director_user,
            {
                "interviewerEmployeeId": director_employee,
                "criteriaResults": [],
                "recommendation": "changed",
            },
        )
    assert (
        getattr(immutable_evaluation.value, "code", None).value
        == "INTERVIEW_EVALUATION_ALREADY_SUBMITTED"
    )
    commission = await operations.create_commission(
        ORGANIZATION_ID,
        _development_user_id("hr"),
        {
            "code": f"INT-{uuid4().hex[:8]}",
            "meetingAt": datetime.now(UTC),
            "quorumRequired": 1,
            "members": [{"employeeId": director_employee, "role": "chair"}],
        },
    )
    await operations.record_commission_decision(
        UUID(str(application["id"])),
        _development_user_id("admin"),
        {"commissionId": commission["id"], "decision": "recommended", "comment": "quorum reached"},
    )
    offer = await operations.create_offer(
        UUID(str(application["id"])),
        _development_user_id("hr"),
        {
            "proposedConditions": {"employmentType": "permanent"},
            "proposedStartDate": date.today(),
            "expirationDate": date.today() + timedelta(days=7),
        },
    )
    await operations.respond_offer(
        UUID(str(offer["id"])), _development_user_id("hr"), int(offer["revision"]), True, None
    )
    hiring = await operations.start_hiring(
        UUID(str(application["id"])), _development_user_id("hr"), {}
    )
    with pytest.raises(Exception) as incomplete:
        await operations.complete_hiring(
            UUID(str(hiring["id"])),
            _development_user_id("hr"),
            int(hiring["revision"]),
            {"employeeNumber": f"BLOCK-{uuid4().hex[:10]}"},
        )
    assert getattr(incomplete.value, "code", None).value == "HIRING_DOCUMENTS_INCOMPLETE"
    documents = SqlAlchemyDocumentOperations(factory)
    async with factory() as session:
        document_type_id = await session.scalar(
            select(DocumentTypeModel.id).where(DocumentTypeModel.code == "employment_contract")
        )
    assert document_type_id is not None
    await documents.create_checklist_item(
        ORGANIZATION_ID,
        _development_user_id("hr"),
        {
            "businessEntityType": "hiringCase",
            "businessEntityId": hiring["id"],
            "documentTypeId": document_type_id,
            "mandatory": True,
            "status": "validated",
        },
    )
    onboarding = await operations.create_onboarding_task(
        UUID(str(hiring["id"])),
        _development_user_id("hr"),
        {"taskType": "account_provisioning", "assignedEmployeeId": director_employee},
    )
    await operations.complete_onboarding_task(
        UUID(str(onboarding["id"])),
        director_user,
        int(onboarding["revision"]),
        {"reference": "INT"},
    )
    completed = await operations.complete_hiring(
        UUID(str(hiring["id"])),
        _development_user_id("hr"),
        int(hiring["revision"]),
        {"employeeNumber": f"INT-{uuid4().hex[:12]}", "fullTimeEquivalent": "1.0"},
    )
    assert completed["status"] == "completed"
    async with factory() as session:
        hiring_process = await session.get(ProcessInstanceModel, completed["process_instance_id"])
        pending_workflow_tasks = int(
            await session.scalar(
                select(func.count())
                .select_from(WorkflowTaskModel)
                .where(
                    WorkflowTaskModel.process_instance_id == completed["process_instance_id"],
                    WorkflowTaskModel.status.in_(("active", "pending")),
                )
            )
            or 0
        )
        result = (
            await session.execute(
                text(
                    "SELECT v.publication_status, a.status, e.active FROM vacancies v "
                    "JOIN candidate_applications a ON a.vacancy_id=v.id "
                    "JOIN hiring_cases h ON h.candidate_application_id=a.id "
                    "JOIN employees e ON e.id=h.employee_id WHERE h.id=:id"
                ),
                {"id": completed["id"]},
            )
        ).one()
        safe_events = (
            (
                await session.execute(
                    text("SELECT payload::text FROM outbox_events WHERE aggregate_id=:id"),
                    {"id": completed["id"]},
                )
            )
            .scalars()
            .all()
        )
    assert tuple(result) == ("filled", "hired", True)
    assert hiring_process is not None and hiring_process.status == "completed"
    assert pending_workflow_tasks == 0
    assert all("candidate@example.invalid" not in payload for payload in safe_events)


@pytest.mark.asyncio
async def test_termination_keeps_assignment_until_effective_completion(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyTerminationOperations(factory)
    employee_id = _seed_id("employee", "development-employee")
    employee_user = _development_user_id("employee")
    async with factory() as session:
        reason_id = await session.scalar(
            text("SELECT id FROM termination_reasons WHERE code='employee_request'")
        )
        unit_id = await session.scalar(
            text(
                "SELECT s.organization_unit_id FROM employee_assignments a "
                "JOIN staffing_slots s ON s.id=a.staffing_slot_id "
                'WHERE a.employee_id=:employee AND a."primary"=true'
            ),
            {"employee": employee_id},
        )
    assert reason_id is not None and unit_id is not None
    case = await operations.initiate(
        ORGANIZATION_ID,
        employee_user,
        {
            "employeeId": employee_id,
            "initiatedByEmployeeId": employee_id,
            "reasonId": reason_id,
            "legalBasis": "Employee request",
            "requestedDate": date.today(),
            "unitId": unit_id,
        },
    )
    case = await operations.decide(
        UUID(str(case["id"])),
        _development_user_id("hr"),
        int(case["revision"]),
        "hr_review",
        "approve",
        "complete",
    )
    case = await operations.decide(
        UUID(str(case["id"])),
        _development_user_id("admin"),
        int(case["revision"]),
        "signature",
        "approve",
        "signed",
    )
    documents = SqlAlchemyDocumentOperations(factory)
    async with factory() as session:
        order_type = await session.scalar(
            select(DocumentTypeModel.id).where(DocumentTypeModel.code == "termination_order")
        )
    assert order_type is not None
    document = await documents.create_record(
        ORGANIZATION_ID,
        _development_user_id("hr"),
        {
            "documentTypeId": order_type,
            "businessEntityType": "terminationCase",
            "businessEntityId": case["id"],
            "title": "Termination order",
            "confidentialityLevel": "confidential",
        },
    )
    await documents.add_version(
        UUID(str(document["id"])),
        _development_user_id("hr"),
        {
            "storageKey": "integration/order.pdf",
            "originalFilename": "order.pdf",
            "safeFilename": "order.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1,
            "sha256": "0" * 64,
            "sourceType": "uploaded",
        },
    )
    document = await documents.register(
        UUID(str(document["id"])),
        _development_user_id("hr"),
        2,
        "INT-TERM",
        date.today().isoformat(),
    )
    acknowledgement = await documents.create_acknowledgement(
        UUID(str(document["id"])), _development_user_id("hr"), employee_id
    )
    acknowledgement = await documents.acknowledge(
        UUID(str(acknowledgement["id"])),
        employee_user,
        ORGANIZATION_ID,
        int(acknowledgement["revision"]),
        {"confirmed": True},
    )
    assert acknowledgement["status"] == "acknowledged"
    case = await operations.register_order(
        UUID(str(case["id"])),
        _development_user_id("hr"),
        int(case["revision"]),
        UUID(str(document["id"])),
    )
    tasks = await operations.create_tasks(
        UUID(str(case["id"])),
        _development_user_id("hr"),
        [
            {"taskType": value, "assignedEmployeeId": employee_id}
            for value in ("handover", "asset_return", "access_revocation", "settlement")
        ],
    )
    await documents.create_checklist_item(
        ORGANIZATION_ID,
        _development_user_id("hr"),
        {
            "businessEntityType": "terminationCase",
            "businessEntityId": case["id"],
            "documentTypeId": order_type,
            "documentId": document["id"],
            "mandatory": True,
            "status": "validated",
        },
    )
    case = await operations.schedule(
        UUID(str(case["id"])), _development_user_id("hr"), int(case["revision"]), date.today(), []
    )
    async with factory() as session:
        before = (
            await session.execute(
                text(
                    "SELECT e.active, a.status FROM employees e "
                    "JOIN employee_assignments a ON a.employee_id=e.id "
                    'WHERE e.id=:id AND a."primary"=true'
                ),
                {"id": employee_id},
            )
        ).one()
    assert tuple(before) == (True, "scheduled_end")
    with pytest.raises(Exception) as incomplete:
        await operations.complete(
            UUID(str(case["id"])), _development_user_id("hr"), int(case["revision"])
        )
    assert getattr(incomplete.value, "code", None).value == "TERMINATION_TASKS_INCOMPLETE"
    for task in tasks:
        await operations.complete_task(
            UUID(str(task["id"])), employee_user, int(task["revision"]), {"confirmed": True}
        )
    completed = await operations.complete(
        UUID(str(case["id"])), _development_user_id("hr"), int(case["revision"])
    )
    assert completed["status"] == "completed"
    async with factory() as session:
        after = (
            await session.execute(
                text(
                    "SELECT e.active, e.employment_status, a.status FROM employees e "
                    "JOIN employee_assignments a ON a.employee_id=e.id "
                    'WHERE e.id=:id AND a."primary"=true'
                ),
                {"id": employee_id},
            )
        ).one()
    assert tuple(after) == (False, "ended", "ended")
    with pytest.raises(Exception) as cancellation:
        await operations.cancel(
            UUID(str(case["id"])),
            _development_user_id("hr"),
            int(completed["revision"]),
            "too late",
        )
    assert getattr(cancellation.value, "code", None).value == "TERMINATION_CANCELLATION_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_conditional_legal_return_and_cancellation_before_effective_date(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyTerminationOperations(factory)
    employee_id = _seed_id("employee", "development-director")
    user_id = _development_user_id("director")
    async with factory() as session:
        reason_id = await session.scalar(
            text("SELECT id FROM termination_reasons WHERE code='agreement'")
        )
        unit_id = await session.scalar(
            text(
                "SELECT s.organization_unit_id FROM employee_assignments a "
                "JOIN staffing_slots s ON s.id=a.staffing_slot_id "
                'WHERE a.employee_id=:employee AND a."primary"=true'
            ),
            {"employee": employee_id},
        )
    assert reason_id is not None and unit_id is not None
    case = await operations.initiate(
        ORGANIZATION_ID,
        user_id,
        {
            "employeeId": employee_id,
            "initiatedByEmployeeId": employee_id,
            "reasonId": reason_id,
            "legalBasis": "Mutual agreement",
            "requestedDate": date.today() + timedelta(days=30),
            "unitId": unit_id,
        },
    )
    case = await operations.decide(
        UUID(str(case["id"])),
        _development_user_id("hr"),
        int(case["revision"]),
        "hr_review",
        "approve",
        "complete",
    )
    assert case["status"] == "legal_review"
    case = await operations.decide(
        UUID(str(case["id"])),
        _development_user_id("admin"),
        int(case["revision"]),
        "legal_review",
        "return",
        "basis requires correction",
    )
    assert case["status"] == "returned"
    async with factory() as session:
        returned_process = await session.get(ProcessInstanceModel, case["process_instance_id"])
        returned_task = await session.scalar(
            select(WorkflowTaskModel).where(
                WorkflowTaskModel.process_instance_id == case["process_instance_id"],
                WorkflowTaskModel.status == "returned",
            )
        )
    assert returned_process is not None and returned_process.status == "active"
    assert returned_task is not None
    cancelled = await operations.cancel(
        UUID(str(case["id"])),
        _development_user_id("hr"),
        int(case["revision"]),
        "employee withdrew request",
    )
    assert cancelled["status"] == "cancelled"
    async with factory() as session:
        cancelled_process = await session.get(
            ProcessInstanceModel, cancelled["process_instance_id"]
        )
        unfinished = int(
            await session.scalar(
                select(func.count())
                .select_from(WorkflowTaskModel)
                .where(
                    WorkflowTaskModel.process_instance_id == cancelled["process_instance_id"],
                    WorkflowTaskModel.status.in_(("active", "pending")),
                )
            )
            or 0
        )
    assert cancelled_process is not None and cancelled_process.status == "cancelled"
    assert unfinished == 0
    with pytest.raises(ResourceNotFoundError):
        await operations.require_case_organization(UUID(str(case["id"])), uuid4())


@pytest.mark.asyncio
async def test_candidate_sensitive_data_is_encrypted_and_expired_record_is_anonymized(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyRecruitmentOperations(
        factory, FernetSensitiveDataProtector(Fernet.generate_key().decode())
    )
    actor = _development_user_id("hr")
    candidate = await operations.create_candidate(
        ORGANIZATION_ID,
        actor,
        {
            "firstName": "Privacy",
            "lastName": "Candidate",
            "displayName": "Privacy Candidate",
            "personalEmail": "privacy@example.test",
            "phone": "+77000000000",
            "identity": "sensitive-identity",
            "source": "integration",
            "consentStatus": "granted",
            "retentionUntil": date.today() - timedelta(days=1),
        },
    )
    async with factory() as session:
        protected = (
            await session.execute(
                text(
                    "SELECT protected_personal_email, protected_phone, protected_identity "
                    "FROM candidates WHERE id=:id"
                ),
                {"id": candidate["id"]},
            )
        ).one()
    assert "privacy@example.test" not in str(protected)
    assert "+77000000000" not in str(protected)
    assert "sensitive-identity" not in str(protected)

    anonymized = await operations.anonymize_candidate(
        UUID(str(candidate["id"])), actor, int(candidate["revision"]), "retention expired"
    )
    assert anonymized["status"] == "anonymized"
    assert anonymized["consent_status"] == "withdrawn"
    async with factory() as session:
        stored = (
            await session.execute(
                text(
                    "SELECT protected_personal_email, protected_phone, protected_identity "
                    "FROM candidates WHERE id=:id"
                ),
                {"id": candidate["id"]},
            )
        ).one()
        event_payload = await session.scalar(
            text(
                "SELECT payload FROM outbox_events "
                "WHERE event_name='candidateAnonymized' ORDER BY occurred_at DESC LIMIT 1"
            )
        )
    assert tuple(stored) == (None, None, None)
    assert event_payload == {"id": str(candidate["id"])}
