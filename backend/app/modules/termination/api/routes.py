from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.database.session import async_session_factory
from app.core.errors import ResourceNotFoundError, ValidationError
from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.shared.api import DataResponse, ListResponse, PageMeta

from ..infrastructure.operations import SqlAlchemyTerminationOperations
from .schemas import (
    CancelBody,
    CompleteBody,
    DecisionBody,
    InitiateBody,
    RegisterBody,
    ResubmitBody,
    ScheduleBody,
    TaskCompleteBody,
    TasksBody,
    WaiveBody,
)

router = APIRouter(prefix="/terminations", tags=["termination"])
Ops = Annotated[
    SqlAlchemyTerminationOperations,
    Depends(lambda: SqlAlchemyTerminationOperations(async_session_factory)),
]
Auth = Annotated[AuthorizationPort, Depends(get_authorization_port)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


async def require(
    auth: AuthorizationPort,
    principal: Principal,
    permission: str,
    org: UUID,
    unit: UUID | None = None,
) -> None:
    await auth.require(
        principal=principal, permission_code=permission, organization_id=org, unit_id=unit
    )


@router.get("", response_model=ListResponse[dict[str, Any]])
async def list_cases(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    ops: Ops,
    auth: Auth,
    principal: PrincipalDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    scope: Literal["self", "unit", "all"] = "all",
    unit_id: Annotated[UUID | None, Query(alias="unitId")] = None,
) -> ListResponse[dict[str, Any]]:
    if scope == "self":
        await require(auth, principal, "termination.read_self", organization_id)
        if principal.employee_id is None:
            return ListResponse(data=[], meta=PageMeta(page=page, page_size=page_size, total=0))
        employee_id = principal.employee_id
        scoped_unit = None
    elif scope == "unit":
        if unit_id is None:
            raise ValidationError("unitId is required for unit scope")
        await require(auth, principal, "termination.read_unit", organization_id, unit_id)
        employee_id, scoped_unit = None, unit_id
    else:
        await require(auth, principal, "termination.read_all", organization_id)
        employee_id = scoped_unit = None
    rows, total = await ops.list_cases(
        organization_id,
        (page - 1) * page_size,
        page_size,
        employee_id=employee_id,
        unit_id=scoped_unit,
    )
    return ListResponse(
        data=[dict(x) for x in rows], meta=PageMeta(page=page, page_size=page_size, total=total)
    )


@router.get("/{item_id}", response_model=DataResponse[dict[str, Any]])
async def get_case(
    item_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    ops: Ops,
    auth: Auth,
    principal: PrincipalDep,
    scope: Literal["self", "unit", "all"] = "all",
    unit_id: Annotated[UUID | None, Query(alias="unitId")] = None,
) -> DataResponse[dict[str, Any]]:
    if scope == "self":
        await require(auth, principal, "termination.read_self", organization_id)
        employee_id, scoped_unit = principal.employee_id, None
    elif scope == "unit":
        if unit_id is None:
            raise ValidationError("unitId is required for unit scope")
        await require(auth, principal, "termination.read_unit", organization_id, unit_id)
        employee_id, scoped_unit = None, unit_id
    else:
        await require(auth, principal, "termination.read_all", organization_id)
        employee_id = scoped_unit = None
    if scope == "self" and employee_id is None:
        raise ResourceNotFoundError("termination case", item_id)
    return DataResponse(
        data=dict(
            await ops.get_case(
                item_id,
                organization_id,
                employee_id=employee_id,
                unit_id=scoped_unit,
            )
        )
    )


@router.post("", response_model=DataResponse[dict[str, Any]], status_code=201)
async def initiate(
    body: InitiateBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    self_case = principal.employee_id == body.employee_id
    permission = "termination.initiate_self" if self_case else "termination.initiate_unit"
    await require(
        auth, principal, permission, body.organization_id, None if self_case else body.unit_id
    )
    return DataResponse(
        data=dict(
            await ops.initiate(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


async def _decide(
    stage: str,
    permission: str,
    item_id: UUID,
    body: DecisionBody,
    ops: SqlAlchemyTerminationOperations,
    auth: AuthorizationPort,
    principal: Principal,
) -> DataResponse[dict[str, Any]]:
    await require(auth, principal, permission, body.organization_id)
    await ops.require_case_organization(item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await ops.decide(
                item_id, principal.user_id, body.revision, stage, body.decision, body.comment
            )
        )
    )


@router.post("/{item_id}/hr-review", response_model=DataResponse[dict[str, Any]])
async def hr(
    item_id: UUID, body: DecisionBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    return await _decide("hr_review", "termination.review_hr", item_id, body, ops, auth, principal)


@router.post("/{item_id}/resubmit", response_model=DataResponse[dict[str, Any]])
async def resubmit(
    item_id: UUID, body: ResubmitBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    self_case = principal.employee_id == body.employee_id
    permission = "termination.initiate_self" if self_case else "termination.initiate_unit"
    await require(
        auth, principal, permission, body.organization_id, None if self_case else body.unit_id
    )
    await ops.require_case_organization(item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await ops.resubmit(
                item_id,
                principal.user_id,
                body.revision,
                body.model_dump(by_alias=True, exclude={"organization_id", "revision"}),
            )
        )
    )


@router.post("/{item_id}/legal-review", response_model=DataResponse[dict[str, Any]])
async def legal(
    item_id: UUID, body: DecisionBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    return await _decide(
        "legal_review", "termination.review_legal", item_id, body, ops, auth, principal
    )


@router.post("/{item_id}/sign", response_model=DataResponse[dict[str, Any]])
async def sign(
    item_id: UUID, body: DecisionBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    return await _decide("signature", "termination.sign", item_id, body, ops, auth, principal)


@router.post("/{item_id}/register-order", response_model=DataResponse[dict[str, Any]])
async def register(
    item_id: UUID, body: RegisterBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await require(auth, principal, "termination.review_hr", body.organization_id)
    await ops.require_case_organization(item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await ops.register_order(item_id, principal.user_id, body.revision, body.document_id)
        )
    )


@router.post("/{item_id}/tasks", response_model=DataResponse[list[dict[str, Any]]], status_code=201)
async def tasks(
    item_id: UUID, body: TasksBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[list[dict[str, Any]]]:
    await require(auth, principal, "termination.review_hr", body.organization_id)
    await ops.require_case_organization(item_id, body.organization_id)
    rows = await ops.create_tasks(
        item_id, principal.user_id, body.model_dump(by_alias=True)["tasks"]
    )
    return DataResponse(data=[dict(x) for x in rows])


@router.post("/tasks/{item_id}/complete", response_model=DataResponse[dict[str, Any]])
async def complete_task(
    item_id: UUID, body: TaskCompleteBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await ops.require_task_organization(item_id, body.organization_id)
    permission = {
        "handover": "termination.handover",
        "asset_return": "termination.assets.confirm",
        "access_revocation": "termination.access.confirm",
        "settlement": "termination.settlement.confirm",
        "exit_interview": "termination.exit_interview.manage",
    }.get(await ops.task_type(item_id), "termination.complete")
    await require(auth, principal, permission, body.organization_id)
    return DataResponse(
        data=dict(await ops.complete_task(item_id, principal.user_id, body.revision, body.evidence))
    )


@router.post("/tasks/{item_id}/waive", response_model=DataResponse[dict[str, Any]])
async def waive(
    item_id: UUID, body: WaiveBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await require(auth, principal, "termination.complete", body.organization_id)
    await ops.require_task_organization(item_id, body.organization_id)
    return DataResponse(
        data=dict(await ops.waive_task(item_id, principal.user_id, body.revision, body.reason))
    )


@router.post("/{item_id}/schedule", response_model=DataResponse[dict[str, Any]])
async def schedule(
    item_id: UUID, body: ScheduleBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await require(auth, principal, "termination.review_hr", body.organization_id)
    await ops.require_case_organization(item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await ops.schedule(
                item_id,
                principal.user_id,
                body.revision,
                body.effective_date,
                body.model_dump(by_alias=True)["secondaryAssignments"],
            )
        )
    )


@router.post("/{item_id}/complete", response_model=DataResponse[dict[str, Any]])
async def complete(
    item_id: UUID, body: CompleteBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await require(auth, principal, "termination.complete", body.organization_id)
    await ops.require_case_organization(item_id, body.organization_id)
    return DataResponse(data=dict(await ops.complete(item_id, principal.user_id, body.revision)))


@router.post("/{item_id}/cancel", response_model=DataResponse[dict[str, Any]])
async def cancel(
    item_id: UUID, body: CancelBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await require(auth, principal, "termination.review_hr", body.organization_id)
    await ops.require_case_organization(item_id, body.organization_id)
    return DataResponse(
        data=dict(await ops.cancel(item_id, principal.user_id, body.revision, body.reason))
    )
