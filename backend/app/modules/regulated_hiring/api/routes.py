from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.database.session import async_session_factory
from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.shared.api import DataResponse

from ..application import RegulatedHiringService
from .schemas import AuthorityBindingBody, FormRecordBody, StageActionBody, StartCaseBody

router = APIRouter(prefix="/regulated-hiring", tags=["regulated hiring"])


def get_service() -> RegulatedHiringService:
    return RegulatedHiringService(async_session_factory)


Service = Annotated[RegulatedHiringService, Depends(get_service)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]
AuthorizationDep = Annotated[AuthorizationPort, Depends(get_authorization_port)]


@router.get("/catalog", response_model=DataResponse[dict[str, Any]])
async def catalog(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: PrincipalDep,
    authorization: AuthorizationDep,
) -> DataResponse[dict[str, Any]]:
    await authorization.require(
        principal=principal,
        permission_code="regulated_hiring.read",
        organization_id=organization_id,
    )
    return DataResponse(data={"stages": service.stage_catalog(), "forms": service.form_catalog()})


@router.post(
    "/cases", response_model=DataResponse[dict[str, Any]], status_code=status.HTTP_201_CREATED
)
async def start_case(
    body: StartCaseBody,
    service: Service,
    principal: PrincipalDep,
    authorization: AuthorizationDep,
) -> DataResponse[dict[str, Any]]:
    await authorization.require(
        principal=principal,
        permission_code="regulated_hiring.start",
        organization_id=body.organization_id,
    )
    return DataResponse(
        data=await service.start_case(
            principal,
            organization_id=body.organization_id,
            recruitment_request_id=body.recruitment_request_id,
            staffing_slot_id=body.staffing_slot_id,
            business_key=body.business_key,
            process_engine=body.process_engine,
            camunda_process_instance_key=body.camunda_process_instance_key,
        )
    )


@router.post("/cases/{case_id}/actions", response_model=DataResponse[dict[str, Any]])
async def act_on_stage(
    case_id: UUID,
    body: StageActionBody,
    service: Service,
    principal: PrincipalDep,
    authorization: AuthorizationDep,
) -> DataResponse[dict[str, Any]]:
    await authorization.require(
        principal=principal,
        permission_code="regulated_hiring.stage.act",
        organization_id=body.organization_id,
    )
    return DataResponse(
        data=await service.act_on_stage(
            principal,
            case_id=case_id,
            organization_id=body.organization_id,
            expected_revision=body.expected_revision,
            action=body.action,
            idempotency_key=body.idempotency_key,
            reason=body.reason,
            evidence=body.evidence,
            return_to_sequence=body.return_to_sequence,
        )
    )


@router.post(
    "/cases/{case_id}/forms",
    response_model=DataResponse[dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
)
async def record_form(
    case_id: UUID,
    body: FormRecordBody,
    service: Service,
    principal: PrincipalDep,
    authorization: AuthorizationDep,
) -> DataResponse[dict[str, Any]]:
    await authorization.require(
        principal=principal,
        permission_code="regulated_hiring.form.manage",
        organization_id=body.organization_id,
    )
    return DataResponse(
        data=await service.record_form(
            principal,
            case_id=case_id,
            organization_id=body.organization_id,
            form_code=body.form_code,
            data=body.data,
            signed=body.signed,
            signers=body.signers,
            correction_reason=body.correction_reason,
            document_id=body.document_id,
        )
    )


@router.get("/cases/{case_id}", response_model=DataResponse[dict[str, Any]])
async def timeline(
    case_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: PrincipalDep,
    authorization: AuthorizationDep,
) -> DataResponse[dict[str, Any]]:
    await authorization.require(
        principal=principal,
        permission_code="regulated_hiring.read",
        organization_id=organization_id,
    )
    return DataResponse(data=await service.timeline(case_id, organization_id))


@router.post(
    "/authority-bindings",
    response_model=DataResponse[dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
)
async def create_authority_binding(
    body: AuthorityBindingBody,
    service: Service,
    principal: PrincipalDep,
    authorization: AuthorizationDep,
) -> DataResponse[dict[str, Any]]:
    await authorization.require(
        principal=principal,
        permission_code="regulated_hiring.authority.manage",
        organization_id=body.organization_id,
    )
    return DataResponse(
        data=await service.create_authority_binding(
            principal,
            organization_id=body.organization_id,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            authority_status=body.authority_status,
            source_id=body.source_id,
            assertion=body.assertion,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            granted_permissions=body.granted_permissions,
        )
    )
