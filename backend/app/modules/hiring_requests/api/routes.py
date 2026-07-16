from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.core.database.session import async_session_factory
from app.core.errors import ForbiddenError, ResourceNotFoundError
from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.modules.documents.api.routes import get_document_service
from app.modules.documents.application.service import DocumentService
from app.modules.employees.infrastructure.crypto import FernetSensitiveDataProtector
from app.shared.api import DataResponse

from ..service import HiringRequestService
from .schemas import (
    AcknowledgeRequest,
    ApprovalDecisionRequest,
    HiringRequestCreate,
    HiringRequestUpdate,
    OrganizationAction,
)

router = APIRouter(prefix="/hiring-requests", tags=["hiring requests"])


def get_hiring_service(
    authorization: Annotated[AuthorizationPort, Depends(get_authorization_port)],
    documents: Annotated[DocumentService, Depends(get_document_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HiringRequestService:
    return HiringRequestService(
        async_session_factory,
        authorization,
        FernetSensitiveDataProtector(settings.require_sensitive_data_key()),
        documents,
    )


Service = Annotated[HiringRequestService, Depends(get_hiring_service)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.post("", response_model=DataResponse[dict[str, Any]], status_code=status.HTTP_201_CREATED)
async def create_request(
    body: HiringRequestCreate, service: Service, principal: PrincipalDependency
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=await service.create(
            principal,
            body.organization_id,
            body.model_dump(by_alias=True, exclude={"organization_id"}),
        )
    )


@router.get("", response_model=DataResponse[list[dict[str, Any]]])
async def list_requests(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: PrincipalDependency,
    scope: str | None = None,
) -> DataResponse[list[dict[str, Any]]]:
    return DataResponse(data=await service.list(principal, organization_id, scope))


@router.get("/{request_id}", response_model=DataResponse[dict[str, Any]])
async def get_request(
    request_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: PrincipalDependency,
) -> DataResponse[dict[str, Any]]:
    return DataResponse(data=await service.get(principal, request_id, organization_id))


@router.patch("/{request_id}", response_model=DataResponse[dict[str, Any]])
async def update_request(
    request_id: UUID, body: HiringRequestUpdate, service: Service, principal: PrincipalDependency
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=await service.update(
            principal,
            request_id,
            body.organization_id,
            body.revision,
            body.model_dump(by_alias=True, exclude={"organization_id", "revision"}),
        )
    )


@router.post(
    "/{request_id}/attachments", response_model=DataResponse[dict[str, Any]], status_code=201
)
async def upload_attachment(
    request_id: UUID,
    service: Service,
    principal: PrincipalDependency,
    organization_id: Annotated[UUID, Form(alias="organizationId")],
    category: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> DataResponse[dict[str, Any]]:
    async def chunks() -> AsyncIterator[bytes]:
        while chunk := await file.read(64 * 1024):
            yield chunk

    result = await service.upload_attachment(
        principal,
        request_id,
        organization_id,
        category,
        file.filename or "document",
        file.content_type or "application/octet-stream",
        chunks(),
    )
    return DataResponse(data=result)


@router.post("/{request_id}/generate-pdf", response_model=DataResponse[dict[str, Any]])
async def generate_pdf(
    request_id: UUID, body: OrganizationAction, service: Service, principal: PrincipalDependency
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=await service.generate_pdf(principal, request_id, body.organization_id)
    )


@router.post("/{request_id}/submit", response_model=DataResponse[dict[str, Any]])
async def submit_request(
    request_id: UUID, body: OrganizationAction, service: Service, principal: PrincipalDependency
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=await service.submit(principal, request_id, body.organization_id, body.revision)
    )


@router.post("/{request_id}/decision", response_model=DataResponse[dict[str, Any]])
async def decide(
    request_id: UUID,
    body: ApprovalDecisionRequest,
    service: Service,
    principal: PrincipalDependency,
) -> DataResponse[dict[str, Any]]:
    result, final = await service.decide(
        principal, request_id, body.organization_id, body.revision, body.decision, body.comment
    )
    if final:
        await service.generate_pdf(principal, request_id, body.organization_id, final=True)
        result = await service.get(principal, request_id, body.organization_id)
    return DataResponse(data=result)


@router.post("/{request_id}/dispatch", response_model=DataResponse[dict[str, Any]])
async def dispatch(
    request_id: UUID, body: OrganizationAction, service: Service, principal: PrincipalDependency
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=await service.dispatch(principal, request_id, body.organization_id, body.revision)
    )


@router.post("/{request_id}/acknowledge", response_model=DataResponse[dict[str, Any]])
async def acknowledge(
    request_id: UUID, body: AcknowledgeRequest, service: Service, principal: PrincipalDependency
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=await service.acknowledge(
            principal, request_id, body.organization_id, body.revision, body.comment
        )
    )


@router.get("/{request_id}/documents/{version_id}/download")
async def download_document(
    request_id: UUID,
    version_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: PrincipalDependency,
    documents: Annotated[DocumentService, Depends(get_document_service)],
    inline: bool = False,
) -> StreamingResponse:
    details = await service.get(principal, request_id, organization_id)
    allowed: dict[UUID, UUID] = {}
    if details.get("pdfVersionId") and details.get("pdfDocumentId"):
        allowed[UUID(str(details["pdfVersionId"]))] = UUID(str(details["pdfDocumentId"]))
    if details.get("finalPdfVersionId") and details.get("pdfDocumentId"):
        allowed[UUID(str(details["finalPdfVersionId"]))] = UUID(str(details["pdfDocumentId"]))
    for attachment in details["attachments"]:
        allowed[UUID(str(attachment["versionId"]))] = UUID(str(attachment["documentId"]))
    document_id = allowed.get(version_id)
    if document_id is None:
        raise ResourceNotFoundError("hiring request document", version_id)
    try:
        metadata, content = await documents.download(
            principal, organization_id, document_id, version_id, sensitive=True
        )
    except ForbiddenError:
        raise
    disposition = "inline" if inline else "attachment"
    return StreamingResponse(
        content,
        media_type=str(metadata["mimeType"]),
        headers={
            "Content-Disposition": f'{disposition}; filename="{metadata["safeFilename"]}"',
            "X-Content-SHA256": str(metadata["sha256"]),
        },
    )
