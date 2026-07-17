from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.database.session import async_session_factory
from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.infrastructure.operations import SqlAlchemyWorkflowOperations
from app.shared.api import DataResponse, ListResponse, PageMeta

from .schemas import (
    ActorRuleRequest,
    CreateDefinitionRequest,
    CreateDraftRequest,
    DecisionRequest,
    FormDefinitionRequest,
    FormDraftRequest,
    FormFieldRequest,
    FormPublishRequest,
    FormSubmissionRequest,
    OrganizationRequest,
    ReassignTaskRequest,
    StartProcessRequest,
    StepRequest,
    TaskActionRequest,
    TransitionRequest,
)

router = APIRouter(prefix="/workflow", tags=["workflow"])


def get_workflow_service(
    authorization: Annotated[AuthorizationPort, Depends(get_authorization_port)],
) -> WorkflowService:
    return WorkflowService(SqlAlchemyWorkflowOperations(async_session_factory), authorization)


Service = Annotated[WorkflowService, Depends(get_workflow_service)]
CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


@router.post("/forms", response_model=DataResponse[dict[str, Any]], status_code=201)
async def create_form(
    body: FormDefinitionRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.definition.manage", body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.create_form_definition(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post(
    "/forms/{form_id}/drafts", response_model=DataResponse[dict[str, Any]], status_code=201
)
async def create_form_draft(
    form_id: UUID, body: FormDraftRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.definition.manage", body.organization_id)
    await service._operations.require_organization("form", form_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.create_form_draft(
                form_id, principal.user_id, body.based_on_version_id
            )
        )
    )


@router.post(
    "/form-versions/{version_id}/fields",
    response_model=DataResponse[dict[str, Any]],
    status_code=201,
)
async def create_form_field(
    version_id: UUID, body: FormFieldRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.definition.manage", body.organization_id)
    await service._operations.require_organization("form_version", version_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.save_form_field(
                version_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post("/form-versions/{version_id}/publish", response_model=DataResponse[dict[str, Any]])
async def publish_form(
    version_id: UUID, body: FormPublishRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.definition.publish", body.organization_id)
    await service._operations.require_organization("form_version", version_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.publish_form_version(
                version_id, principal.user_id, body.revision, body.reason
            )
        )
    )


@router.post("/form-submissions", response_model=DataResponse[dict[str, Any]], status_code=201)
async def submit_form(
    body: FormSubmissionRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.task.act", body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.submit_form(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.get("/definitions", response_model=DataResponse[list[dict[str, Any]]])
async def definitions(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[list[dict[str, Any]]]:
    return DataResponse(
        data=[dict(item) for item in await service.list_definitions(principal, organization_id)]
    )


@router.post(
    "/definitions", response_model=DataResponse[dict[str, Any]], status_code=status.HTTP_201_CREATED
)
async def create_definition(
    body: CreateDefinitionRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=dict(
            await service.create_definition(
                principal,
                body.organization_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post(
    "/definitions/{definition_id}/drafts",
    response_model=DataResponse[dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
)
async def create_draft(
    definition_id: UUID, body: CreateDraftRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=dict(
            await service.create_draft(
                principal, body.organization_id, definition_id, body.based_on_version_id, body.name
            )
        )
    )


@router.get("/versions/{version_id}", response_model=DataResponse[dict[str, Any]])
async def version(
    version_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.definition.read", organization_id)
    await service._operations.require_organization("version", version_id, organization_id)
    return DataResponse(data=dict(await service._operations.get_version(version_id)))


@router.post(
    "/versions/{version_id}/actor-rules",
    response_model=DataResponse[dict[str, Any]],
    status_code=201,
)
async def actor_rule(
    version_id: UUID, body: ActorRuleRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.definition.manage", body.organization_id)
    await service._operations.require_organization("version", version_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.save_actor_rule(
                version_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post(
    "/versions/{version_id}/steps", response_model=DataResponse[dict[str, Any]], status_code=201
)
async def step(
    version_id: UUID, body: StepRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.definition.manage", body.organization_id)
    await service._operations.require_organization("version", version_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.save_step(
                version_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post(
    "/versions/{version_id}/transitions",
    response_model=DataResponse[dict[str, Any]],
    status_code=201,
)
async def transition(
    version_id: UUID, body: TransitionRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.definition.manage", body.organization_id)
    await service._operations.require_organization("version", version_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.save_transition(
                version_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post("/versions/{version_id}/validate", response_model=DataResponse[dict[str, Any]])
async def validate(
    version_id: UUID, body: OrganizationRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    problems = await service.validate(principal, body.organization_id, version_id)
    return DataResponse(
        data={
            "valid": not problems,
            "problems": [
                {"code": p.code, "message": p.message, "entityId": p.entity_id} for p in problems
            ],
        }
    )


@router.post("/versions/{version_id}/submit-review", response_model=DataResponse[dict[str, Any]])
async def submit_review(
    version_id: UUID, body: DecisionRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=dict(
            await service.submit_review(
                principal, body.organization_id, version_id, body.revision, body.reason
            )
        )
    )


@router.post("/versions/{version_id}/return", response_model=DataResponse[dict[str, Any]])
async def return_version(
    version_id: UUID, body: DecisionRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=dict(
            await service.return_draft(
                principal, body.organization_id, version_id, body.revision, body.reason
            )
        )
    )


@router.post("/versions/{version_id}/publish", response_model=DataResponse[dict[str, Any]])
async def publish(
    version_id: UUID, body: DecisionRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=dict(
            await service.publish(
                principal, body.organization_id, version_id, body.revision, body.reason
            )
        )
    )


@router.get("/versions/{left_id}/compare/{right_id}", response_model=DataResponse[dict[str, Any]])
async def compare(
    left_id: UUID,
    right_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.definition.read", organization_id)
    await service._operations.require_organization("version", left_id, organization_id)
    await service._operations.require_organization("version", right_id, organization_id)
    return DataResponse(data=dict(await service._operations.compare_versions(left_id, right_id)))


@router.post("/instances", response_model=DataResponse[dict[str, Any]], status_code=201)
async def start(
    body: StartProcessRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=dict(
            await service.start_instance(
                principal,
                body.organization_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.get("/instances", response_model=ListResponse[dict[str, Any]])
async def instances(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
) -> ListResponse[dict[str, Any]]:
    await service._require(principal, "workflow.instance.read", organization_id)
    items, total = await service._operations.list_instances(
        organization_id, (page - 1) * page_size, page_size
    )
    return ListResponse(
        data=[dict(item) for item in items],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/instances/{instance_id}", response_model=DataResponse[dict[str, Any]])
async def instance(
    instance_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[dict[str, Any]]:
    await service._require(principal, "workflow.instance.read", organization_id)
    await service._operations.require_organization("instance", instance_id, organization_id)
    return DataResponse(data=dict(await service._operations.get_instance(instance_id)))


@router.get("/instances/{instance_id}/history", response_model=DataResponse[list[dict[str, Any]]])
async def history(
    instance_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[list[dict[str, Any]]]:
    await service._require(principal, "workflow.instance.read", organization_id)
    await service._operations.require_organization("instance", instance_id, organization_id)
    return DataResponse(
        data=[dict(item) for item in await service._operations.history(instance_id)]
    )


@router.get("/tasks/my", response_model=ListResponse[dict[str, Any]])
async def my_tasks(
    service: Service,
    principal: CurrentPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
) -> ListResponse[dict[str, Any]]:
    await service._require(principal, "workflow.task.read", principal.organization_id)
    items, total = await service._operations.my_tasks(
        principal.user_id, (page - 1) * page_size, page_size
    )
    return ListResponse(
        data=[dict(item) for item in items],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.post("/tasks/{task_id}/actions", response_model=DataResponse[dict[str, Any]])
async def task_action(
    task_id: UUID, body: TaskActionRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=dict(
            await service.act_task(
                principal,
                body.organization_id,
                task_id,
                body.revision,
                body.action,
                body.comment,
                body.idempotency_key,
            )
        )
    )


@router.post("/tasks/{task_id}/reassign", response_model=DataResponse[dict[str, Any]])
async def reassign(
    task_id: UUID, body: ReassignTaskRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=dict(
            await service.reassign_task(
                principal,
                body.organization_id,
                task_id,
                body.revision,
                body.assigned_user_id,
                body.reason,
            )
        )
    )
