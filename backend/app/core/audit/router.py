"""Read-only audit API; mutation is available only to application services."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.domain import AuditQuery
from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.audit.schemas import AuditEventDto
from app.core.audit.service import AuditService
from app.core.database.session import get_session
from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.shared.api import ListResponse, PageMeta

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=ListResponse[AuditEventDto])
async def list_audit_events(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    authorization: Annotated[AuthorizationPort, Depends(get_authorization_port)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
    actor_id: Annotated[UUID | None, Query(alias="actorId")] = None,
    entity_type: Annotated[str | None, Query(alias="entityType", max_length=100)] = None,
    entity_id: Annotated[UUID | None, Query(alias="entityId")] = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[
        Literal[
            "occurredAt",
            "-occurredAt",
            "action",
            "-action",
            "entityType",
            "-entityType",
        ],
        Query(),
    ] = "-occurredAt",
) -> ListResponse[AuditEventDto]:
    effective_organization_id = organization_id or principal.organization_id
    await authorization.require(
        principal=principal,
        permission_code="audit.read",
        organization_id=effective_organization_id,
    )

    service = AuditService(SqlAlchemyAuditLog(session))
    result = await service.list_events(
        AuditQuery(
            organization_id=effective_organization_id,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            page=page,
            page_size=page_size,
            sort=sort,
        )
    )
    return ListResponse[AuditEventDto](
        data=[AuditEventDto.model_validate(event) for event in result.items],
        meta=PageMeta(page=page, page_size=page_size, total=result.total),
    )
