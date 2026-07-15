"""Thin REST adapter for role and permission use cases."""

from __future__ import annotations

from typing import Annotated, Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.modules.access_control.api.dependencies import get_authorized_access_service
from app.modules.access_control.api.schemas import (
    AccessScopeResponse,
    PermissionResponse,
    RoleAssignmentCreateRequest,
    RoleAssignmentResponse,
    RoleAssignmentRevokeRequest,
    RoleCreateRequest,
    RoleResponse,
)
from app.modules.access_control.application.facade import (
    AccessActor,
    AuthorizedAccessControlService,
)
from app.modules.access_control.application.services import (
    AssignRoleCommand,
    CreateRoleCommand,
)
from app.modules.access_control.domain.entities import UserRoleAssignment
from app.shared.api.schemas import DataResponse, ListResponse, PageMeta

router = APIRouter(prefix="/access", tags=["access-control"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
ServiceDependency = Annotated[
    AuthorizedAccessControlService,
    Depends(get_authorized_access_service),
]
RoleSort = Literal["code", "-code", "name", "-name", "createdAt", "-createdAt"]
PermissionSort = Literal["code", "-code", "name", "-name", "createdAt", "-createdAt"]


class _HasId(Protocol):
    @property
    def id(self) -> UUID: ...


def _sort_items[Sortable: _HasId](
    items: list[Sortable], sort: str, attributes: dict[str, str]
) -> list[Sortable]:
    attribute = attributes[sort.removeprefix("-")]
    return sorted(
        items,
        key=lambda item: (getattr(item, attribute), str(item.id)),
        reverse=sort.startswith("-"),
    )


def _actor(principal: Principal) -> AccessActor:
    return AccessActor(
        user_id=principal.user_id,
        organization_id=principal.organization_id,
    )


def _assignment_response(assignment: UserRoleAssignment) -> RoleAssignmentResponse:
    return RoleAssignmentResponse(
        id=assignment.id,
        user_id=assignment.user_id,
        role_id=assignment.role_id,
        scope=AccessScopeResponse(
            id=assignment.scope.id,
            type=assignment.scope.scope_type,
            organization_id=assignment.scope.organization_id,
            unit_ids=assignment.scope.unit_ids,
        ),
        effective_from=assignment.effective_from,
        effective_to=assignment.effective_to,
        created_by=assignment.created_by,
        created_at=assignment.created_at,
        revoked_at=assignment.revoked_at,
        revoked_by=assignment.revoked_by,
        revocation_reason=assignment.revocation_reason,
        revision=assignment.revision,
    )


@router.get("/roles", response_model=ListResponse[RoleResponse])
async def list_roles(
    principal: PrincipalDependency,
    service: ServiceDependency,
    organization_id: UUID | None = Query(default=None, alias="organizationId"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    sort: Annotated[RoleSort, Query()] = "code",
) -> ListResponse[RoleResponse]:
    roles = _sort_items(
        list(
            await service.list_roles(
                actor=_actor(principal),
                organization_id=organization_id,
            )
        ),
        sort,
        {"code": "code", "name": "name", "createdAt": "created_at"},
    )
    start = (page - 1) * page_size
    items = [RoleResponse.model_validate(role) for role in roles[start : start + page_size]]
    return ListResponse(
        data=items,
        meta=PageMeta(page=page, page_size=page_size, total=len(roles)),
    )


@router.post(
    "/roles",
    response_model=DataResponse[RoleResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_role(
    payload: RoleCreateRequest,
    principal: PrincipalDependency,
    service: ServiceDependency,
) -> DataResponse[RoleResponse]:
    role = await service.create_role(
        CreateRoleCommand(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            organization_id=payload.organization_id,
            permission_codes=frozenset(payload.permission_codes),
            reason=payload.reason,
        ),
        actor=_actor(principal),
    )
    return DataResponse(data=RoleResponse.model_validate(role))


@router.get("/permissions", response_model=ListResponse[PermissionResponse])
async def list_permissions(
    principal: PrincipalDependency,
    service: ServiceDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, alias="pageSize", ge=1, le=100),
    sort: Annotated[PermissionSort, Query()] = "code",
) -> ListResponse[PermissionResponse]:
    permissions = _sort_items(
        list(await service.list_permissions(actor=_actor(principal))),
        sort,
        {"code": "code", "name": "name", "createdAt": "created_at"},
    )
    start = (page - 1) * page_size
    items = [
        PermissionResponse.model_validate(permission)
        for permission in permissions[start : start + page_size]
    ]
    return ListResponse(
        data=items,
        meta=PageMeta(page=page, page_size=page_size, total=len(permissions)),
    )


@router.post(
    "/role-assignments",
    response_model=DataResponse[RoleAssignmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_role_assignment(
    payload: RoleAssignmentCreateRequest,
    principal: PrincipalDependency,
    service: ServiceDependency,
) -> DataResponse[RoleAssignmentResponse]:
    assignment = await service.assign_role(
        AssignRoleCommand(
            user_id=payload.user_id,
            role_id=payload.role_id,
            scope_type=payload.scope.type,
            organization_id=payload.scope.organization_id,
            unit_ids=frozenset(payload.scope.unit_ids),
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            reason=payload.reason,
        ),
        actor=_actor(principal),
    )
    return DataResponse(data=_assignment_response(assignment))


@router.post(
    "/role-assignments/{assignment_id}/revoke",
    response_model=DataResponse[RoleAssignmentResponse],
)
async def revoke_role_assignment(
    assignment_id: UUID,
    payload: RoleAssignmentRevokeRequest,
    principal: PrincipalDependency,
    service: ServiceDependency,
) -> DataResponse[RoleAssignmentResponse]:
    assignment = await service.revoke_role_assignment(
        assignment_id,
        actor=_actor(principal),
        reason=payload.reason,
        expected_revision=payload.revision,
    )
    return DataResponse(data=_assignment_response(assignment))
