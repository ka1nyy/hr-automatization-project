from __future__ import annotations

import json
from calendar import monthrange
from collections.abc import AsyncIterator, Mapping
from datetime import date
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.audit.service import AuditService
from app.core.errors import ConflictError, ForbiddenError, ResourceNotFoundError, ValidationError
from app.core.events.domain import ApplicationEvent, EventName
from app.core.events.repository import SqlAlchemyTransactionalOutbox
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.modules.documents.application.service import DocumentService
from app.modules.documents.infrastructure.models import DocumentTypeModel
from app.modules.documents.infrastructure.operations import SqlAlchemyDocumentOperations
from app.modules.employees.infrastructure.crypto import FernetSensitiveDataProtector
from app.modules.employees.infrastructure.models import EmployeeModel, PersonModel
from app.modules.identity.infrastructure.models import UserAccountModel
from app.shared.identifiers import new_uuid
from app.shared.time import utc_now

from .domain import APPROVAL_STAGES, EDITABLE_STATUSES, REQUIRED_ATTACHMENT_CATEGORIES
from .infrastructure.models import (
    HiringApprovalDecisionModel,
    HiringAttachmentModel,
    HiringDispatchModel,
    HiringRequestModel,
)
from .pdf import render_hiring_request_pdf

MAX_EMPLOYEE_NUMBER = 999_999
DEPARTMENT_DIRECTORS = {
    "Департамент управления персоналом": "Сауле Бекенова",
    "Департамент документооборота и управления персоналом": "Сауле Бекенова",
    "Департамент цифровой трансформации": "Мирас Абдрахманов",
    "Строительный департамент": "Нуржан Тлеубаев",
    "Юридический департамент": "Елена Ким",
    "Департамент экономического планирования": "Руслан Ибраев",
}


def format_employee_identity(sequence_value: int) -> tuple[str, str]:
    """Return the public employee ID and its deterministic corporate e-mail."""

    if sequence_value < 1 or sequence_value > MAX_EMPLOYEE_NUMBER:
        raise ConflictError("The six-digit employee identifier range is exhausted")
    employee_number = f"{sequence_value:06d}"
    return employee_number, f"ertis{employee_number}@ertis.kz"


def calculate_probation_end(hire_date: date, probation_months: object) -> date | None:
    """Return the contractual probation end date, or None when probation is absent."""

    try:
        months = int(str(probation_months or 0))
    except (TypeError, ValueError):
        months = 0
    if months <= 0:
        return None
    month_index = hire_date.month - 1 + months
    year = hire_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(hire_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def resolve_department_director(department: object, requested_manager: object) -> str | None:
    """Resolve the department director stored on the hired employee profile."""

    department_name = str(department or "").strip()
    configured = DEPARTMENT_DIRECTORS.get(department_name)
    if configured:
        return configured
    manager = str(requested_manager or "").strip()
    return manager if manager and manager != "Не указан" else None


class HiringRequestService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        authorization: AuthorizationPort,
        protector: FernetSensitiveDataProtector,
        documents: DocumentService,
    ) -> None:
        self.sessions = sessions
        self.authorization = authorization
        self.protector = protector
        self.documents = documents
        self.document_operations = SqlAlchemyDocumentOperations(sessions)

    async def require(self, principal: Principal, permission: str, organization_id: UUID) -> None:
        await self.authorization.require(
            principal=principal, permission_code=permission, organization_id=organization_id
        )

    def _protect(self, personal: Mapping[str, Any]) -> str:
        return self.protector.protect(json.dumps(dict(personal), ensure_ascii=False)).decode(
            "ascii"
        )

    def _reveal(self, value: str) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.protector.reveal(value.encode("ascii"))))

    async def create(
        self, principal: Principal, organization_id: UUID, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        await self.require(principal, "hiring.request.create", organization_id)
        async with self.sessions.begin() as session:
            sequence = (
                int(
                    await session.scalar(
                        select(func.count())
                        .select_from(HiringRequestModel)
                        .where(HiringRequestModel.organization_id == organization_id)
                    )
                    or 0
                )
                + 1
            )
            row = HiringRequestModel(
                organization_id=organization_id,
                request_number=f"HR-HIRE-{utc_now().year}-{sequence:05d}",
                created_by=principal.user_id,
                protected_personal_data=self._protect(cast(Mapping[str, Any], payload["personal"])),
                employment_data=dict(cast(Mapping[str, Any], payload["employment"])),
                education_data=dict(cast(Mapping[str, Any], payload["education"])),
                status="draft",
                current_stage=0,
                approval_cycle=1,
            )
            session.add(row)
            await session.flush()
            await self._audit(
                session, principal.user_id, row, "hiring.request.created", None, "draft"
            )
            return await self._view(session, row, sensitive=True)

    async def update(
        self,
        principal: Principal,
        request_id: UUID,
        organization_id: UUID,
        revision: int,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        await self.require(principal, "hiring.request.create", organization_id)
        async with self.sessions.begin() as session:
            row = await self._locked(session, request_id, organization_id)
            self._owner_editable(row, principal, revision)
            before = row.status
            row.protected_personal_data = self._protect(
                cast(Mapping[str, Any], payload["personal"])
            )
            row.employment_data = dict(cast(Mapping[str, Any], payload["employment"]))
            row.education_data = dict(cast(Mapping[str, Any], payload["education"]))
            row.revision += 1
            await self._audit(
                session, principal.user_id, row, "hiring.request.draft_updated", before, row.status
            )
            return await self._view(session, row, sensitive=True)

    async def list(
        self, principal: Principal, organization_id: UUID, scope: str | None
    ) -> list[dict[str, Any]]:
        await self.require(principal, "hiring.request.read", organization_id)
        if scope is None and "system-administrator" not in principal.role_codes:
            scope = "mine"
        async with self.sessions() as session:
            stmt = select(HiringRequestModel).where(
                HiringRequestModel.organization_id == organization_id
            )
            if scope == "mine":
                stmt = stmt.where(HiringRequestModel.created_by == principal.user_id)
            elif scope == "dispatch":
                await self.require(principal, "hiring.request.dispatch", organization_id)
                stmt = stmt.where(
                    HiringRequestModel.created_by == principal.user_id,
                    HiringRequestModel.status == "final_approved",
                )
            elif scope == "inbox":
                allowed = []
                for index, stage in enumerate(APPROVAL_STAGES):
                    try:
                        await self.require(principal, stage.permission, organization_id)
                        allowed.append(index)
                    except ForbiddenError:
                        pass
                already_decided_in_cycle = (
                    select(HiringApprovalDecisionModel.id)
                    .where(
                        HiringApprovalDecisionModel.request_id == HiringRequestModel.id,
                        HiringApprovalDecisionModel.approval_cycle
                        == HiringRequestModel.approval_cycle,
                        HiringApprovalDecisionModel.approver_user_id == principal.user_id,
                    )
                    .exists()
                )
                stmt = stmt.where(
                    HiringRequestModel.status == "under_review",
                    HiringRequestModel.current_stage.in_(allowed or [-1]),
                    ~already_decided_in_cycle,
                )
            elif scope == "received":
                stmt = stmt.join(HiringDispatchModel).where(
                    HiringDispatchModel.assigned_user_id == principal.user_id,
                    HiringDispatchModel.status != "acknowledged",
                )
            elif scope is not None:
                raise ValidationError("Unsupported hiring request scope")
            rows = (
                await session.scalars(stmt.order_by(HiringRequestModel.created_at.desc()))
            ).all()
            return [await self._view(session, row, sensitive=False) for row in rows]

    async def get(
        self, principal: Principal, request_id: UUID, organization_id: UUID
    ) -> dict[str, Any]:
        await self.require(principal, "hiring.request.read", organization_id)
        async with self.sessions() as session:
            row = await self._required(session, request_id, organization_id)
            if not await self._can_access(session, row, principal):
                raise ForbiddenError()
            sensitive = True
            try:
                await self.require(principal, "hiring.request.read_sensitive", organization_id)
            except ForbiddenError:
                sensitive = False
            return await self._view(session, row, sensitive=sensitive)

    async def _can_access(
        self, session: AsyncSession, row: HiringRequestModel, principal: Principal
    ) -> bool:
        if "system-administrator" in principal.role_codes or row.created_by == principal.user_id:
            return True
        dispatch = await session.scalar(
            select(HiringDispatchModel.id).where(
                HiringDispatchModel.request_id == row.id,
                HiringDispatchModel.assigned_user_id == principal.user_id,
            )
        )
        if dispatch is not None:
            return True
        prior_decision = await session.scalar(
            select(HiringApprovalDecisionModel.id).where(
                HiringApprovalDecisionModel.request_id == row.id,
                HiringApprovalDecisionModel.approver_user_id == principal.user_id,
            )
        )
        if prior_decision is not None:
            return True
        if row.status == "under_review" and row.current_stage < len(APPROVAL_STAGES):
            try:
                await self.require(
                    principal, APPROVAL_STAGES[row.current_stage].permission, row.organization_id
                )
                return True
            except ForbiddenError:
                return False
        return False

    async def upload_attachment(
        self,
        principal: Principal,
        request_id: UUID,
        organization_id: UUID,
        category: str,
        filename: str,
        mime_type: str,
        chunks: AsyncIterator[bytes],
    ) -> dict[str, Any]:
        if category not in REQUIRED_ATTACHMENT_CATEGORIES:
            raise ValidationError("Unsupported hiring attachment category")
        await self.require(principal, "hiring.request.create", organization_id)
        async with self.sessions() as session:
            row = await self._required(session, request_id, organization_id)
            if row.created_by != principal.user_id or row.status not in EDITABLE_STATUSES:
                raise ForbiddenError()
            existing = await session.scalar(
                select(HiringAttachmentModel).where(
                    HiringAttachmentModel.request_id == request_id,
                    HiringAttachmentModel.category == category,
                )
            )
        if existing is None:
            type_code = "identity_document" if category == "identity" else "education_diploma"
            document_type_id = await self._document_type_id(organization_id, type_code)
            record = await self.document_operations.create_record(
                organization_id,
                principal.user_id,
                {
                    "documentTypeId": document_type_id,
                    "businessEntityType": "newEmployeeHiringRequest",
                    "businessEntityId": request_id,
                    "title": "Документ, удостоверяющий личность"
                    if category == "identity"
                    else "Диплом об образовании",
                    "confidentialityLevel": "restricted",
                },
            )
            document_id = UUID(str(record["id"]))
        else:
            document_id = existing.document_id
        version = await self.documents.upload(
            principal,
            organization_id,
            document_id,
            filename=filename,
            mime_type=mime_type,
            chunks=chunks,
        )
        async with self.sessions.begin() as session:
            row = await self._locked(session, request_id, organization_id)
            if row.created_by != principal.user_id or row.status not in EDITABLE_STATUSES:
                raise ConflictError("The request is no longer editable")
            existing = await session.scalar(
                select(HiringAttachmentModel)
                .where(
                    HiringAttachmentModel.request_id == request_id,
                    HiringAttachmentModel.category == category,
                )
                .with_for_update()
            )
            if existing is None:
                existing = HiringAttachmentModel(
                    request_id=request_id,
                    category=category,
                    document_id=document_id,
                    current_version_id=UUID(str(version["id"])),
                    original_filename=str(version["originalFilename"]),
                    size_bytes=int(str(version["sizeBytes"])),
                    mime_type=str(version["mimeType"]),
                )
                session.add(existing)
            else:
                existing.current_version_id = UUID(str(version["id"]))
                existing.original_filename = str(version["originalFilename"])
                existing.size_bytes = int(str(version["sizeBytes"]))
                existing.mime_type = str(version["mimeType"])
            row.revision += 1
            await self._audit(
                session,
                principal.user_id,
                row,
                "hiring.request.file_uploaded",
                row.status,
                row.status,
                category,
            )
        return dict(version)

    async def generate_pdf(
        self, principal: Principal, request_id: UUID, organization_id: UUID, final: bool = False
    ) -> dict[str, Any]:
        await self.require(
            principal,
            "hiring.request.create" if not final else "hiring.request.read",
            organization_id,
        )
        async with self.sessions() as session:
            row = await self._required(session, request_id, organization_id)
            if not final and (
                row.created_by != principal.user_id
                or row.status not in EDITABLE_STATUSES | {"pdf_generated"}
            ):
                raise ForbiddenError()
            details = await self._view(session, row, sensitive=True)
            if not final:
                self._validate_complete(details)
            document_id = row.pdf_document_id
            request_number = row.request_number
            previous_status = row.status
        content = render_hiring_request_pdf(
            details,
            cast(Mapping[str, Any], details["personal"]),
            cast(list[Mapping[str, Any]], details["attachments"]),
        )
        if document_id is None:
            document_type_id = await self._document_type_id(
                organization_id, "hiring_application_pdf"
            )
            record = await self.document_operations.create_record(
                organization_id,
                principal.user_id,
                {
                    "documentTypeId": document_type_id,
                    "businessEntityType": "newEmployeeHiringRequest",
                    "businessEntityId": request_id,
                    "title": "Заявление о найме нового сотрудника",
                    "confidentialityLevel": "restricted",
                },
            )
            document_id = UUID(str(record["id"]))

        async def chunks() -> AsyncIterator[bytes]:
            yield content

        surname = str(cast(Mapping[str, Any], details["personal"]).get("lastName", "candidate"))
        filename = f"hiring-request_{request_number}_{surname}_{utc_now().date().isoformat()}.pdf"
        version = await self.documents.upload(
            principal,
            organization_id,
            document_id,
            filename=filename,
            mime_type="application/pdf",
            chunks=chunks(),
            source_type="generated",
        )
        async with self.sessions.begin() as session:
            locked = await self._locked(session, request_id, organization_id)
            if not final and (
                locked.created_by != principal.user_id
                or locked.status not in EDITABLE_STATUSES | {"pdf_generated"}
            ):
                raise ConflictError("The request is no longer editable")
            locked.pdf_document_id = document_id
            locked.pdf_version_id = UUID(str(version["id"]))
            if final:
                locked.final_pdf_version_id = UUID(str(version["id"]))
            elif locked.status in EDITABLE_STATUSES:
                locked.status = "pdf_generated"
            locked.revision += 1
            await self._audit(
                session,
                principal.user_id,
                locked,
                "hiring.request.pdf_generated"
                if not final
                else "hiring.request.final_pdf_generated",
                previous_status,
                locked.status,
            )
        return dict(version)

    async def submit(
        self, principal: Principal, request_id: UUID, organization_id: UUID, revision: int
    ) -> dict[str, Any]:
        await self.require(principal, "hiring.request.create", organization_id)
        async with self.sessions.begin() as session:
            row = await self._locked(session, request_id, organization_id)
            if (
                row.created_by != principal.user_id
                or row.status != "pdf_generated"
                or row.revision != revision
            ):
                raise ConflictError("The request is not ready for submission")
            categories = set(
                (
                    await session.scalars(
                        select(HiringAttachmentModel.category).where(
                            HiringAttachmentModel.request_id == request_id
                        )
                    )
                ).all()
            )
            required_categories = {"identity"}
            if row.education_data.get("educationLevel") != "Среднее общее":
                required_categories.add("diploma")
            if not required_categories.issubset(categories) or row.pdf_version_id is None:
                raise ValidationError("PDF and both required attachments are required")
            has_prior_decisions = bool(
                await session.scalar(
                    select(func.count())
                    .select_from(HiringApprovalDecisionModel)
                    .where(
                        HiringApprovalDecisionModel.request_id == request_id,
                        HiringApprovalDecisionModel.approval_cycle == row.approval_cycle,
                    )
                )
            )
            if has_prior_decisions:
                row.approval_cycle += 1
            before = row.status
            row.status = "under_review"
            row.current_stage = 0
            row.submitted_at = utc_now()
            row.revision += 1
            await self._audit(
                session, principal.user_id, row, "hiring.request.submitted", before, row.status
            )
            await self._event(
                session, EventName.HIRING_REQUEST_SUBMITTED, row, {"stage": APPROVAL_STAGES[0].code}
            )
            return await self._view(session, row, sensitive=True)

    async def decide(
        self,
        principal: Principal,
        request_id: UUID,
        organization_id: UUID,
        revision: int,
        decision: str,
        comment: str,
    ) -> tuple[dict[str, Any], bool]:
        async with self.sessions.begin() as session:
            row = await self._locked(session, request_id, organization_id)
            if (
                row.status != "under_review"
                or row.revision != revision
                or row.current_stage >= len(APPROVAL_STAGES)
            ):
                raise ConflictError("The approval stage has already changed")
            stage = APPROVAL_STAGES[row.current_stage]
            await self.require(principal, stage.permission, organization_id)
            account = await session.get(UserAccountModel, principal.user_id)
            if account is None:
                raise ResourceNotFoundError("user account", principal.user_id)
            session.add(
                HiringApprovalDecisionModel(
                    request_id=row.id,
                    approval_cycle=row.approval_cycle,
                    stage_number=row.current_stage + 1,
                    stage_code=stage.code,
                    stage_name=stage.name,
                    approver_user_id=principal.user_id,
                    approver_name=account.display_name,
                    approver_role=stage.role_label,
                    decision=decision,
                    comment=comment or None,
                    decided_at=utc_now(),
                )
            )
            before = row.status
            final = False
            if decision == "return":
                row.status = "returned"
                row.current_stage = 0
            elif decision == "reject":
                row.status = "rejected"
            elif row.current_stage == len(APPROVAL_STAGES) - 1:
                row.status = "final_approved"
                row.final_approved_at = utc_now()
                final = True
            else:
                row.current_stage += 1
            row.revision += 1
            await self._audit(
                session,
                principal.user_id,
                row,
                f"hiring.request.{decision}",
                before,
                row.status,
                comment,
            )
            await self._event(
                session,
                EventName.HIRING_APPROVAL_DECIDED,
                row,
                {"decision": decision, "stage": stage.code, "status": row.status},
            )
            result = await self._view(session, row, sensitive=True)
        return result, final

    async def dispatch(
        self, principal: Principal, request_id: UUID, organization_id: UUID, revision: int
    ) -> dict[str, Any]:
        await self.require(principal, "hiring.request.dispatch", organization_id)
        async with self.sessions.begin() as session:
            row = await self._locked(session, request_id, organization_id)
            if (
                row.created_by != principal.user_id
                or row.status != "final_approved"
                or row.revision != revision
                or row.final_pdf_version_id is None
            ):
                raise ConflictError("The request is not ready for dispatch")
            recipients = {"accounting": "accountant", "it": "it.specialist"}
            for recipient, username in recipients.items():
                user = await session.scalar(
                    select(UserAccountModel).where(
                        UserAccountModel.username == username, UserAccountModel.active.is_(True)
                    )
                )
                if user is None:
                    raise ConflictError(f"Development recipient {username} is not configured")
                session.add(
                    HiringDispatchModel(
                        request_id=row.id,
                        recipient_type=recipient,
                        assigned_user_id=user.id,
                        assigned_at=utc_now(),
                        status="assigned",
                    )
                )
            before = row.status
            row.status = "dispatched"
            row.dispatched_at = utc_now()
            row.revision += 1
            await self._audit(
                session, principal.user_id, row, "hiring.request.dispatched", before, row.status
            )
            await self._event(
                session, EventName.HIRING_PACKAGE_DISPATCHED, row, {"recipients": list(recipients)}
            )
            return await self._view(session, row, sensitive=True)

    async def acknowledge(
        self,
        principal: Principal,
        request_id: UUID,
        organization_id: UUID,
        revision: int,
        comment: str,
    ) -> dict[str, Any]:
        await self.require(principal, "hiring.request.acknowledge", organization_id)
        async with self.sessions.begin() as session:
            row = await self._locked(session, request_id, organization_id)
            dispatch = await session.scalar(
                select(HiringDispatchModel)
                .where(
                    HiringDispatchModel.request_id == request_id,
                    HiringDispatchModel.assigned_user_id == principal.user_id,
                )
                .with_for_update()
            )
            if dispatch is None or dispatch.status == "acknowledged" or row.revision != revision:
                raise ConflictError("The package is not available for acknowledgement")
            dispatch.status = "acknowledged"
            dispatch.acknowledged_at = utc_now()
            dispatch.revision += 1
            await session.flush()
            pending = int(
                await session.scalar(
                    select(func.count())
                    .select_from(HiringDispatchModel)
                    .where(
                        HiringDispatchModel.request_id == request_id,
                        HiringDispatchModel.status != "acknowledged",
                    )
                )
                or 0
            )
            before = row.status
            row.status = "completed" if pending == 0 else "partially_acknowledged"
            if pending == 0:
                row.completed_at = utc_now()
                await self._auto_hire(session, row, principal.user_id)
            row.revision += 1
            await self._audit(
                session,
                principal.user_id,
                row,
                "hiring.request.acknowledged",
                before,
                row.status,
                comment,
            )
            await self._event(
                session,
                EventName.HIRING_PACKAGE_ACKNOWLEDGED,
                row,
                {"recipient": dispatch.recipient_type, "status": row.status},
            )
            return await self._view(session, row, sensitive=True)

    async def _auto_hire(
        self, session: AsyncSession, row: HiringRequestModel, actor_id: UUID
    ) -> EmployeeModel:
        """Create exactly one active employee when the hiring route is completed."""

        if row.hired_employee_id is not None:
            employee = await session.get(EmployeeModel, row.hired_employee_id)
            if employee is not None:
                return employee

        personal = self._reveal(row.protected_personal_data)
        employment = row.employment_data
        employee_id = new_uuid()
        person_id = new_uuid()
        timestamp = utc_now()
        sequence_value = await session.scalar(text("SELECT nextval('employee_number_seq')"))
        employee_number, corporate_email = format_employee_identity(int(sequence_value or 0))
        first_name = str(personal.get("firstName") or "").strip()
        last_name = str(personal.get("lastName") or "").strip()
        middle_name = str(personal.get("middleName") or "").strip() or None
        display_name = " ".join(filter(None, (last_name, first_name, middle_name)))
        birth_date_value = str(personal.get("birthDate") or "").strip()
        hire_date_value = str(employment.get("startDate") or "").strip()
        hire_date = date.fromisoformat(hire_date_value) if hire_date_value else timestamp.date()
        probation_end = calculate_probation_end(hire_date, employment.get("probationMonths"))
        position_title = str(employment.get("position") or "").strip() or None
        department_name = str(employment.get("department") or "").strip() or None
        manager_name = resolve_department_director(
            employment.get("department"), employment.get("manager")
        )
        employment_type_label = str(employment.get("employmentType") or "").strip() or None
        iin = str(personal.get("iin") or "").strip()

        person = PersonModel(
            id=person_id,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            display_name=display_name,
            protected_iin=self.protector.protect(iin) if iin else None,
            birth_date=date.fromisoformat(birth_date_value) if birth_date_value else None,
            personal_email=str(personal.get("personalEmail") or "").strip() or None,
            phone=str(personal.get("personalPhone") or "").strip() or None,
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
            revision=1,
        )
        employee = EmployeeModel(
            id=employee_id,
            organization_id=row.organization_id,
            created_by=row.created_by,
            person_id=person_id,
            employee_number=employee_number,
            employment_status="active",
            position_title=position_title,
            department_name=department_name,
            manager_name=manager_name,
            employment_type_label=employment_type_label,
            hire_date=hire_date,
            probation_end=probation_end,
            termination_date=None,
            corporate_email=corporate_email,
            active=True,
            created_at=timestamp,
            updated_at=timestamp,
            revision=1,
        )
        session.add(person)
        await session.flush()
        session.add(employee)
        await session.flush()
        row.hired_employee_id = employee.id

        await AuditService(SqlAlchemyAuditLog(session)).record(
            actor_id=actor_id,
            action="employee.hired.automatically",
            entity_type="employee",
            entity_id=employee.id,
            before_state=None,
            after_state={
                "hiringRequestId": str(row.id),
                "employeeNumber": employee_number,
                "corporateEmail": corporate_email,
                "positionTitle": position_title,
                "departmentName": department_name,
                "managerName": manager_name,
                "probationEnd": probation_end.isoformat() if probation_end else None,
            },
            organization_id=row.organization_id,
        )
        await SqlAlchemyTransactionalOutbox(session).append(
            ApplicationEvent(
                name=EventName.EMPLOYEE_HIRED,
                aggregate_type="employee",
                aggregate_id=employee.id,
                payload={
                    "employeeId": str(employee.id),
                    "organizationId": str(row.organization_id),
                    "hiringRequestId": str(row.id),
                    "hireDate": employee.hire_date.isoformat(),
                    "employeeNumber": employee_number,
                    "corporateEmail": corporate_email,
                    "positionTitle": position_title,
                    "departmentName": department_name,
                    "managerName": manager_name,
                    "probationEnd": probation_end.isoformat() if probation_end else None,
                },
            )
        )
        return employee

    async def _document_type_id(self, organization_id: UUID, code: str) -> UUID:
        async with self.sessions() as session:
            value = await session.scalar(
                select(DocumentTypeModel.id).where(
                    DocumentTypeModel.organization_id == organization_id,
                    DocumentTypeModel.code == code,
                    DocumentTypeModel.active.is_(True),
                )
            )
            if value is None:
                raise ResourceNotFoundError("document type", code)
            return value

    async def _view(
        self, session: AsyncSession, row: HiringRequestModel, sensitive: bool
    ) -> dict[str, Any]:
        personal = self._reveal(row.protected_personal_data)
        candidate = " ".join(
            filter(
                None,
                [personal.get("lastName"), personal.get("firstName"), personal.get("middleName")],
            )
        )
        attachments = (
            await session.scalars(
                select(HiringAttachmentModel)
                .where(HiringAttachmentModel.request_id == row.id)
                .order_by(HiringAttachmentModel.category)
            )
        ).all()
        dispatches = (
            await session.scalars(
                select(HiringDispatchModel)
                .where(HiringDispatchModel.request_id == row.id)
                .order_by(HiringDispatchModel.recipient_type)
            )
        ).all()
        creator = await session.get(UserAccountModel, row.created_by)
        if not sensitive:
            personal = {
                "lastName": personal.get("lastName"),
                "firstName": personal.get("firstName"),
                "middleName": personal.get("middleName"),
                "iin": f"******{str(personal.get('iin', ''))[-6:]}",
            }
        stage = (
            APPROVAL_STAGES[row.current_stage]
            if row.status == "under_review" and row.current_stage < len(APPROVAL_STAGES)
            else None
        )
        hired_employee = (
            await session.get(EmployeeModel, row.hired_employee_id)
            if row.hired_employee_id is not None
            else None
        )
        return {
            "id": row.id,
            "organizationId": row.organization_id,
            "requestNumber": row.request_number,
            "createdBy": row.created_by,
            "initiatorName": creator.display_name if creator else "—",
            "candidateName": candidate,
            "personal": personal,
            "employmentData": row.employment_data,
            "educationData": row.education_data,
            "status": row.status,
            "currentStage": row.current_stage + 1 if stage else None,
            "currentStageCode": stage.code if stage else None,
            "currentStageName": stage.name if stage else None,
            "approvalCycle": row.approval_cycle,
            "revision": row.revision,
            "pdfDocumentId": row.pdf_document_id,
            "pdfVersionId": row.pdf_version_id,
            "finalPdfVersionId": row.final_pdf_version_id,
            "createdAt": row.created_at,
            "updatedAt": row.updated_at,
            "submittedAt": row.submitted_at,
            "finalApprovedAt": row.final_approved_at,
            "dispatchedAt": row.dispatched_at,
            "completedAt": row.completed_at,
            "hiredEmployee": (
                {
                    "id": hired_employee.id,
                    "employeeNumber": hired_employee.employee_number,
                    "corporateEmail": hired_employee.corporate_email,
                }
                if hired_employee is not None
                else None
            ),
            "attachments": [
                {
                    "id": x.id,
                    "category": x.category,
                    "documentId": x.document_id,
                    "versionId": x.current_version_id,
                    "originalFilename": x.original_filename,
                    "sizeBytes": x.size_bytes,
                    "mimeType": x.mime_type,
                }
                for x in attachments
            ],
            # The route and decision history stay internal to the workflow engine.
            "decisions": [],
            "approvalStages": [],
            "dispatches": [
                {
                    "id": x.id,
                    "recipientType": x.recipient_type,
                    "assignedUserId": x.assigned_user_id,
                    "status": x.status,
                    "assignedAt": x.assigned_at,
                    "acknowledgedAt": x.acknowledged_at,
                    "revision": x.revision,
                }
                for x in dispatches
            ],
        }

    async def _required(
        self, session: AsyncSession, request_id: UUID, organization_id: UUID
    ) -> HiringRequestModel:
        row = await session.get(HiringRequestModel, request_id)
        if row is None or row.organization_id != organization_id:
            raise ResourceNotFoundError("hiring request", request_id)
        return row

    async def _locked(
        self, session: AsyncSession, request_id: UUID, organization_id: UUID
    ) -> HiringRequestModel:
        row = await session.scalar(
            select(HiringRequestModel)
            .where(
                HiringRequestModel.id == request_id,
                HiringRequestModel.organization_id == organization_id,
            )
            .with_for_update()
        )
        if row is None:
            raise ResourceNotFoundError("hiring request", request_id)
        return row

    def _owner_editable(self, row: HiringRequestModel, principal: Principal, revision: int) -> None:
        if row.created_by != principal.user_id:
            raise ForbiddenError()
        if row.status not in EDITABLE_STATUSES or row.revision != revision:
            raise ConflictError("The request is not editable")

    def _validate_complete(self, details: Mapping[str, Any]) -> None:
        groups = (
            (
                cast(Mapping[str, Any], details["personal"]),
                (
                    "lastName",
                    "firstName",
                    "iin",
                    "birthDate",
                    "gender",
                    "citizenship",
                    "maritalStatus",
                    "personalPhone",
                    "personalEmail",
                    "address",
                    "identityDocumentType",
                    "identityDocumentNumber",
                ),
            ),
            (
                cast(Mapping[str, Any], details["employmentData"]),
                (
                    "department",
                    "position",
                    "employmentType",
                    "workArrangement",
                    "workplace",
                    "startDate",
                    "schedule",
                    "hiringReason",
                ),
            ),
            (
                cast(Mapping[str, Any], details["educationData"]),
                ("educationLevel", "institution", "specialization", "totalExperience"),
            ),
        )
        missing = [
            field
            for group, fields in groups
            for field in fields
            if not str(group.get(field, "")).strip()
        ]
        if missing:
            raise ValidationError(
                "Required hiring request fields are missing", details={"fields": missing}
            )
        personal = groups[0][0]
        iin = str(personal["iin"])
        if len(iin) != 12 or not iin.isdigit():
            raise ValidationError("IIN must contain exactly 12 digits", details={"field": "iin"})
        if not str(personal["personalPhone"]).replace(" ", "").startswith("+7"):
            raise ValidationError(
                "Phone must use the Kazakhstan +7 format", details={"field": "personalPhone"}
            )
        email = str(personal["personalEmail"])
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValidationError("Email address is invalid", details={"field": "personalEmail"})

    async def _audit(
        self,
        session: AsyncSession,
        actor: UUID,
        row: HiringRequestModel,
        action: str,
        before: str | None,
        after: str,
        reason: str | None = None,
    ) -> None:
        await AuditService(SqlAlchemyAuditLog(session)).record(
            actor_id=actor,
            action=action,
            entity_type="newEmployeeHiringRequest",
            entity_id=row.id,
            before_state={"status": before} if before else None,
            after_state={"status": after, "stage": row.current_stage},
            reason=reason,
            organization_id=row.organization_id,
        )

    async def _event(
        self,
        session: AsyncSession,
        name: EventName,
        row: HiringRequestModel,
        payload: Mapping[str, Any],
    ) -> None:
        await SqlAlchemyTransactionalOutbox(session).append(
            ApplicationEvent(
                name=name,
                aggregate_type="newEmployeeHiringRequest",
                aggregate_id=row.id,
                payload={
                    "requestId": str(row.id),
                    "requestNumber": row.request_number,
                    "path": f"/hiring/requests/{row.id}",
                    **payload,
                },
            )
        )
