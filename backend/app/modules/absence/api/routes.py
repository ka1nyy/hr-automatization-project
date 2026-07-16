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

from ..infrastructure.operations import SqlAlchemyAbsenceOperations
from .schemas import (
    CancelBody,
    DecisionBody,
    LeaveCreateBody,
    LeaveResubmitBody,
    TripCreateBody,
    TripResubmitBody,
)

router = APIRouter(prefix="/absence", tags=["absence"])
Ops = Annotated[
    SqlAlchemyAbsenceOperations,
    Depends(lambda: SqlAlchemyAbsenceOperations(async_session_factory)),
]
Auth = Annotated[AuthorizationPort, Depends(get_authorization_port)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


async def _require(
    auth: AuthorizationPort,
    principal: Principal,
    permission: str,
    organization_id: UUID,
    unit_id: UUID | None = None,
) -> None:
    await auth.require(
        principal=principal,
        permission_code=permission,
        organization_id=organization_id,
        unit_id=unit_id,
    )


@router.get("/leave-types", response_model=DataResponse[list[dict[str, Any]]])
async def leave_types(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    ops: Ops,
    auth: Auth,
    principal: PrincipalDep,
) -> DataResponse[list[dict[str, Any]]]:
    await _require(auth, principal, "absence.read_self", organization_id)
    return DataResponse(data=[dict(row) for row in await ops.list_leave_types(organization_id)])


@router.get("/leave-balances", response_model=DataResponse[list[dict[str, Any]]])
async def balances(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    ops: Ops,
    auth: Auth,
    principal: PrincipalDep,
    employee_id: Annotated[UUID | None, Query(alias="employeeId")] = None,
) -> DataResponse[list[dict[str, Any]]]:
    target = employee_id or principal.employee_id
    if target is None:
        raise ResourceNotFoundError("employee")
    permission = "absence.read_self" if target == principal.employee_id else "absence.read_all"
    await _require(auth, principal, permission, organization_id)
    return DataResponse(
        data=[dict(row) for row in await ops.list_balances(organization_id, target)]
    )


async def _list(
    resource: str,
    organization_id: UUID,
    scope: Literal["self", "unit", "all"],
    unit_id: UUID | None,
    page: int,
    page_size: int,
    ops: SqlAlchemyAbsenceOperations,
    auth: AuthorizationPort,
    principal: Principal,
) -> ListResponse[dict[str, Any]]:
    if scope == "self":
        await _require(auth, principal, "absence.read_self", organization_id)
        if principal.employee_id is None:
            return ListResponse(data=[], meta=PageMeta(page=page, page_size=page_size, total=0))
        employee_id, scoped_unit = principal.employee_id, None
    elif scope == "unit":
        if unit_id is None:
            raise ValidationError("unitId is required for unit scope.")
        await _require(auth, principal, "absence.read_unit", organization_id, unit_id)
        employee_id, scoped_unit = None, unit_id
    else:
        await _require(auth, principal, "absence.read_all", organization_id)
        employee_id = scoped_unit = None
    rows, total = await ops.list_requests(
        resource,
        organization_id,
        (page - 1) * page_size,
        page_size,
        employee_id=employee_id,
        unit_id=scoped_unit,
    )
    return ListResponse(
        data=[dict(row) for row in rows],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/leave-requests", response_model=ListResponse[dict[str, Any]])
async def list_leave(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    ops: Ops,
    auth: Auth,
    principal: PrincipalDep,
    scope: Literal["self", "unit", "all"] = "self",
    unit_id: Annotated[UUID | None, Query(alias="unitId")] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
) -> ListResponse[dict[str, Any]]:
    return await _list(
        "leave", organization_id, scope, unit_id, page, page_size, ops, auth, principal
    )


@router.post("/leave-requests", response_model=DataResponse[dict[str, Any]], status_code=201)
async def create_leave(
    body: LeaveCreateBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    if principal.employee_id != body.employee_id:
        raise ValidationError("Employees may only request their own leave.")
    await _require(auth, principal, "leave.request", body.organization_id)
    return DataResponse(
        data=dict(
            await ops.create_leave(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


async def _leave_decision(
    stage: str,
    permission: str,
    item_id: UUID,
    body: DecisionBody,
    ops: SqlAlchemyAbsenceOperations,
    auth: AuthorizationPort,
    principal: Principal,
) -> DataResponse[dict[str, Any]]:
    await _require(auth, principal, permission, body.organization_id)
    await ops.require_organization("leave", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await ops.decide_leave(
                item_id, principal.user_id, body.revision, stage, body.decision, body.comment
            )
        )
    )


@router.post(
    "/leave-requests/{item_id}/manager-review", response_model=DataResponse[dict[str, Any]]
)
async def leave_manager(
    item_id: UUID, body: DecisionBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    return await _leave_decision(
        "manager_review", "leave.review_manager", item_id, body, ops, auth, principal
    )


@router.post("/leave-requests/{item_id}/hr-review", response_model=DataResponse[dict[str, Any]])
async def leave_hr(
    item_id: UUID, body: DecisionBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    return await _leave_decision(
        "hr_review", "leave.review_hr", item_id, body, ops, auth, principal
    )


@router.post("/leave-requests/{item_id}/resubmit", response_model=DataResponse[dict[str, Any]])
async def resubmit_leave(
    item_id: UUID, body: LeaveResubmitBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await _require(auth, principal, "leave.request", body.organization_id)
    await ops.require_organization("leave", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await ops.resubmit_leave(
                item_id,
                principal.user_id,
                body.revision,
                body.model_dump(by_alias=True, exclude={"organization_id", "revision"}),
            )
        )
    )


@router.post("/leave-requests/{item_id}/cancel", response_model=DataResponse[dict[str, Any]])
async def cancel_leave(
    item_id: UUID, body: CancelBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await _require(auth, principal, "leave.request", body.organization_id)
    await ops.require_organization("leave", item_id, body.organization_id)
    return DataResponse(
        data=dict(await ops.cancel_leave(item_id, principal.user_id, body.revision, body.reason))
    )


@router.get("/business-trips", response_model=ListResponse[dict[str, Any]])
async def list_trips(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    ops: Ops,
    auth: Auth,
    principal: PrincipalDep,
    scope: Literal["self", "unit", "all"] = "self",
    unit_id: Annotated[UUID | None, Query(alias="unitId")] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
) -> ListResponse[dict[str, Any]]:
    return await _list(
        "trip", organization_id, scope, unit_id, page, page_size, ops, auth, principal
    )


@router.post("/business-trips", response_model=DataResponse[dict[str, Any]], status_code=201)
async def create_trip(
    body: TripCreateBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    if principal.employee_id != body.employee_id:
        raise ValidationError("Employees may only request their own trips.")
    await _require(auth, principal, "business_trip.request", body.organization_id)
    return DataResponse(
        data=dict(
            await ops.create_trip(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


async def _trip_decision(
    stage: str,
    permission: str,
    item_id: UUID,
    body: DecisionBody,
    ops: SqlAlchemyAbsenceOperations,
    auth: AuthorizationPort,
    principal: Principal,
) -> DataResponse[dict[str, Any]]:
    await _require(auth, principal, permission, body.organization_id)
    await ops.require_organization("trip", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await ops.decide_trip(
                item_id, principal.user_id, body.revision, stage, body.decision, body.comment
            )
        )
    )


@router.post(
    "/business-trips/{item_id}/manager-review", response_model=DataResponse[dict[str, Any]]
)
async def trip_manager(
    item_id: UUID, body: DecisionBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    return await _trip_decision(
        "manager_review", "business_trip.review_manager", item_id, body, ops, auth, principal
    )


@router.post(
    "/business-trips/{item_id}/finance-review", response_model=DataResponse[dict[str, Any]]
)
async def trip_finance(
    item_id: UUID, body: DecisionBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    return await _trip_decision(
        "finance_review", "business_trip.review_finance", item_id, body, ops, auth, principal
    )


@router.post("/business-trips/{item_id}/register", response_model=DataResponse[dict[str, Any]])
async def trip_register(
    item_id: UUID, body: DecisionBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    return await _trip_decision(
        "hr_registration", "business_trip.register", item_id, body, ops, auth, principal
    )


@router.post("/business-trips/{item_id}/resubmit", response_model=DataResponse[dict[str, Any]])
async def resubmit_trip(
    item_id: UUID, body: TripResubmitBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await _require(auth, principal, "business_trip.request", body.organization_id)
    await ops.require_organization("trip", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await ops.resubmit_trip(
                item_id,
                principal.user_id,
                body.revision,
                body.model_dump(
                    by_alias=True, exclude={"organization_id", "revision", "employee_id"}
                ),
            )
        )
    )


@router.post("/business-trips/{item_id}/cancel", response_model=DataResponse[dict[str, Any]])
async def cancel_trip(
    item_id: UUID, body: CancelBody, ops: Ops, auth: Auth, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await _require(auth, principal, "business_trip.request", body.organization_id)
    await ops.require_organization("trip", item_id, body.organization_id)
    return DataResponse(
        data=dict(await ops.cancel_trip(item_id, principal.user_id, body.revision, body.reason))
    )
