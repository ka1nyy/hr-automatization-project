from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.audit.service import AuditService
from app.core.errors import ConcurrencyConflictError, ResourceNotFoundError, ValidationError
from app.core.errors.codes import ErrorCode
from app.modules.employees.infrastructure.models import EmployeeModel
from app.modules.identity.infrastructure.models import UserAccountModel
from app.shared.time import utc_now

from .models import (
    DocumentAcknowledgementModel,
    DocumentChecklistItemModel,
    DocumentRecordModel,
    DocumentSignatureModel,
    DocumentTemplateModel,
    DocumentTemplateVersionModel,
    DocumentTypeModel,
    DocumentVersionModel,
)


class SqlAlchemyDocumentOperations:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def require_organization(
        self, resource: str, resource_id: UUID, organization_id: UUID
    ) -> None:
        async with self._sessions() as session:
            if resource == "template":
                actual = await session.scalar(
                    select(DocumentTemplateModel.organization_id).where(
                        DocumentTemplateModel.id == resource_id
                    )
                )
            elif resource == "template_version":
                actual = await session.scalar(
                    select(DocumentTemplateModel.organization_id)
                    .join(
                        DocumentTemplateVersionModel,
                        DocumentTemplateVersionModel.template_id == DocumentTemplateModel.id,
                    )
                    .where(DocumentTemplateVersionModel.id == resource_id)
                )
            elif resource == "acknowledgement":
                actual = await session.scalar(
                    select(DocumentRecordModel.organization_id)
                    .join(
                        DocumentAcknowledgementModel,
                        DocumentAcknowledgementModel.document_id == DocumentRecordModel.id,
                    )
                    .where(DocumentAcknowledgementModel.id == resource_id)
                )
            else:
                raise ResourceNotFoundError("document resource")
            if actual != organization_id:
                raise ResourceNotFoundError(resource, resource_id)

    async def list_types(self, organization_id: UUID) -> Sequence[Mapping[str, object]]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(DocumentTypeModel)
                    .where(DocumentTypeModel.organization_id == organization_id)
                    .order_by(DocumentTypeModel.code)
                )
            ).all()
            return [_type_view(row) for row in rows]

    async def create_type(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            row = DocumentTypeModel(
                organization_id=organization_id,
                code=str(data["code"]),
                name=str(data["name"]),
                description=cast(str | None, data.get("description")),
                default_confidentiality=str(data.get("defaultConfidentiality", "internal")),
                allowed_mime_types=list(cast(Sequence[str], data.get("allowedMimeTypes", ()))),
                maximum_size_bytes=int(cast(int, data.get("maximumSizeBytes", 10_485_760))),
                active=True,
            )
            session.add(row)
            await session.flush()
            await _audit(
                session,
                actor_id,
                organization_id,
                "document.type.created",
                "documentType",
                row.id,
                _type_view(row),
            )
            return _type_view(row)

    async def create_template(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            document_type = await _required(
                session,
                DocumentTypeModel,
                UUID(str(data["documentTypeId"])),
                "document type",
            )
            if document_type.organization_id != organization_id:
                raise ResourceNotFoundError("document type", document_type.id)
            row = DocumentTemplateModel(
                organization_id=organization_id,
                document_type_id=UUID(str(data["documentTypeId"])),
                code=str(data["code"]),
                name=str(data["name"]),
                active=True,
            )
            session.add(row)
            await session.flush()
            await _audit(
                session,
                actor_id,
                organization_id,
                "document.template.created",
                "documentTemplate",
                row.id,
                _template_view(row),
            )
            return _template_view(row)

    async def add_template_version(
        self, template_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            template = await _required(
                session, DocumentTemplateModel, template_id, "document template"
            )
            versions = (
                await session.scalars(
                    select(DocumentTemplateVersionModel).where(
                        DocumentTemplateVersionModel.template_id == template_id
                    )
                )
            ).all()
            row = DocumentTemplateVersionModel(
                template_id=template_id,
                version_number=max((item.version_number for item in versions), default=0) + 1,
                status="draft",
                based_on_version_id=UUID(str(data["basedOnVersionId"]))
                if data.get("basedOnVersionId")
                else None,
                storage_key=str(data["storageKey"]),
                content_sha256=str(data["contentSha256"]),
                variable_schema=dict(cast(Mapping[str, Any], data.get("variableSchema", {}))),
                created_by=actor_id,
                created_at=utc_now(),
            )
            session.add(row)
            await session.flush()
            await _audit(
                session,
                actor_id,
                template.organization_id,
                "document.template.version.created",
                "documentTemplateVersion",
                row.id,
                _template_version_view(row),
            )
            return _template_version_view(row)

    async def publish_template_version(
        self, version_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            row = await _required(
                session, DocumentTemplateVersionModel, version_id, "document template version"
            )
            _revision(row.revision, revision)
            if row.status not in {"draft", "in_review"}:
                raise ValidationError(
                    "Only draft template versions can be published.",
                    code=ErrorCode.DOCUMENT_VERSION_IMMUTABLE,
                )
            template = await _required(
                session, DocumentTemplateModel, row.template_id, "document template"
            )
            old = (
                await session.scalars(
                    select(DocumentTemplateVersionModel).where(
                        DocumentTemplateVersionModel.template_id == row.template_id,
                        DocumentTemplateVersionModel.status == "published",
                    )
                )
            ).all()
            for item in old:
                item.status = "archived"
            row.status = "published"
            row.published_by = actor_id
            row.published_at = utc_now()
            row.revision += 1
            await _audit(
                session,
                actor_id,
                template.organization_id,
                "document.template.version.published",
                "documentTemplateVersion",
                row.id,
                _template_version_view(row),
                reason,
            )
            return _template_version_view(row)

    async def create_record(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            document_type = await _required(
                session,
                DocumentTypeModel,
                UUID(str(data["documentTypeId"])),
                "document type",
            )
            if document_type.organization_id != organization_id:
                raise ResourceNotFoundError("document type", document_type.id)
            row = DocumentRecordModel(
                organization_id=organization_id,
                document_type_id=UUID(str(data["documentTypeId"])),
                template_version_id=UUID(str(data["templateVersionId"]))
                if data.get("templateVersionId")
                else None,
                process_instance_id=UUID(str(data["processInstanceId"]))
                if data.get("processInstanceId")
                else None,
                business_entity_type=str(data["businessEntityType"]),
                business_entity_id=UUID(str(data["businessEntityId"])),
                title=str(data["title"]),
                status="draft",
                current_version_number=0,
                confidentiality_level=str(data.get("confidentialityLevel", "internal")),
                created_by=actor_id,
            )
            session.add(row)
            await session.flush()
            await _audit(
                session,
                actor_id,
                organization_id,
                "document.record.created",
                "documentRecord",
                row.id,
                _record_view(row),
            )
            return _record_view(row)

    async def add_version(
        self, document_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            document = await _required(session, DocumentRecordModel, document_id, "document")
            if document.status in {"signed", "registered", "archived", "voided"}:
                raise ValidationError(
                    "Historical documents cannot be overwritten.",
                    code=ErrorCode.DOCUMENT_VERSION_IMMUTABLE,
                )
            number = document.current_version_number + 1
            row = DocumentVersionModel(
                document_id=document_id,
                version_number=number,
                storage_key=str(data["storageKey"]),
                original_filename=str(data["originalFilename"]),
                safe_filename=str(data["safeFilename"]),
                mime_type=str(data["mimeType"]),
                size_bytes=int(cast(int, data["sizeBytes"])),
                sha256=str(data["sha256"]),
                author_user_id=actor_id,
                source_type=str(data["sourceType"]),
                metadata_={},
                immutable=False,
                created_at=utc_now(),
            )
            session.add(row)
            document.current_version_number = number
            document.status = "uploaded"
            document.revision += 1
            await session.flush()
            await _audit(
                session,
                actor_id,
                document.organization_id,
                "document.version.uploaded",
                "documentVersion",
                row.id,
                _version_view(row),
            )
            return _version_view(row)

    async def get_record(self, document_id: UUID) -> Mapping[str, object]:
        async with self._sessions() as session:
            return _record_view(
                await _required(session, DocumentRecordModel, document_id, "document")
            )

    async def get_version(self, document_id: UUID, version_id: UUID) -> Mapping[str, object]:
        async with self._sessions() as session:
            row = await _required(session, DocumentVersionModel, version_id, "document version")
            if row.document_id != document_id:
                raise ResourceNotFoundError("document version", version_id)
            return _version_view(row)

    async def get_generation_source(self, document_id: UUID) -> Mapping[str, object]:
        async with self._sessions() as session:
            document = await _required(session, DocumentRecordModel, document_id, "document")
            if document.template_version_id is None:
                raise ValidationError(
                    "A document template is required.", code=ErrorCode.DOCUMENT_REQUIRED
                )
            version = await _required(
                session,
                DocumentTemplateVersionModel,
                document.template_version_id,
                "template version",
            )
            if version.status != "published":
                raise ValidationError(
                    "A published template version is required.", code=ErrorCode.DOCUMENT_REQUIRED
                )
            return {
                "organizationId": document.organization_id,
                "storageKey": version.storage_key,
                "templateVersionId": version.id,
                "variableSchema": version.variable_schema,
            }

    async def register(
        self, document_id: UUID, actor_id: UUID, revision: int, number: str, registration_date: str
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            row = await _required(session, DocumentRecordModel, document_id, "document")
            _revision(row.revision, revision)
            row.registration_number = number
            row.registration_date = date.fromisoformat(registration_date)
            row.status = "registered"
            row.revision += 1
            versions = (
                await session.scalars(
                    select(DocumentVersionModel).where(DocumentVersionModel.document_id == row.id)
                )
            ).all()
            for version in versions:
                version.immutable = True
            await _audit(
                session,
                actor_id,
                row.organization_id,
                "document.registered",
                "documentRecord",
                row.id,
                _record_view(row),
            )
            return _record_view(row)

    async def signature(
        self, document_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            document = await _required(session, DocumentRecordModel, document_id, "document")
            versions = (
                await session.scalars(
                    select(DocumentVersionModel)
                    .where(DocumentVersionModel.document_id == document_id)
                    .order_by(DocumentVersionModel.version_number.desc())
                )
            ).all()
            if not versions:
                raise ValidationError(
                    "A document version is required.", code=ErrorCode.DOCUMENT_REQUIRED
                )
            status = str(data.get("status", "pending_external"))
            manual = bool(data.get("manualConfirmation", False))
            row = DocumentSignatureModel(
                document_id=document_id,
                document_version_id=versions[0].id,
                signer_user_id=UUID(str(data.get("signerUserId", actor_id))),
                status=status,
                provider_reference=cast(str | None, data.get("providerReference")),
                manual_confirmation=manual,
                requested_at=utc_now(),
                resolved_at=utc_now() if status in {"signed", "rejected", "failed"} else None,
                evidence_metadata=dict(cast(Mapping[str, Any], data.get("evidenceMetadata", {}))),
            )
            session.add(row)
            if status == "signed":
                document.status = "signed"
                document.revision += 1
                versions[0].immutable = True
            await session.flush()
            await _audit(
                session,
                actor_id,
                document.organization_id,
                "document.signature.changed",
                "documentSignature",
                row.id,
                _signature_view(row),
            )
            return _signature_view(row)

    async def acknowledge(
        self,
        acknowledgement_id: UUID,
        actor_id: UUID,
        organization_id: UUID,
        revision: int,
        evidence: Mapping[str, object],
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            row = await _required(
                session,
                DocumentAcknowledgementModel,
                acknowledgement_id,
                "document acknowledgement",
            )
            _revision(row.revision, revision)
            document = await _required(session, DocumentRecordModel, row.document_id, "document")
            account = await session.get(UserAccountModel, actor_id)
            if (
                document.organization_id != organization_id
                or account is None
                or account.employee_id != row.assigned_employee_id
            ):
                raise ResourceNotFoundError("document acknowledgement", acknowledgement_id)
            row.status = "acknowledged"
            row.acknowledged_at = utc_now()
            row.evidence_metadata = dict(evidence)
            row.revision += 1
            await _audit(
                session,
                actor_id,
                document.organization_id,
                "document.acknowledged",
                "documentAcknowledgement",
                row.id,
                {**_ack_view(row), "evidenceMetadata": "[redacted]"},
            )
            return _ack_view(row)

    async def create_acknowledgement(
        self, document_id: UUID, actor_id: UUID, assigned_employee_id: UUID
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            document = await _required(session, DocumentRecordModel, document_id, "document")
            employee = await _required(
                session, EmployeeModel, assigned_employee_id, "assigned employee"
            )
            if employee.organization_id != document.organization_id:
                raise ResourceNotFoundError("assigned employee", assigned_employee_id)
            version = await session.scalar(
                select(DocumentVersionModel)
                .where(DocumentVersionModel.document_id == document.id)
                .order_by(DocumentVersionModel.version_number.desc())
            )
            if version is None:
                raise ValidationError(
                    "A document version is required.", code=ErrorCode.DOCUMENT_REQUIRED
                )
            row = DocumentAcknowledgementModel(
                document_id=document.id,
                document_version_id=version.id,
                assigned_employee_id=assigned_employee_id,
                assigned_at=utc_now(),
                status="assigned",
                evidence_metadata={},
            )
            session.add(row)
            await session.flush()
            await _audit(
                session,
                actor_id,
                document.organization_id,
                "document.acknowledgement.assigned",
                "documentAcknowledgement",
                row.id,
                _ack_view(row),
            )
            return _ack_view(row)

    async def signature_status(self, document_id: UUID) -> Sequence[Mapping[str, object]]:
        async with self._sessions() as session:
            await _required(session, DocumentRecordModel, document_id, "document")
            rows = (
                await session.scalars(
                    select(DocumentSignatureModel)
                    .where(DocumentSignatureModel.document_id == document_id)
                    .order_by(DocumentSignatureModel.requested_at.desc())
                )
            ).all()
            return [_signature_view(row) for row in rows]

    async def create_checklist_item(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> Mapping[str, object]:
        async with self._sessions.begin() as session:
            business_type = str(data["businessEntityType"])
            business_id = UUID(str(data["businessEntityId"]))
            business_org = await _business_entity_organization(session, business_type, business_id)
            if business_org != organization_id:
                raise ResourceNotFoundError("checklist business entity", business_id)
            document_type = await _required(
                session,
                DocumentTypeModel,
                UUID(str(data["documentTypeId"])),
                "document type",
            )
            if document_type.organization_id != organization_id:
                raise ResourceNotFoundError("document type", document_type.id)
            if data.get("documentId"):
                document = await _required(
                    session,
                    DocumentRecordModel,
                    UUID(str(data["documentId"])),
                    "document",
                )
                if document.organization_id != organization_id:
                    raise ResourceNotFoundError("document", document.id)
            row = DocumentChecklistItemModel(
                organization_id=organization_id,
                process_instance_id=UUID(str(data["processInstanceId"]))
                if data.get("processInstanceId")
                else None,
                business_entity_type=business_type,
                business_entity_id=business_id,
                document_type_id=UUID(str(data["documentTypeId"])),
                document_id=UUID(str(data["documentId"])) if data.get("documentId") else None,
                mandatory=bool(data.get("mandatory", True)),
                status=str(data.get("status", "missing")),
                rejection_comment=cast(str | None, data.get("rejectionComment")),
            )
            session.add(row)
            await session.flush()
            await _audit(
                session,
                actor_id,
                organization_id,
                "document.checklist.created",
                "documentChecklistItem",
                row.id,
                _checklist_view(row),
            )
            return _checklist_view(row)

    async def validate_checklist(
        self, business_type: str, business_id: UUID, organization_id: UUID
    ) -> Sequence[Mapping[str, object]]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(DocumentChecklistItemModel).where(
                        DocumentChecklistItemModel.business_entity_type == business_type,
                        DocumentChecklistItemModel.business_entity_id == business_id,
                        DocumentChecklistItemModel.organization_id == organization_id,
                        DocumentChecklistItemModel.mandatory.is_(True),
                        DocumentChecklistItemModel.status != "validated",
                    )
                )
            ).all()
            return [_checklist_view(row) for row in rows]


async def _business_entity_organization(
    session: AsyncSession, business_type: str, business_id: UUID
) -> UUID | None:
    from app.modules.recruitment.infrastructure.models import (
        CandidateApplicationModel,
        HiringCaseModel,
        RecruitmentRequestModel,
        VacancyModel,
    )
    from app.modules.termination.infrastructure.models import TerminationCaseModel

    if business_type == "hiringCase":
        return cast(
            UUID | None,
            await session.scalar(
                select(HiringCaseModel.organization_id).where(HiringCaseModel.id == business_id)
            ),
        )
    if business_type == "terminationCase":
        return cast(
            UUID | None,
            await session.scalar(
                select(TerminationCaseModel.organization_id).where(
                    TerminationCaseModel.id == business_id
                )
            ),
        )
    if business_type == "recruitmentRequest":
        return cast(
            UUID | None,
            await session.scalar(
                select(RecruitmentRequestModel.organization_id).where(
                    RecruitmentRequestModel.id == business_id
                )
            ),
        )
    if business_type == "vacancy":
        return cast(
            UUID | None,
            await session.scalar(
                select(VacancyModel.organization_id).where(VacancyModel.id == business_id)
            ),
        )
    if business_type == "candidateApplication":
        return cast(
            UUID | None,
            await session.scalar(
                select(VacancyModel.organization_id)
                .join(
                    CandidateApplicationModel,
                    CandidateApplicationModel.vacancy_id == VacancyModel.id,
                )
                .where(CandidateApplicationModel.id == business_id)
            ),
        )
    raise ValidationError("Unsupported checklist business entity type.")


async def _required(session: AsyncSession, model: Any, identity: UUID, resource: str) -> Any:
    row = await session.get(model, identity)
    if row is None:
        raise ResourceNotFoundError(resource, identity)
    return row


def _revision(actual: int, expected: int) -> None:
    if actual != expected:
        raise ConcurrencyConflictError(
            details={"expectedRevision": expected, "actualRevision": actual}
        )


async def _audit(
    session: AsyncSession,
    actor: UUID,
    organization: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    after: Mapping[str, object],
    reason: str | None = None,
) -> None:
    await AuditService(SqlAlchemyAuditLog(session)).record(
        actor_id=actor,
        organization_id=organization,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        after_state=after,
        reason=reason,
    )


def _type_view(r: DocumentTypeModel) -> dict[str, object]:
    return {
        "id": r.id,
        "organizationId": r.organization_id,
        "code": r.code,
        "name": r.name,
        "description": r.description,
        "defaultConfidentiality": r.default_confidentiality,
        "allowedMimeTypes": r.allowed_mime_types,
        "maximumSizeBytes": r.maximum_size_bytes,
        "active": r.active,
        "revision": r.revision,
    }


def _template_view(r: DocumentTemplateModel) -> dict[str, object]:
    return {
        "id": r.id,
        "organizationId": r.organization_id,
        "documentTypeId": r.document_type_id,
        "code": r.code,
        "name": r.name,
        "active": r.active,
    }


def _template_version_view(r: DocumentTemplateVersionModel) -> dict[str, object]:
    return {
        "id": r.id,
        "templateId": r.template_id,
        "versionNumber": r.version_number,
        "status": r.status,
        "storageKey": r.storage_key,
        "contentSha256": r.content_sha256,
        "variableSchema": r.variable_schema,
        "revision": r.revision,
    }


def _record_view(r: DocumentRecordModel) -> dict[str, object]:
    return {
        "id": r.id,
        "organizationId": r.organization_id,
        "documentTypeId": r.document_type_id,
        "templateVersionId": r.template_version_id,
        "processInstanceId": r.process_instance_id,
        "businessEntityType": r.business_entity_type,
        "businessEntityId": r.business_entity_id,
        "title": r.title,
        "status": r.status,
        "registrationNumber": r.registration_number,
        "registrationDate": r.registration_date,
        "currentVersionNumber": r.current_version_number,
        "confidentialityLevel": r.confidentiality_level,
        "revision": r.revision,
    }


def _version_view(r: DocumentVersionModel) -> dict[str, object]:
    return {
        "id": r.id,
        "documentId": r.document_id,
        "versionNumber": r.version_number,
        "storageKey": r.storage_key,
        "originalFilename": r.original_filename,
        "safeFilename": r.safe_filename,
        "mimeType": r.mime_type,
        "sizeBytes": r.size_bytes,
        "sha256": r.sha256,
        "sourceType": r.source_type,
        "immutable": r.immutable,
        "createdAt": r.created_at,
    }


def _signature_view(r: DocumentSignatureModel) -> dict[str, object]:
    return {
        "id": r.id,
        "documentId": r.document_id,
        "documentVersionId": r.document_version_id,
        "signerUserId": r.signer_user_id,
        "status": r.status,
        "providerReference": r.provider_reference,
        "manualConfirmation": r.manual_confirmation,
        "requestedAt": r.requested_at,
        "resolvedAt": r.resolved_at,
        "revision": r.revision,
    }


def _ack_view(r: DocumentAcknowledgementModel) -> dict[str, object]:
    return {
        "id": r.id,
        "documentId": r.document_id,
        "documentVersionId": r.document_version_id,
        "assignedEmployeeId": r.assigned_employee_id,
        "assignedAt": r.assigned_at,
        "acknowledgedAt": r.acknowledged_at,
        "status": r.status,
        "evidenceMetadata": r.evidence_metadata,
        "revision": r.revision,
    }


def _checklist_view(r: DocumentChecklistItemModel) -> dict[str, object]:
    return {
        "id": r.id,
        "organizationId": r.organization_id,
        "businessEntityType": r.business_entity_type,
        "businessEntityId": r.business_entity_id,
        "documentTypeId": r.document_type_id,
        "documentId": r.document_id,
        "mandatory": r.mandatory,
        "status": r.status,
        "rejectionComment": r.rejection_comment,
        "revision": r.revision,
    }
