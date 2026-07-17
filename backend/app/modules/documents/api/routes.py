from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.core.database.session import async_session_factory
from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.modules.documents.application.ports import DocumentStoragePort
from app.modules.documents.application.service import DocumentService
from app.modules.documents.infrastructure.operations import SqlAlchemyDocumentOperations
from app.modules.documents.infrastructure.storage_factory import build_document_storage
from app.shared.api import DataResponse

from .schemas import (
    AcknowledgeRequest,
    AssignAcknowledgementRequest,
    ChecklistItemRequest,
    DocumentRecordRequest,
    DocumentTypeRequest,
    GenerateDocumentRequest,
    ManualSignatureRequest,
    PublishTemplateRequest,
    RegisterDocumentRequest,
    TemplateRequest,
    TemplateVersionRequest,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def _storage(settings: Settings) -> DocumentStoragePort:
    return build_document_storage(settings)


def get_document_service(
    authorization: Annotated[AuthorizationPort, Depends(get_authorization_port)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentService:
    return DocumentService(
        SqlAlchemyDocumentOperations(async_session_factory),
        _storage(settings),
        authorization,
        maximum_size=settings.document_max_size_bytes,
        allowed_mime_types=frozenset(settings.document_allowed_mime_types),
        development=settings.is_development,
    )


Service = Annotated[DocumentService, Depends(get_document_service)]
CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


@router.get("/types", response_model=DataResponse[list[dict[str, Any]]])
async def list_types(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[list[dict[str, Any]]]:
    await service.require(principal, "documents.read", organization_id)
    return DataResponse(
        data=[dict(item) for item in await service._operations.list_types(organization_id)]
    )


@router.post("/types", response_model=DataResponse[dict[str, Any]], status_code=201)
async def create_type(
    body: DocumentTypeRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "documents.create", body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.create_type(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post("/templates", response_model=DataResponse[dict[str, Any]], status_code=201)
async def create_template(
    body: TemplateRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "documents.create", body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.create_template(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post(
    "/templates/{template_id}/versions",
    response_model=DataResponse[dict[str, Any]],
    status_code=201,
)
async def template_version(
    template_id: UUID, body: TemplateVersionRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "documents.create", body.organization_id)
    await service._operations.require_organization("template", template_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.add_template_version(
                template_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post("/template-versions/{version_id}/publish", response_model=DataResponse[dict[str, Any]])
async def publish_template(
    version_id: UUID, body: PublishTemplateRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "documents.review", body.organization_id)
    await service._operations.require_organization(
        "template_version", version_id, body.organization_id
    )
    return DataResponse(
        data=dict(
            await service._operations.publish_template_version(
                version_id, principal.user_id, body.revision, body.reason
            )
        )
    )


@router.post(
    "/records", response_model=DataResponse[dict[str, Any]], status_code=status.HTTP_201_CREATED
)
async def create_record(
    body: DocumentRecordRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "documents.create", body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.create_record(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.get("/records/{document_id}", response_model=DataResponse[dict[str, Any]])
async def get_record(
    document_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "documents.read", organization_id)
    await service._assert_organization(document_id, organization_id)
    return DataResponse(data=dict(await service._operations.get_record(document_id)))


@router.post(
    "/records/{document_id}/versions", response_model=DataResponse[dict[str, Any]], status_code=201
)
async def upload_version(
    document_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
    file: Annotated[UploadFile, File()],
) -> DataResponse[dict[str, Any]]:
    async def chunks() -> AsyncIterator[bytes]:
        while chunk := await file.read(64 * 1024):
            yield chunk

    result = await service.upload(
        principal,
        organization_id,
        document_id,
        filename=file.filename or "document",
        mime_type=file.content_type or "application/octet-stream",
        chunks=chunks(),
    )
    return DataResponse(data=dict(result))


@router.post("/records/{document_id}/generate", response_model=DataResponse[dict[str, Any]])
async def generate_document(
    document_id: UUID,
    body: GenerateDocumentRequest,
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[dict[str, Any]]:
    result = await service.generate(
        principal,
        body.organization_id,
        document_id,
        filename=body.filename,
        mime_type=body.mime_type,
        variables=body.variables,
    )
    return DataResponse(data=dict(result))


@router.get("/records/{document_id}/versions/{version_id}/download")
async def download(
    document_id: UUID,
    version_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
) -> StreamingResponse:
    metadata, content = await service.download(principal, organization_id, document_id, version_id)
    return StreamingResponse(
        content,
        media_type=str(metadata["mimeType"]),
        headers={
            "Content-Disposition": f'attachment; filename="{metadata["safeFilename"]}"',
            "X-Content-SHA256": str(metadata["sha256"]),
        },
    )


@router.post("/records/{document_id}/register", response_model=DataResponse[dict[str, Any]])
async def register(
    document_id: UUID, body: RegisterDocumentRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "documents.register", body.organization_id)
    await service._assert_organization(document_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.register(
                document_id,
                principal.user_id,
                body.revision,
                body.registration_number,
                body.registration_date.isoformat(),
            )
        )
    )


@router.post("/records/{document_id}/manual-signature", response_model=DataResponse[dict[str, Any]])
async def manual_signature(
    document_id: UUID, body: ManualSignatureRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=dict(
            await service.manual_signature(
                principal,
                body.organization_id,
                document_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.get("/records/{document_id}/signatures", response_model=DataResponse[list[dict[str, Any]]])
async def signature_status(
    document_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[list[dict[str, Any]]]:
    await service.require(principal, "documents.read", organization_id)
    await service._assert_organization(document_id, organization_id)
    return DataResponse(
        data=[dict(item) for item in await service._operations.signature_status(document_id)]
    )


@router.post(
    "/records/{document_id}/acknowledgements",
    response_model=DataResponse[dict[str, Any]],
    status_code=201,
)
async def assign_acknowledgement(
    document_id: UUID,
    body: AssignAcknowledgementRequest,
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "documents.acknowledge_assign", body.organization_id)
    await service._assert_organization(document_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.create_acknowledgement(
                document_id, principal.user_id, body.assigned_employee_id
            )
        )
    )


@router.post("/checklist-items", response_model=DataResponse[dict[str, Any]], status_code=201)
async def checklist_item(
    body: ChecklistItemRequest, service: Service, principal: CurrentPrincipal
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "documents.create", body.organization_id)
    return DataResponse(
        data=dict(
            await service._operations.create_checklist_item(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.get(
    "/checklists/{business_type}/{business_id}/missing",
    response_model=DataResponse[list[dict[str, Any]]],
)
async def missing_checklist(
    business_type: str,
    business_id: UUID,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[list[dict[str, Any]]]:
    await service.require(principal, "documents.read", organization_id)
    return DataResponse(
        data=[
            dict(item)
            for item in await service._operations.validate_checklist(
                business_type, business_id, organization_id
            )
        ]
    )


@router.post(
    "/acknowledgements/{acknowledgement_id}/acknowledge",
    response_model=DataResponse[dict[str, Any]],
)
async def acknowledge(
    acknowledgement_id: UUID,
    body: AcknowledgeRequest,
    service: Service,
    principal: CurrentPrincipal,
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "documents.acknowledge", body.organization_id)
    await service._operations.require_organization(
        "acknowledgement", acknowledgement_id, body.organization_id
    )
    return DataResponse(
        data=dict(
            await service._operations.acknowledge(
                acknowledgement_id,
                principal.user_id,
                body.organization_id,
                body.revision,
                body.evidence,
            )
        )
    )
