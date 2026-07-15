"""Async SQLAlchemy repository adapters for the organization domain ports."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.domain import AuditEvent
from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.events.domain import ApplicationEvent, EventName
from app.core.events.repository import SqlAlchemyTransactionalOutbox
from app.modules.organization.domain.entities import (
    Organization,
    OrganizationPolicy,
    OrganizationRelationship,
    OrganizationRelationshipType,
    OrganizationStructureVersion,
    OrganizationUnit,
    OrganizationUnitType,
    PositionDefinition,
    StaffingSlot,
    StructureReviewRequest,
)
from app.modules.organization.domain.enums import (
    EmploymentType,
    OrganizationStatus,
    ReviewRequestStatus,
    StaffingSlotStatus,
    StructureVersionStatus,
)
from app.modules.organization.domain.errors import (
    ConcurrencyConflictError,
    VersionConflictError,
)
from app.modules.organization.domain.ports import AuditRecord, OutboxRecord
from app.modules.organization.infrastructure.models import (
    OrganizationModel,
    OrganizationPolicyModel,
    OrganizationRelationshipModel,
    OrganizationRelationshipTypeModel,
    OrganizationStructureVersionModel,
    OrganizationUnitModel,
    OrganizationUnitTypeAllowedParentModel,
    OrganizationUnitTypeModel,
    PositionDefinitionModel,
    StaffingSlotModel,
    StructureReviewRequestModel,
)


async def _optimistic_update(
    session: AsyncSession,
    model_type: Any,
    entity_id: UUID,
    expected_revision: int,
    values: dict[str, Any],
    *,
    entity_name: str,
) -> None:
    statement = (
        update(model_type)
        .where(
            model_type.id == entity_id,
            model_type.revision == expected_revision,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(statement)
    rowcount = getattr(result, "rowcount", None)
    if not isinstance(rowcount, int) or rowcount != 1:
        raise ConcurrencyConflictError(entity_name, entity_id, expected_revision)


def _organization(model: OrganizationModel) -> Organization:
    return Organization(
        id=model.id,
        code=model.code,
        legal_name=model.legal_name,
        display_name=model.display_name,
        status=OrganizationStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _version(model: OrganizationStructureVersionModel) -> OrganizationStructureVersion:
    return OrganizationStructureVersion(
        id=model.id,
        organization_id=model.organization_id,
        version_number=model.version_number,
        name=model.name,
        status=StructureVersionStatus(model.status),
        based_on_version_id=model.based_on_version_id,
        effective_from=model.effective_from,
        effective_to=model.effective_to,
        revision=model.revision,
        created_by=model.created_by,
        published_by=model.published_by,
        created_at=model.created_at,
        published_at=model.published_at,
    )


def _relationship_type(
    model: OrganizationRelationshipTypeModel,
) -> OrganizationRelationshipType:
    return OrganizationRelationshipType(
        id=model.id,
        organization_id=model.organization_id,
        code=model.code,
        name=model.name,
        description=model.description,
        directed=model.directed,
        prevents_cycles=model.prevents_cycles,
        allow_self_link=model.allow_self_link,
        active=model.active,
        metadata_schema=dict(model.metadata_schema),
        revision=model.revision,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _policy(model: OrganizationPolicyModel) -> OrganizationPolicy:
    return OrganizationPolicy(
        id=model.id,
        organization_id=model.organization_id,
        structure_version_id=model.structure_version_id,
        effective_from=model.effective_from,
        effective_to=model.effective_to,
        managers_can_create_employee_drafts=model.managers_can_create_employee_drafts,
        managers_can_assign_existing_employees=model.managers_can_assign_existing_employees,
        manager_changes_require_hr_approval=model.manager_changes_require_hr_approval,
        managers_can_create_staffing_slots=model.managers_can_create_staffing_slots,
        staffing_changes_require_finance_review=model.staffing_changes_require_finance_review,
        structure_publish_requires_review=model.structure_publish_requires_review,
        allow_multiple_unit_heads=model.allow_multiple_unit_heads,
        allow_cross_unit_relationships=model.allow_cross_unit_relationships,
        revision=model.revision,
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _review(model: StructureReviewRequestModel) -> StructureReviewRequest:
    return StructureReviewRequest(
        id=model.id,
        organization_id=model.organization_id,
        structure_version_id=model.structure_version_id,
        status=ReviewRequestStatus(model.status),
        submitted_by=model.submitted_by,
        submitted_at=model.submitted_at,
        resolved_by=model.resolved_by,
        resolved_at=model.resolved_at,
        submission_reason=model.submission_reason,
        resolution_reason=model.resolution_reason,
        revision=model.revision,
    )


def _unit(model: OrganizationUnitModel) -> OrganizationUnit:
    return OrganizationUnit(
        id=model.id,
        structure_version_id=model.structure_version_id,
        stable_key=model.stable_key,
        code=model.code,
        name=model.name,
        short_name=model.short_name,
        unit_type_id=model.unit_type_id,
        parent_unit_id=model.parent_unit_id,
        sort_order=model.sort_order,
        description=model.description,
        active=model.active,
        custom_fields=dict(model.custom_fields),
        revision=model.revision,
    )


def _relationship(model: OrganizationRelationshipModel) -> OrganizationRelationship:
    return OrganizationRelationship(
        id=model.id,
        structure_version_id=model.structure_version_id,
        relationship_type_id=model.relationship_type_id,
        source_unit_id=model.source_unit_id,
        target_unit_id=model.target_unit_id,
        effective_from=model.effective_from,
        effective_to=model.effective_to,
        metadata=dict(model.metadata_payload),
        active=model.active,
        revision=model.revision,
    )


def _position(model: PositionDefinitionModel) -> PositionDefinition:
    return PositionDefinition(
        id=model.id,
        organization_id=model.organization_id,
        code=model.code,
        name=model.name,
        description=model.description,
        job_family=model.job_family,
        grade=model.grade,
        active=model.active,
        custom_fields=dict(model.custom_fields),
        revision=model.revision,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _slot(model: StaffingSlotModel) -> StaffingSlot:
    return StaffingSlot(
        id=model.id,
        structure_version_id=model.structure_version_id,
        stable_key=model.stable_key,
        organization_unit_id=model.organization_unit_id,
        position_definition_id=model.position_definition_id,
        reports_to_slot_id=model.reports_to_slot_id,
        head_of_unit=model.head_of_unit,
        full_time_equivalent=model.full_time_equivalent,
        employment_type=EmploymentType(model.employment_type),
        status=StaffingSlotStatus(model.status),
        effective_from=model.effective_from,
        effective_to=model.effective_to,
        custom_fields=dict(model.custom_fields),
        revision=model.revision,
    )


class SqlAlchemyOrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID) -> Organization | None:
        model = await self._session.get(OrganizationModel, organization_id)
        return _organization(model) if model is not None else None

    async def list(self) -> Sequence[Organization]:
        models = (
            await self._session.scalars(
                select(OrganizationModel).order_by(OrganizationModel.display_name)
            )
        ).all()
        return tuple(_organization(item) for item in models)

    async def add(self, organization: Organization) -> None:
        self._session.add(
            OrganizationModel(
                id=organization.id,
                code=organization.code,
                legal_name=organization.legal_name,
                display_name=organization.display_name,
                status=organization.status.value,
                created_at=organization.created_at,
                updated_at=organization.updated_at,
            )
        )


class SqlAlchemyStructureVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, version_id: UUID) -> OrganizationStructureVersion | None:
        model = await self._session.get(OrganizationStructureVersionModel, version_id)
        return _version(model) if model is not None else None

    async def list(
        self,
        organization_id: UUID,
        *,
        status: StructureVersionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
        sort: str = "-versionNumber",
    ) -> Sequence[OrganizationStructureVersion]:
        statement = select(OrganizationStructureVersionModel).where(
            OrganizationStructureVersionModel.organization_id == organization_id
        )
        if status is not None:
            statement = statement.where(OrganizationStructureVersionModel.status == status.value)
        sort_column: Any = {
            "versionNumber": OrganizationStructureVersionModel.version_number.asc(),
            "-versionNumber": OrganizationStructureVersionModel.version_number.desc(),
            "createdAt": OrganizationStructureVersionModel.created_at.asc(),
            "-createdAt": OrganizationStructureVersionModel.created_at.desc(),
        }[sort]
        statement = (
            statement.order_by(sort_column, OrganizationStructureVersionModel.id.asc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.scalars(statement)).all()
        return tuple(_version(item) for item in models)

    async def count(
        self, organization_id: UUID, *, status: StructureVersionStatus | None = None
    ) -> int:
        statement = (
            select(func.count())
            .select_from(OrganizationStructureVersionModel)
            .where(OrganizationStructureVersionModel.organization_id == organization_id)
        )
        if status is not None:
            statement = statement.where(OrganizationStructureVersionModel.status == status.value)
        return int((await self._session.scalar(statement)) or 0)

    async def get_active(
        self, organization_id: UUID, *, on_date: date
    ) -> OrganizationStructureVersion | None:
        statement = (
            select(OrganizationStructureVersionModel)
            .where(
                OrganizationStructureVersionModel.organization_id == organization_id,
                OrganizationStructureVersionModel.status == StructureVersionStatus.PUBLISHED.value,
                OrganizationStructureVersionModel.effective_from.is_not(None),
                OrganizationStructureVersionModel.effective_from <= on_date,
                (
                    OrganizationStructureVersionModel.effective_to.is_(None)
                    | (OrganizationStructureVersionModel.effective_to >= on_date)
                ),
            )
            .order_by(
                OrganizationStructureVersionModel.effective_from.desc(),
                OrganizationStructureVersionModel.version_number.desc(),
            )
            .limit(1)
        )
        model = await self._session.scalar(statement)
        return _version(model) if model is not None else None

    async def next_version_number(self, organization_id: UUID) -> int:
        maximum = await self._session.scalar(
            select(func.max(OrganizationStructureVersionModel.version_number)).where(
                OrganizationStructureVersionModel.organization_id == organization_id
            )
        )
        return int(maximum or 0) + 1

    async def add(self, version: OrganizationStructureVersion) -> None:
        self._session.add(
            OrganizationStructureVersionModel(
                id=version.id,
                organization_id=version.organization_id,
                version_number=version.version_number,
                name=version.name,
                status=version.status.value,
                based_on_version_id=version.based_on_version_id,
                effective_from=version.effective_from,
                effective_to=version.effective_to,
                revision=version.revision,
                created_by=version.created_by,
                published_by=version.published_by,
                created_at=version.created_at,
                published_at=version.published_at,
            )
        )

    async def save(self, version: OrganizationStructureVersion, *, expected_revision: int) -> None:
        await _optimistic_update(
            self._session,
            OrganizationStructureVersionModel,
            version.id,
            expected_revision,
            {
                "name": version.name,
                "status": version.status.value,
                "based_on_version_id": version.based_on_version_id,
                "effective_from": version.effective_from,
                "effective_to": version.effective_to,
                "revision": version.revision,
                "published_by": version.published_by,
                "published_at": version.published_at,
            },
            entity_name="organizationStructureVersion",
        )


class SqlAlchemyUnitTypeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _to_domain(self, model: OrganizationUnitTypeModel) -> OrganizationUnitType:
        parent_ids = tuple(
            (
                await self._session.scalars(
                    select(OrganizationUnitTypeAllowedParentModel.parent_type_id).where(
                        OrganizationUnitTypeAllowedParentModel.unit_type_id == model.id
                    )
                )
            ).all()
        )
        return OrganizationUnitType(
            id=model.id,
            organization_id=model.organization_id,
            code=model.code,
            name=model.name,
            description=model.description,
            active=model.active,
            allowed_parent_type_ids=parent_ids,
            custom_fields_schema=dict(model.custom_fields_schema),
            revision=model.revision,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get(self, type_id: UUID) -> OrganizationUnitType | None:
        model = await self._session.get(OrganizationUnitTypeModel, type_id)
        return await self._to_domain(model) if model is not None else None

    async def list(
        self, organization_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationUnitType]:
        statement = select(OrganizationUnitTypeModel).where(
            OrganizationUnitTypeModel.organization_id == organization_id
        )
        if not include_inactive:
            statement = statement.where(OrganizationUnitTypeModel.active.is_(True))
        models = (
            await self._session.scalars(statement.order_by(OrganizationUnitTypeModel.name))
        ).all()
        return tuple([await self._to_domain(item) for item in models])

    async def add(self, unit_type: OrganizationUnitType) -> None:
        self._session.add(
            OrganizationUnitTypeModel(
                id=unit_type.id,
                organization_id=unit_type.organization_id,
                code=unit_type.code,
                name=unit_type.name,
                description=unit_type.description,
                active=unit_type.active,
                custom_fields_schema=dict(unit_type.custom_fields_schema),
                revision=unit_type.revision,
                created_at=unit_type.created_at,
                updated_at=unit_type.updated_at,
            )
        )
        for parent_type_id in unit_type.allowed_parent_type_ids:
            self._session.add(
                OrganizationUnitTypeAllowedParentModel(
                    unit_type_id=unit_type.id, parent_type_id=parent_type_id
                )
            )

    async def save(self, unit_type: OrganizationUnitType, *, expected_revision: int) -> None:
        await _optimistic_update(
            self._session,
            OrganizationUnitTypeModel,
            unit_type.id,
            expected_revision,
            {
                "code": unit_type.code,
                "name": unit_type.name,
                "description": unit_type.description,
                "active": unit_type.active,
                "custom_fields_schema": dict(unit_type.custom_fields_schema),
                "revision": unit_type.revision,
                "updated_at": unit_type.updated_at,
            },
            entity_name="organizationUnitType",
        )
        await self._session.execute(
            delete(OrganizationUnitTypeAllowedParentModel).where(
                OrganizationUnitTypeAllowedParentModel.unit_type_id == unit_type.id
            )
        )
        self._session.add_all(
            [
                OrganizationUnitTypeAllowedParentModel(
                    unit_type_id=unit_type.id, parent_type_id=parent_type_id
                )
                for parent_type_id in unit_type.allowed_parent_type_ids
            ]
        )


class SqlAlchemyRelationshipTypeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, type_id: UUID) -> OrganizationRelationshipType | None:
        model = await self._session.get(OrganizationRelationshipTypeModel, type_id)
        return _relationship_type(model) if model is not None else None

    async def list(
        self, organization_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationRelationshipType]:
        statement = select(OrganizationRelationshipTypeModel).where(
            OrganizationRelationshipTypeModel.organization_id == organization_id
        )
        if not include_inactive:
            statement = statement.where(OrganizationRelationshipTypeModel.active.is_(True))
        models = (
            await self._session.scalars(statement.order_by(OrganizationRelationshipTypeModel.name))
        ).all()
        return tuple(_relationship_type(item) for item in models)

    async def add(self, relationship_type: OrganizationRelationshipType) -> None:
        self._session.add(
            OrganizationRelationshipTypeModel(
                id=relationship_type.id,
                organization_id=relationship_type.organization_id,
                code=relationship_type.code,
                name=relationship_type.name,
                description=relationship_type.description,
                directed=relationship_type.directed,
                prevents_cycles=relationship_type.prevents_cycles,
                allow_self_link=relationship_type.allow_self_link,
                active=relationship_type.active,
                metadata_schema=dict(relationship_type.metadata_schema),
                revision=relationship_type.revision,
                created_at=relationship_type.created_at,
                updated_at=relationship_type.updated_at,
            )
        )

    async def save(
        self,
        relationship_type: OrganizationRelationshipType,
        *,
        expected_revision: int,
    ) -> None:
        await _optimistic_update(
            self._session,
            OrganizationRelationshipTypeModel,
            relationship_type.id,
            expected_revision,
            {
                "code": relationship_type.code,
                "name": relationship_type.name,
                "description": relationship_type.description,
                "directed": relationship_type.directed,
                "prevents_cycles": relationship_type.prevents_cycles,
                "allow_self_link": relationship_type.allow_self_link,
                "active": relationship_type.active,
                "metadata_schema": dict(relationship_type.metadata_schema),
                "revision": relationship_type.revision,
                "updated_at": relationship_type.updated_at,
            },
            entity_name="organizationRelationshipType",
        )


class SqlAlchemyPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_version(self, version_id: UUID) -> OrganizationPolicy | None:
        model = await self._session.scalar(
            select(OrganizationPolicyModel).where(
                OrganizationPolicyModel.structure_version_id == version_id
            )
        )
        return _policy(model) if model is not None else None

    async def get_default(self, organization_id: UUID) -> OrganizationPolicy | None:
        model = await self._session.scalar(
            select(OrganizationPolicyModel)
            .where(
                OrganizationPolicyModel.organization_id == organization_id,
                OrganizationPolicyModel.structure_version_id.is_(None),
            )
            .order_by(OrganizationPolicyModel.created_at.desc())
            .limit(1)
        )
        return _policy(model) if model is not None else None

    async def add(self, policy: OrganizationPolicy) -> None:
        self._session.add(
            OrganizationPolicyModel(
                id=policy.id,
                organization_id=policy.organization_id,
                structure_version_id=policy.structure_version_id,
                effective_from=policy.effective_from,
                effective_to=policy.effective_to,
                managers_can_create_employee_drafts=policy.managers_can_create_employee_drafts,
                managers_can_assign_existing_employees=policy.managers_can_assign_existing_employees,
                manager_changes_require_hr_approval=policy.manager_changes_require_hr_approval,
                managers_can_create_staffing_slots=policy.managers_can_create_staffing_slots,
                staffing_changes_require_finance_review=policy.staffing_changes_require_finance_review,
                structure_publish_requires_review=policy.structure_publish_requires_review,
                allow_multiple_unit_heads=policy.allow_multiple_unit_heads,
                allow_cross_unit_relationships=policy.allow_cross_unit_relationships,
                revision=policy.revision,
                created_by=policy.created_by,
                created_at=policy.created_at,
                updated_at=policy.updated_at,
            )
        )

    async def save(self, policy: OrganizationPolicy, *, expected_revision: int) -> None:
        await _optimistic_update(
            self._session,
            OrganizationPolicyModel,
            policy.id,
            expected_revision,
            {
                "effective_from": policy.effective_from,
                "effective_to": policy.effective_to,
                "managers_can_create_employee_drafts": policy.managers_can_create_employee_drafts,
                "managers_can_assign_existing_employees": (
                    policy.managers_can_assign_existing_employees
                ),
                "manager_changes_require_hr_approval": policy.manager_changes_require_hr_approval,
                "managers_can_create_staffing_slots": policy.managers_can_create_staffing_slots,
                "staffing_changes_require_finance_review": (
                    policy.staffing_changes_require_finance_review
                ),
                "structure_publish_requires_review": policy.structure_publish_requires_review,
                "allow_multiple_unit_heads": policy.allow_multiple_unit_heads,
                "allow_cross_unit_relationships": policy.allow_cross_unit_relationships,
                "revision": policy.revision,
                "updated_at": policy.updated_at,
            },
            entity_name="organizationPolicy",
        )


class SqlAlchemyReviewRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, review_request_id: UUID) -> StructureReviewRequest | None:
        model = await self._session.get(StructureReviewRequestModel, review_request_id)
        return _review(model) if model is not None else None

    async def get_pending_for_version(self, version_id: UUID) -> StructureReviewRequest | None:
        model = await self._session.scalar(
            select(StructureReviewRequestModel)
            .where(
                StructureReviewRequestModel.structure_version_id == version_id,
                StructureReviewRequestModel.status == ReviewRequestStatus.PENDING.value,
            )
            .limit(1)
        )
        return _review(model) if model is not None else None

    async def list_for_version(self, version_id: UUID) -> Sequence[StructureReviewRequest]:
        models = (
            await self._session.scalars(
                select(StructureReviewRequestModel)
                .where(StructureReviewRequestModel.structure_version_id == version_id)
                .order_by(StructureReviewRequestModel.submitted_at.desc())
            )
        ).all()
        return tuple(_review(item) for item in models)

    async def add(self, review_request: StructureReviewRequest) -> None:
        self._session.add(
            StructureReviewRequestModel(
                id=review_request.id,
                organization_id=review_request.organization_id,
                structure_version_id=review_request.structure_version_id,
                status=review_request.status.value,
                submitted_by=review_request.submitted_by,
                submitted_at=review_request.submitted_at,
                resolved_by=review_request.resolved_by,
                resolved_at=review_request.resolved_at,
                submission_reason=review_request.submission_reason,
                resolution_reason=review_request.resolution_reason,
                revision=review_request.revision,
            )
        )

    async def save(self, review_request: StructureReviewRequest, *, expected_revision: int) -> None:
        await _optimistic_update(
            self._session,
            StructureReviewRequestModel,
            review_request.id,
            expected_revision,
            {
                "status": review_request.status.value,
                "resolved_by": review_request.resolved_by,
                "resolved_at": review_request.resolved_at,
                "submission_reason": review_request.submission_reason,
                "resolution_reason": review_request.resolution_reason,
                "revision": review_request.revision,
            },
            entity_name="structureReviewRequest",
        )


class SqlAlchemyUnitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, unit_id: UUID) -> OrganizationUnit | None:
        model = await self._session.get(OrganizationUnitModel, unit_id)
        return _unit(model) if model is not None else None

    async def list_by_version(
        self, version_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationUnit]:
        statement = select(OrganizationUnitModel).where(
            OrganizationUnitModel.structure_version_id == version_id
        )
        if not include_inactive:
            statement = statement.where(OrganizationUnitModel.active.is_(True))
        models = (
            await self._session.scalars(
                statement.order_by(
                    OrganizationUnitModel.parent_unit_id.nulls_first(),
                    OrganizationUnitModel.sort_order,
                    OrganizationUnitModel.code,
                )
            )
        ).all()
        return tuple(_unit(item) for item in models)

    async def add(self, unit: OrganizationUnit) -> None:
        self._session.add(
            OrganizationUnitModel(
                id=unit.id,
                structure_version_id=unit.structure_version_id,
                stable_key=unit.stable_key,
                code=unit.code,
                name=unit.name,
                short_name=unit.short_name,
                unit_type_id=unit.unit_type_id,
                parent_unit_id=unit.parent_unit_id,
                sort_order=unit.sort_order,
                description=unit.description,
                active=unit.active,
                custom_fields=dict(unit.custom_fields),
                revision=unit.revision,
            )
        )

    async def save(self, unit: OrganizationUnit, *, expected_revision: int) -> None:
        await _optimistic_update(
            self._session,
            OrganizationUnitModel,
            unit.id,
            expected_revision,
            {
                "code": unit.code,
                "name": unit.name,
                "short_name": unit.short_name,
                "unit_type_id": unit.unit_type_id,
                "parent_unit_id": unit.parent_unit_id,
                "sort_order": unit.sort_order,
                "description": unit.description,
                "active": unit.active,
                "custom_fields": dict(unit.custom_fields),
                "revision": unit.revision,
            },
            entity_name="organizationUnit",
        )


class SqlAlchemyRelationshipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, relationship_id: UUID) -> OrganizationRelationship | None:
        model = await self._session.get(OrganizationRelationshipModel, relationship_id)
        return _relationship(model) if model is not None else None

    async def list_by_version(
        self, version_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationRelationship]:
        statement = select(OrganizationRelationshipModel).where(
            OrganizationRelationshipModel.structure_version_id == version_id
        )
        if not include_inactive:
            statement = statement.where(OrganizationRelationshipModel.active.is_(True))
        models = (
            await self._session.scalars(
                statement.order_by(
                    OrganizationRelationshipModel.relationship_type_id,
                    OrganizationRelationshipModel.source_unit_id,
                    OrganizationRelationshipModel.target_unit_id,
                )
            )
        ).all()
        return tuple(_relationship(item) for item in models)

    async def add(self, relationship: OrganizationRelationship) -> None:
        self._session.add(
            OrganizationRelationshipModel(
                id=relationship.id,
                structure_version_id=relationship.structure_version_id,
                relationship_type_id=relationship.relationship_type_id,
                source_unit_id=relationship.source_unit_id,
                target_unit_id=relationship.target_unit_id,
                effective_from=relationship.effective_from,
                effective_to=relationship.effective_to,
                metadata_payload=dict(relationship.metadata),
                active=relationship.active,
                revision=relationship.revision,
            )
        )

    async def save(self, relationship: OrganizationRelationship, *, expected_revision: int) -> None:
        await _optimistic_update(
            self._session,
            OrganizationRelationshipModel,
            relationship.id,
            expected_revision,
            {
                "relationship_type_id": relationship.relationship_type_id,
                "source_unit_id": relationship.source_unit_id,
                "target_unit_id": relationship.target_unit_id,
                "effective_from": relationship.effective_from,
                "effective_to": relationship.effective_to,
                "metadata_payload": dict(relationship.metadata),
                "active": relationship.active,
                "revision": relationship.revision,
            },
            entity_name="organizationRelationship",
        )


class SqlAlchemyPositionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, position_id: UUID) -> PositionDefinition | None:
        model = await self._session.get(PositionDefinitionModel, position_id)
        return _position(model) if model is not None else None

    async def list(
        self,
        organization_id: UUID,
        *,
        include_inactive: bool = False,
        offset: int = 0,
        limit: int = 100,
        sort: str = "name",
    ) -> Sequence[PositionDefinition]:
        statement = select(PositionDefinitionModel).where(
            PositionDefinitionModel.organization_id == organization_id
        )
        if not include_inactive:
            statement = statement.where(PositionDefinitionModel.active.is_(True))
        sort_column: Any = {
            "code": PositionDefinitionModel.code.asc(),
            "-code": PositionDefinitionModel.code.desc(),
            "name": PositionDefinitionModel.name.asc(),
            "-name": PositionDefinitionModel.name.desc(),
            "createdAt": PositionDefinitionModel.created_at.asc(),
            "-createdAt": PositionDefinitionModel.created_at.desc(),
        }[sort]
        models = (
            await self._session.scalars(
                statement.order_by(sort_column, PositionDefinitionModel.id.asc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return tuple(_position(item) for item in models)

    async def count(self, organization_id: UUID, *, include_inactive: bool = False) -> int:
        statement = (
            select(func.count())
            .select_from(PositionDefinitionModel)
            .where(PositionDefinitionModel.organization_id == organization_id)
        )
        if not include_inactive:
            statement = statement.where(PositionDefinitionModel.active.is_(True))
        return int((await self._session.scalar(statement)) or 0)

    async def add(self, position: PositionDefinition) -> None:
        self._session.add(
            PositionDefinitionModel(
                id=position.id,
                organization_id=position.organization_id,
                code=position.code,
                name=position.name,
                description=position.description,
                job_family=position.job_family,
                grade=position.grade,
                active=position.active,
                custom_fields=dict(position.custom_fields),
                revision=position.revision,
                created_at=position.created_at,
                updated_at=position.updated_at,
            )
        )

    async def save(self, position: PositionDefinition, *, expected_revision: int) -> None:
        await _optimistic_update(
            self._session,
            PositionDefinitionModel,
            position.id,
            expected_revision,
            {
                "code": position.code,
                "name": position.name,
                "description": position.description,
                "job_family": position.job_family,
                "grade": position.grade,
                "active": position.active,
                "custom_fields": dict(position.custom_fields),
                "revision": position.revision,
                "updated_at": position.updated_at,
            },
            entity_name="positionDefinition",
        )


class SqlAlchemyStaffingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, slot_id: UUID) -> StaffingSlot | None:
        model = await self._session.get(StaffingSlotModel, slot_id)
        return _slot(model) if model is not None else None

    def _filters(
        self,
        organization_id: UUID,
        *,
        version_id: UUID | None,
        unit_id: UUID | None,
        status: StaffingSlotStatus | None,
    ) -> list[Any]:
        filters: list[Any] = [OrganizationStructureVersionModel.organization_id == organization_id]
        if version_id is not None:
            filters.append(StaffingSlotModel.structure_version_id == version_id)
        if unit_id is not None:
            filters.append(StaffingSlotModel.organization_unit_id == unit_id)
        if status is not None:
            if status is StaffingSlotStatus.CLOSED:
                filters.append(
                    or_(
                        StaffingSlotModel.status == StaffingSlotStatus.CLOSED.value,
                        and_(
                            StaffingSlotModel.status == StaffingSlotStatus.CLOSING.value,
                            StaffingSlotModel.effective_to <= date.today(),
                        ),
                    )
                )
            elif status is StaffingSlotStatus.CLOSING:
                filters.append(
                    and_(
                        StaffingSlotModel.status == StaffingSlotStatus.CLOSING.value,
                        StaffingSlotModel.effective_to > date.today(),
                    )
                )
            else:
                filters.append(StaffingSlotModel.status == status.value)
        return filters

    async def list(
        self,
        organization_id: UUID,
        *,
        version_id: UUID | None = None,
        unit_id: UUID | None = None,
        status: StaffingSlotStatus | None = None,
        offset: int = 0,
        limit: int = 100,
        sort: str = "organizationUnitId",
    ) -> Sequence[StaffingSlot]:
        sort_column: Any = {
            "organizationUnitId": StaffingSlotModel.organization_unit_id.asc(),
            "-organizationUnitId": StaffingSlotModel.organization_unit_id.desc(),
            "status": StaffingSlotModel.status.asc(),
            "-status": StaffingSlotModel.status.desc(),
            "fullTimeEquivalent": StaffingSlotModel.full_time_equivalent.asc(),
            "-fullTimeEquivalent": StaffingSlotModel.full_time_equivalent.desc(),
        }[sort]
        statement = (
            select(StaffingSlotModel)
            .join(
                OrganizationStructureVersionModel,
                OrganizationStructureVersionModel.id == StaffingSlotModel.structure_version_id,
            )
            .where(
                *self._filters(
                    organization_id,
                    version_id=version_id,
                    unit_id=unit_id,
                    status=status,
                )
            )
            .order_by(sort_column, StaffingSlotModel.id.asc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.scalars(statement)).all()
        return tuple(_slot(item) for item in models)

    async def count(
        self,
        organization_id: UUID,
        *,
        version_id: UUID | None = None,
        unit_id: UUID | None = None,
        status: StaffingSlotStatus | None = None,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(StaffingSlotModel)
            .join(
                OrganizationStructureVersionModel,
                OrganizationStructureVersionModel.id == StaffingSlotModel.structure_version_id,
            )
            .where(
                *self._filters(
                    organization_id,
                    version_id=version_id,
                    unit_id=unit_id,
                    status=status,
                )
            )
        )
        return int((await self._session.scalar(statement)) or 0)

    async def list_by_version(self, version_id: UUID) -> Sequence[StaffingSlot]:
        models = (
            await self._session.scalars(
                select(StaffingSlotModel)
                .where(StaffingSlotModel.structure_version_id == version_id)
                .order_by(
                    StaffingSlotModel.organization_unit_id,
                    StaffingSlotModel.position_definition_id,
                    StaffingSlotModel.id,
                )
            )
        ).all()
        return tuple(_slot(item) for item in models)

    async def add(self, slot: StaffingSlot) -> None:
        self._session.add(
            StaffingSlotModel(
                id=slot.id,
                structure_version_id=slot.structure_version_id,
                stable_key=slot.stable_key,
                organization_unit_id=slot.organization_unit_id,
                position_definition_id=slot.position_definition_id,
                reports_to_slot_id=slot.reports_to_slot_id,
                head_of_unit=slot.head_of_unit,
                full_time_equivalent=slot.full_time_equivalent,
                employment_type=slot.employment_type.value,
                status=slot.status.value,
                effective_from=slot.effective_from,
                effective_to=slot.effective_to,
                revision=slot.revision,
                custom_fields=dict(slot.custom_fields),
            )
        )

    async def save(self, slot: StaffingSlot, *, expected_revision: int) -> None:
        await _optimistic_update(
            self._session,
            StaffingSlotModel,
            slot.id,
            expected_revision,
            {
                "organization_unit_id": slot.organization_unit_id,
                "position_definition_id": slot.position_definition_id,
                "reports_to_slot_id": slot.reports_to_slot_id,
                "head_of_unit": slot.head_of_unit,
                "full_time_equivalent": slot.full_time_equivalent,
                "employment_type": slot.employment_type.value,
                "status": slot.status.value,
                "effective_from": slot.effective_from,
                "effective_to": slot.effective_to,
                "revision": slot.revision,
                "custom_fields": dict(slot.custom_fields),
            },
            entity_name="staffingSlot",
        )


class SqlAlchemyAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._audit = SqlAlchemyAuditLog(session)

    async def add(self, record: AuditRecord) -> None:
        try:
            await self._audit.append(
                AuditEvent(
                    id=record.id,
                    organization_id=record.organization_id,
                    actor_id=record.actor_id,
                    action=record.action,
                    entity_type=record.entity_type,
                    entity_id=record.entity_id,
                    before_state=record.before,
                    after_state=record.after,
                    reason=record.reason,
                    request_id=record.request_id,
                    occurred_at=record.occurred_at,
                )
            )
        except IntegrityError as exc:
            raise VersionConflictError(
                "The requested organization change conflicts with persisted data."
            ) from exc


class SqlAlchemyOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._outbox = SqlAlchemyTransactionalOutbox(session)

    async def add(self, record: OutboxRecord) -> None:
        payload = {
            "organizationId": str(record.organization_id),
            **dict(record.payload),
        }
        try:
            await self._outbox.append(
                ApplicationEvent(
                    id=record.id,
                    name=EventName(record.event_type),
                    aggregate_type=record.aggregate_type,
                    aggregate_id=record.aggregate_id,
                    payload=payload,
                    occurred_at=record.occurred_at,
                )
            )
        except IntegrityError as exc:
            raise VersionConflictError(
                "The requested organization change conflicts with persisted data."
            ) from exc
