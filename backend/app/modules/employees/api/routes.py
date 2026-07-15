"""Thin HTTP routes for employee application services."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from app.core.logging.context import get_request_id

from ..application.ports import Actor
from ..application.service import EmployeeService
from ..domain.errors import EmployeeDomainError
from .schemas import (
    AssignmentResponse,
    CreateAssignmentRequest,
    CreateDelegationRequest,
    CreateEmployeeRequest,
    DelegationResponse,
    EmployeeResponse,
    EndAssignmentRequest,
    Envelope,
    ErrorBody,
    ErrorEnvelope,
    Meta,
    ReviewAssignmentRequest,
    RevokeDelegationRequest,
    UpdateEmployeeRequest,
)

ServiceProvider = Callable[[], EmployeeService]
ActorProvider = Callable[..., Actor | Awaitable[Actor]]
EmployeeSort = Literal[
    "employeeNumber",
    "-employeeNumber",
    "hireDate",
    "-hireDate",
    "createdAt",
    "-createdAt",
]
DelegationSort = Literal[
    "effectiveFrom",
    "-effectiveFrom",
    "createdAt",
    "-createdAt",
    "status",
    "-status",
]


def _request_id(request: Request) -> UUID:
    del request
    return UUID(get_request_id())


async def employee_exception_handler(
    request: Request, exception: EmployeeDomainError
) -> JSONResponse:
    payload = ErrorEnvelope(
        error=ErrorBody(
            code=exception.code,
            message=exception.message,
            details=exception.details,
            request_id=_request_id(request),
        )
    )
    return JSONResponse(
        status_code=exception.status_code,
        content=payload.model_dump(mode="json", by_alias=True),
    )


def create_employee_router(
    service_provider: ServiceProvider, actor_provider: ActorProvider
) -> APIRouter:
    router = APIRouter(tags=["employees"])
    Service = Annotated[EmployeeService, Depends(service_provider)]
    CurrentActor = Annotated[Actor, Depends(actor_provider)]

    @router.get("/employees", response_model=Envelope[list[EmployeeResponse]])
    async def list_employees(
        request: Request,
        service: Service,
        actor: CurrentActor,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(alias="pageSize", ge=1, le=200)] = 20,
        active: bool | None = None,
        sort: Annotated[EmployeeSort, Query()] = "employeeNumber",
    ) -> Envelope[list[EmployeeResponse]]:
        result = await service.list_employees(
            actor,
            page=page,
            page_size=page_size,
            active=active,
            sort=sort,
        )
        return Envelope(
            data=[EmployeeResponse.from_details(item) for item in result.items],
            meta=Meta(
                request_id=_request_id(request), page=page, page_size=page_size, total=result.total
            ),
        )

    @router.post(
        "/employees", response_model=Envelope[EmployeeResponse], status_code=status.HTTP_201_CREATED
    )
    async def create_employee(
        body: CreateEmployeeRequest,
        request: Request,
        service: Service,
        actor: CurrentActor,
    ) -> Envelope[EmployeeResponse]:
        result = await service.create_employee(actor, body.to_command())
        return Envelope(
            data=EmployeeResponse.from_details(result),
            meta=Meta(request_id=_request_id(request)),
        )

    @router.get("/employees/{employee_id}", response_model=Envelope[EmployeeResponse])
    async def get_employee(
        employee_id: UUID,
        request: Request,
        service: Service,
        actor: CurrentActor,
        include_sensitive: Annotated[bool, Query(alias="includeSensitive")] = False,
    ) -> Envelope[EmployeeResponse]:
        result = await service.get_employee(actor, employee_id, include_sensitive=include_sensitive)
        return Envelope(
            data=EmployeeResponse.from_details(result, include_sensitive=include_sensitive),
            meta=Meta(request_id=_request_id(request)),
        )

    @router.patch("/employees/{employee_id}", response_model=Envelope[EmployeeResponse])
    async def update_employee(
        employee_id: UUID,
        body: UpdateEmployeeRequest,
        request: Request,
        service: Service,
        actor: CurrentActor,
    ) -> Envelope[EmployeeResponse]:
        result = await service.update_employee(actor, body.to_command(employee_id))
        return Envelope(
            data=EmployeeResponse.from_details(result),
            meta=Meta(request_id=_request_id(request)),
        )

    @router.post(
        "/employee-assignments",
        response_model=Envelope[AssignmentResponse],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_assignment(
        body: CreateAssignmentRequest,
        request: Request,
        service: Service,
        actor: CurrentActor,
    ) -> Envelope[AssignmentResponse]:
        assignment = await service.create_assignment(actor, body.to_command())
        return Envelope(
            data=AssignmentResponse.from_domain(assignment),
            meta=Meta(request_id=_request_id(request)),
        )

    @router.post(
        "/employee-assignments/{assignment_id}/end",
        response_model=Envelope[AssignmentResponse],
    )
    async def end_assignment(
        assignment_id: UUID,
        body: EndAssignmentRequest,
        request: Request,
        service: Service,
        actor: CurrentActor,
    ) -> Envelope[AssignmentResponse]:
        assignment = await service.end_assignment(actor, body.to_command(assignment_id))
        return Envelope(
            data=AssignmentResponse.from_domain(assignment),
            meta=Meta(request_id=_request_id(request)),
        )

    @router.post(
        "/employee-assignments/{assignment_id}/review",
        response_model=Envelope[AssignmentResponse],
    )
    async def review_assignment(
        assignment_id: UUID,
        body: ReviewAssignmentRequest,
        request: Request,
        service: Service,
        actor: CurrentActor,
    ) -> Envelope[AssignmentResponse]:
        assignment = await service.review_assignment(actor, body.to_command(assignment_id))
        return Envelope(
            data=AssignmentResponse.from_domain(assignment),
            meta=Meta(request_id=_request_id(request)),
        )

    @router.get("/delegations", response_model=Envelope[list[DelegationResponse]])
    async def list_delegations(
        request: Request,
        service: Service,
        actor: CurrentActor,
        employee_id: Annotated[UUID | None, Query(alias="employeeId")] = None,
        active_at: Annotated[datetime | None, Query(alias="activeAt")] = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(alias="pageSize", ge=1, le=200)] = 20,
        sort: Annotated[DelegationSort, Query()] = "-effectiveFrom",
    ) -> Envelope[list[DelegationResponse]]:
        result = await service.list_delegations(
            actor,
            employee_id=employee_id,
            active_at=active_at,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        return Envelope(
            data=[DelegationResponse.from_domain(item) for item in result.items],
            meta=Meta(
                request_id=_request_id(request), page=page, page_size=page_size, total=result.total
            ),
        )

    @router.post(
        "/delegations",
        response_model=Envelope[DelegationResponse],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_delegation(
        body: CreateDelegationRequest,
        request: Request,
        service: Service,
        actor: CurrentActor,
    ) -> Envelope[DelegationResponse]:
        delegation = await service.create_delegation(actor, body.to_command())
        return Envelope(
            data=DelegationResponse.from_domain(delegation),
            meta=Meta(request_id=_request_id(request)),
        )

    @router.post("/delegations/{delegation_id}/revoke", response_model=Envelope[DelegationResponse])
    async def revoke_delegation(
        delegation_id: UUID,
        body: RevokeDelegationRequest,
        request: Request,
        service: Service,
        actor: CurrentActor,
    ) -> Envelope[DelegationResponse]:
        delegation = await service.revoke_delegation(actor, body.to_command(delegation_id))
        return Envelope(
            data=DelegationResponse.from_domain(delegation),
            meta=Meta(request_id=_request_id(request)),
        )

    return router
