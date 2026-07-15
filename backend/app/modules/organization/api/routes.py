"""Thin FastAPI routes for organization application use cases."""

from collections.abc import Callable
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from app.core.logging.context import get_request_id
from app.modules.organization.api.dependencies import (
    get_organization_actor,
    get_organization_service,
)
from app.modules.organization.api.schemas import (
    AddRelationshipRequest,
    AddUnitRequest,
    CloseStaffingSlotRequest,
    CreateDraftRequest,
    CreatePositionRequest,
    CreateRelationshipTypeRequest,
    CreateStaffingSlotRequest,
    CreateUnitTypeRequest,
    DeactivateUnitRequest,
    MoveUnitRequest,
    OrganizationPolicyResponse,
    OrganizationRelationshipResponse,
    OrganizationResponse,
    OrganizationUnitResponse,
    PositionDefinitionResponse,
    PublishStructureRequest,
    RelationshipTypeResponse,
    RemoveRelationshipRequest,
    ReorderUnitsRequest,
    ReturnForCorrectionRequest,
    ReviewRequestResponse,
    RevisionReasonRequest,
    StaffingSlotResponse,
    StructureVersionResponse,
    StructureViewResponse,
    UnitTypeResponse,
    UpdatePolicyRequest,
    UpdatePositionRequest,
    UpdateRelationshipRequest,
    UpdateRelationshipTypeRequest,
    UpdateStaffingSlotRequest,
    UpdateUnitRequest,
    UpdateUnitTypeRequest,
    ValidationResponse,
    VersionComparisonResponse,
)
from app.modules.organization.application.commands import (
    AddRelationshipCommand,
    AddUnitCommand,
    CloseStaffingSlotCommand,
    CreateDraftCommand,
    CreatePositionCommand,
    CreateRelationshipTypeCommand,
    CreateStaffingSlotCommand,
    CreateUnitTypeCommand,
    DeactivateUnitCommand,
    MoveUnitCommand,
    PublishStructureCommand,
    RemoveRelationshipCommand,
    ReorderUnitItem,
    ReorderUnitsCommand,
    ReturnForCorrectionCommand,
    SubmitReviewCommand,
    UpdatePolicyCommand,
    UpdatePositionCommand,
    UpdateRelationshipCommand,
    UpdateRelationshipTypeCommand,
    UpdateStaffingSlotCommand,
    UpdateUnitCommand,
    UpdateUnitTypeCommand,
)
from app.modules.organization.application.service import OrganizationService
from app.modules.organization.domain.enums import StaffingSlotStatus, StructureVersionStatus
from app.modules.organization.domain.errors import OrganizationError
from app.modules.organization.domain.ports import Actor
from app.shared.api.schemas import DataResponse, ListResponse, PageMeta

ServiceProvider = Callable[..., OrganizationService]
ActorProvider = Callable[..., Actor]
StructureVersionSort = Literal["versionNumber", "-versionNumber", "createdAt", "-createdAt"]
PositionSort = Literal["code", "-code", "name", "-name", "createdAt", "-createdAt"]
StaffingSlotSort = Literal[
    "organizationUnitId",
    "-organizationUnitId",
    "status",
    "-status",
    "fullTimeEquivalent",
    "-fullTimeEquivalent",
]


async def organization_exception_handler(
    request: Request, exception: OrganizationError
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=exception.status_code,
        content={
            "error": {
                "code": exception.code,
                "message": exception.message,
                "details": exception.details,
                "requestId": get_request_id(),
            }
        },
    )


def _organization_id(actor: Actor, supplied: UUID | None) -> UUID:
    organization_id = supplied or actor.organization_id
    if organization_id is None:
        raise OrganizationError(
            "VALIDATION_FAILED",
            (
                "organizationId is required when the authenticated account "
                "has no default organization."
            ),
            details={"field": "organizationId"},
        )
    return organization_id


def create_organization_router(
    service_provider: ServiceProvider,
    actor_provider: ActorProvider,
) -> APIRouter:
    """Create a router from explicit service/actor dependencies for easy testing."""

    api = APIRouter(tags=["organization"])
    Service = Annotated[OrganizationService, Depends(service_provider)]
    CurrentActor = Annotated[Actor, Depends(actor_provider)]

    @api.get("/organization", response_model=DataResponse[OrganizationResponse])
    async def get_organization(
        service: Service,
        actor: CurrentActor,
        organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
    ) -> DataResponse[OrganizationResponse]:
        item = await service.get_organization(_organization_id(actor, organization_id), actor)
        return DataResponse(data=OrganizationResponse.model_validate(item))

    @api.get(
        "/organization/structure/active",
        response_model=DataResponse[StructureViewResponse],
    )
    async def get_active_structure(
        service: Service,
        actor: CurrentActor,
        organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
        effective_on: Annotated[date | None, Query(alias="effectiveOn")] = None,
    ) -> DataResponse[StructureViewResponse]:
        view = await service.read_active_structure(
            _organization_id(actor, organization_id), actor, on_date=effective_on
        )
        return DataResponse(data=StructureViewResponse.from_view(view))

    @api.get(
        "/organization/structure/versions",
        response_model=ListResponse[StructureVersionResponse],
    )
    async def list_versions(
        service: Service,
        actor: CurrentActor,
        organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
        version_status: Annotated[StructureVersionStatus | None, Query(alias="status")] = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
        sort: Annotated[StructureVersionSort, Query()] = "-versionNumber",
    ) -> ListResponse[StructureVersionResponse]:
        items, total = await service.list_versions(
            _organization_id(actor, organization_id),
            actor,
            status=version_status,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        return ListResponse(
            data=[StructureVersionResponse.model_validate(item) for item in items],
            meta=PageMeta(page=page, page_size=page_size, total=total),
        )

    @api.get(
        "/organization/structure/versions/{version_id}",
        response_model=DataResponse[StructureViewResponse],
    )
    async def get_structure_version(
        version_id: UUID, service: Service, actor: CurrentActor
    ) -> DataResponse[StructureViewResponse]:
        view = await service.read_structure_version(version_id, actor)
        return DataResponse(data=StructureViewResponse.from_view(view))

    @api.get(
        "/organization/structure/versions/{from_version_id}/compare/{to_version_id}",
        response_model=DataResponse[VersionComparisonResponse],
    )
    async def compare_versions(
        from_version_id: UUID,
        to_version_id: UUID,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[VersionComparisonResponse]:
        comparison = await service.compare_versions(from_version_id, to_version_id, actor)
        return DataResponse(data=VersionComparisonResponse.from_comparison(comparison))

    @api.post(
        "/organization/structure/drafts",
        response_model=DataResponse[StructureVersionResponse],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_draft(
        payload: CreateDraftRequest, service: Service, actor: CurrentActor
    ) -> DataResponse[StructureVersionResponse]:
        item = await service.create_draft(
            CreateDraftCommand(
                organization_id=payload.organization_id,
                name=payload.name,
                based_on_version_id=payload.based_on_version_id,
            ),
            actor,
        )
        return DataResponse(data=StructureVersionResponse.model_validate(item))

    @api.post(
        "/organization/structure/drafts/{version_id}/validate",
        response_model=DataResponse[ValidationResponse],
    )
    async def validate_draft(
        version_id: UUID, service: Service, actor: CurrentActor
    ) -> DataResponse[ValidationResponse]:
        outcome = await service.validate_draft(version_id, actor)
        return DataResponse(data=ValidationResponse.from_outcome(outcome))

    @api.post(
        "/organization/structure/drafts/{version_id}/submit-review",
        response_model=DataResponse[ReviewRequestResponse],
    )
    async def submit_review(
        version_id: UUID,
        payload: RevisionReasonRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[ReviewRequestResponse]:
        item = await service.submit_for_review(
            SubmitReviewCommand(
                version_id=version_id,
                revision=payload.revision,
                reason=payload.reason,
            ),
            actor,
        )
        return DataResponse(data=ReviewRequestResponse.model_validate(item))

    @api.post(
        "/organization/structure/drafts/{version_id}/return",
        response_model=DataResponse[StructureVersionResponse],
    )
    async def return_for_correction(
        version_id: UUID,
        payload: ReturnForCorrectionRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[StructureVersionResponse]:
        item = await service.return_for_correction(
            ReturnForCorrectionCommand(
                version_id=version_id,
                revision=payload.revision,
                review_revision=payload.review_revision,
                reason=payload.reason,
            ),
            actor,
        )
        return DataResponse(data=StructureVersionResponse.model_validate(item))

    @api.post(
        "/organization/structure/drafts/{version_id}/publish",
        response_model=DataResponse[StructureVersionResponse],
    )
    async def publish_structure(
        version_id: UUID,
        payload: PublishStructureRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[StructureVersionResponse]:
        item = await service.publish_structure(
            PublishStructureCommand(
                version_id=version_id,
                revision=payload.revision,
                effective_from=payload.effective_from,
                reason=payload.reason,
                review_revision=payload.review_revision,
            ),
            actor,
        )
        return DataResponse(data=StructureVersionResponse.model_validate(item))

    @api.get(
        "/organization/structure/{version_id}/reviews",
        response_model=ListResponse[ReviewRequestResponse],
    )
    async def list_reviews(
        version_id: UUID, service: Service, actor: CurrentActor
    ) -> ListResponse[ReviewRequestResponse]:
        items = await service.list_review_requests(version_id, actor)
        return ListResponse(
            data=[ReviewRequestResponse.model_validate(item) for item in items],
            meta=PageMeta(page=1, page_size=max(1, len(items)), total=len(items)),
        )

    @api.post(
        "/organization/structure/{version_id}/units",
        response_model=DataResponse[OrganizationUnitResponse],
        status_code=status.HTTP_201_CREATED,
    )
    async def add_unit(
        version_id: UUID,
        payload: AddUnitRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[OrganizationUnitResponse]:
        item = await service.add_unit(
            AddUnitCommand(
                version_id=version_id,
                version_revision=payload.version_revision,
                code=payload.code,
                name=payload.name,
                short_name=payload.short_name,
                unit_type_id=payload.unit_type_id,
                parent_unit_id=payload.parent_unit_id,
                sort_order=payload.sort_order,
                description=payload.description,
                custom_fields=payload.custom_fields,
            ),
            actor,
        )
        return DataResponse(data=OrganizationUnitResponse.model_validate(item))

    @api.patch(
        "/organization/structure/{version_id}/units/{unit_id}",
        response_model=DataResponse[OrganizationUnitResponse],
    )
    async def update_unit(
        version_id: UUID,
        unit_id: UUID,
        payload: UpdateUnitRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[OrganizationUnitResponse]:
        item = await service.update_unit(
            UpdateUnitCommand(
                version_id=version_id,
                unit_id=unit_id,
                version_revision=payload.version_revision,
                unit_revision=payload.revision,
                changes=payload.changes(),
            ),
            actor,
        )
        return DataResponse(data=OrganizationUnitResponse.model_validate(item))

    @api.post(
        "/organization/structure/{version_id}/units/{unit_id}/move",
        response_model=DataResponse[OrganizationUnitResponse],
    )
    async def move_unit(
        version_id: UUID,
        unit_id: UUID,
        payload: MoveUnitRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[OrganizationUnitResponse]:
        item = await service.move_unit(
            MoveUnitCommand(
                version_id=version_id,
                unit_id=unit_id,
                version_revision=payload.version_revision,
                unit_revision=payload.revision,
                parent_unit_id=payload.parent_unit_id,
                sort_order=payload.sort_order,
            ),
            actor,
        )
        return DataResponse(data=OrganizationUnitResponse.model_validate(item))

    @api.post(
        "/organization/structure/{version_id}/units/reorder",
        response_model=DataResponse[list[OrganizationUnitResponse]],
    )
    async def reorder_units(
        version_id: UUID,
        payload: ReorderUnitsRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[list[OrganizationUnitResponse]]:
        items = await service.reorder_units(
            ReorderUnitsCommand(
                version_id=version_id,
                version_revision=payload.version_revision,
                parent_unit_id=payload.parent_unit_id,
                items=tuple(
                    ReorderUnitItem(
                        unit_id=item.unit_id,
                        revision=item.revision,
                        sort_order=item.sort_order,
                    )
                    for item in payload.items
                ),
            ),
            actor,
        )
        return DataResponse(data=[OrganizationUnitResponse.model_validate(item) for item in items])

    @api.delete(
        "/organization/structure/{version_id}/units/{unit_id}",
        response_model=DataResponse[OrganizationUnitResponse],
    )
    async def deactivate_unit(
        version_id: UUID,
        unit_id: UUID,
        payload: DeactivateUnitRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[OrganizationUnitResponse]:
        item = await service.deactivate_unit(
            DeactivateUnitCommand(
                version_id=version_id,
                unit_id=unit_id,
                version_revision=payload.version_revision,
                unit_revision=payload.revision,
                reason=payload.reason,
            ),
            actor,
        )
        return DataResponse(data=OrganizationUnitResponse.model_validate(item))

    @api.get(
        "/organization/structure/{version_id}/relationships",
        response_model=ListResponse[OrganizationRelationshipResponse],
    )
    async def list_relationships(
        version_id: UUID,
        service: Service,
        actor: CurrentActor,
        include_inactive: Annotated[bool, Query(alias="includeInactive")] = False,
    ) -> ListResponse[OrganizationRelationshipResponse]:
        items = await service.list_relationships(
            version_id, actor, include_inactive=include_inactive
        )
        return ListResponse(
            data=[OrganizationRelationshipResponse.model_validate(item) for item in items],
            meta=PageMeta(page=1, page_size=max(1, len(items)), total=len(items)),
        )

    @api.post(
        "/organization/structure/{version_id}/relationships",
        response_model=DataResponse[OrganizationRelationshipResponse],
        status_code=status.HTTP_201_CREATED,
    )
    async def add_relationship(
        version_id: UUID,
        payload: AddRelationshipRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[OrganizationRelationshipResponse]:
        item = await service.add_relationship(
            AddRelationshipCommand(
                version_id=version_id,
                version_revision=payload.version_revision,
                relationship_type_id=payload.relationship_type_id,
                source_unit_id=payload.source_unit_id,
                target_unit_id=payload.target_unit_id,
                effective_from=payload.effective_from,
                effective_to=payload.effective_to,
                metadata=payload.metadata,
            ),
            actor,
        )
        return DataResponse(data=OrganizationRelationshipResponse.model_validate(item))

    @api.patch(
        "/organization/structure/{version_id}/relationships/{relationship_id}",
        response_model=DataResponse[OrganizationRelationshipResponse],
    )
    async def update_relationship(
        version_id: UUID,
        relationship_id: UUID,
        payload: UpdateRelationshipRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[OrganizationRelationshipResponse]:
        item = await service.update_relationship(
            UpdateRelationshipCommand(
                version_id=version_id,
                relationship_id=relationship_id,
                version_revision=payload.version_revision,
                relationship_revision=payload.revision,
                changes=payload.changes(),
            ),
            actor,
        )
        return DataResponse(data=OrganizationRelationshipResponse.model_validate(item))

    @api.delete(
        "/organization/structure/{version_id}/relationships/{relationship_id}",
        response_model=DataResponse[OrganizationRelationshipResponse],
    )
    async def remove_relationship(
        version_id: UUID,
        relationship_id: UUID,
        payload: RemoveRelationshipRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[OrganizationRelationshipResponse]:
        item = await service.remove_relationship(
            RemoveRelationshipCommand(
                version_id=version_id,
                relationship_id=relationship_id,
                version_revision=payload.version_revision,
                relationship_revision=payload.revision,
                reason=payload.reason,
            ),
            actor,
        )
        return DataResponse(data=OrganizationRelationshipResponse.model_validate(item))

    @api.get("/positions", response_model=ListResponse[PositionDefinitionResponse])
    async def list_positions(
        service: Service,
        actor: CurrentActor,
        organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
        include_inactive: Annotated[bool, Query(alias="includeInactive")] = False,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
        sort: Annotated[PositionSort, Query()] = "name",
    ) -> ListResponse[PositionDefinitionResponse]:
        items, total = await service.list_positions(
            _organization_id(actor, organization_id),
            actor,
            include_inactive=include_inactive,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        return ListResponse(
            data=[PositionDefinitionResponse.model_validate(item) for item in items],
            meta=PageMeta(page=page, page_size=page_size, total=total),
        )

    @api.post(
        "/positions",
        response_model=DataResponse[PositionDefinitionResponse],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_position(
        payload: CreatePositionRequest, service: Service, actor: CurrentActor
    ) -> DataResponse[PositionDefinitionResponse]:
        item = await service.create_position(
            CreatePositionCommand(
                organization_id=payload.organization_id,
                code=payload.code,
                name=payload.name,
                description=payload.description,
                job_family=payload.job_family,
                grade=payload.grade,
                custom_fields=payload.custom_fields,
            ),
            actor,
        )
        return DataResponse(data=PositionDefinitionResponse.model_validate(item))

    @api.patch(
        "/positions/{position_id}",
        response_model=DataResponse[PositionDefinitionResponse],
    )
    async def update_position(
        position_id: UUID,
        payload: UpdatePositionRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[PositionDefinitionResponse]:
        item = await service.update_position(
            UpdatePositionCommand(
                position_id=position_id,
                revision=payload.revision,
                changes=payload.changes(),
            ),
            actor,
        )
        return DataResponse(data=PositionDefinitionResponse.model_validate(item))

    @api.get("/staffing-slots", response_model=ListResponse[StaffingSlotResponse])
    async def list_staffing_slots(
        service: Service,
        actor: CurrentActor,
        organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
        version_id: Annotated[UUID | None, Query(alias="versionId")] = None,
        unit_id: Annotated[UUID | None, Query(alias="unitId")] = None,
        slot_status: Annotated[StaffingSlotStatus | None, Query(alias="status")] = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
        sort: Annotated[StaffingSlotSort, Query()] = "organizationUnitId",
    ) -> ListResponse[StaffingSlotResponse]:
        items, total = await service.list_staffing_slots(
            _organization_id(actor, organization_id),
            actor,
            version_id=version_id,
            unit_id=unit_id,
            status=slot_status,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        return ListResponse(
            data=[StaffingSlotResponse.from_domain(item) for item in items],
            meta=PageMeta(page=page, page_size=page_size, total=total),
        )

    @api.post(
        "/staffing-slots",
        response_model=DataResponse[StaffingSlotResponse],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_staffing_slot(
        payload: CreateStaffingSlotRequest, service: Service, actor: CurrentActor
    ) -> DataResponse[StaffingSlotResponse]:
        item = await service.create_staffing_slot(
            CreateStaffingSlotCommand(
                version_id=payload.version_id,
                version_revision=payload.version_revision,
                organization_unit_id=payload.organization_unit_id,
                position_definition_id=payload.position_definition_id,
                reports_to_slot_id=payload.reports_to_slot_id,
                head_of_unit=payload.head_of_unit,
                full_time_equivalent=payload.full_time_equivalent,
                employment_type=payload.employment_type,
                status=payload.status,
                effective_from=payload.effective_from,
                effective_to=payload.effective_to,
                custom_fields=payload.custom_fields,
            ),
            actor,
        )
        return DataResponse(data=StaffingSlotResponse.from_domain(item))

    @api.patch(
        "/staffing-slots/{slot_id}",
        response_model=DataResponse[StaffingSlotResponse],
    )
    async def update_staffing_slot(
        slot_id: UUID,
        payload: UpdateStaffingSlotRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[StaffingSlotResponse]:
        item = await service.update_staffing_slot(
            UpdateStaffingSlotCommand(
                slot_id=slot_id,
                version_revision=payload.version_revision,
                slot_revision=payload.revision,
                changes=payload.changes(),
            ),
            actor,
        )
        return DataResponse(data=StaffingSlotResponse.from_domain(item))

    @api.post(
        "/staffing-slots/{slot_id}/close",
        response_model=DataResponse[StaffingSlotResponse],
    )
    async def close_staffing_slot(
        slot_id: UUID,
        payload: CloseStaffingSlotRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[StaffingSlotResponse]:
        item = await service.close_staffing_slot(
            CloseStaffingSlotCommand(
                slot_id=slot_id,
                version_revision=payload.version_revision,
                slot_revision=payload.revision,
                effective_to=payload.effective_to,
                reason=payload.reason,
            ),
            actor,
        )
        return DataResponse(data=StaffingSlotResponse.from_domain(item))

    @api.get(
        "/organization/reference/unit-types",
        response_model=ListResponse[UnitTypeResponse],
    )
    async def list_unit_types(
        service: Service,
        actor: CurrentActor,
        organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
        include_inactive: Annotated[bool, Query(alias="includeInactive")] = False,
    ) -> ListResponse[UnitTypeResponse]:
        items = await service.list_unit_types(
            _organization_id(actor, organization_id),
            actor,
            include_inactive=include_inactive,
        )
        return ListResponse(
            data=[UnitTypeResponse.model_validate(item) for item in items],
            meta=PageMeta(page=1, page_size=max(1, len(items)), total=len(items)),
        )

    @api.post(
        "/organization/reference/unit-types",
        response_model=DataResponse[UnitTypeResponse],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_unit_type(
        payload: CreateUnitTypeRequest, service: Service, actor: CurrentActor
    ) -> DataResponse[UnitTypeResponse]:
        item = await service.create_unit_type(
            CreateUnitTypeCommand(
                organization_id=payload.organization_id,
                code=payload.code,
                name=payload.name,
                description=payload.description,
                allowed_parent_type_ids=tuple(payload.allowed_parent_type_ids),
                custom_fields_schema=payload.custom_fields_schema,
            ),
            actor,
        )
        return DataResponse(data=UnitTypeResponse.model_validate(item))

    @api.patch(
        "/organization/reference/unit-types/{type_id}",
        response_model=DataResponse[UnitTypeResponse],
    )
    async def update_unit_type(
        type_id: UUID,
        payload: UpdateUnitTypeRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[UnitTypeResponse]:
        item = await service.update_unit_type(
            UpdateUnitTypeCommand(
                type_id=type_id,
                revision=payload.revision,
                changes=payload.changes(),
            ),
            actor,
        )
        return DataResponse(data=UnitTypeResponse.model_validate(item))

    @api.get(
        "/organization/reference/relationship-types",
        response_model=ListResponse[RelationshipTypeResponse],
    )
    async def list_relationship_types(
        service: Service,
        actor: CurrentActor,
        organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
        include_inactive: Annotated[bool, Query(alias="includeInactive")] = False,
    ) -> ListResponse[RelationshipTypeResponse]:
        items = await service.list_relationship_types(
            _organization_id(actor, organization_id),
            actor,
            include_inactive=include_inactive,
        )
        return ListResponse(
            data=[RelationshipTypeResponse.model_validate(item) for item in items],
            meta=PageMeta(page=1, page_size=max(1, len(items)), total=len(items)),
        )

    @api.post(
        "/organization/reference/relationship-types",
        response_model=DataResponse[RelationshipTypeResponse],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_relationship_type(
        payload: CreateRelationshipTypeRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[RelationshipTypeResponse]:
        item = await service.create_relationship_type(
            CreateRelationshipTypeCommand(
                organization_id=payload.organization_id,
                code=payload.code,
                name=payload.name,
                description=payload.description,
                directed=payload.directed,
                prevents_cycles=payload.prevents_cycles,
                allow_self_link=payload.allow_self_link,
                metadata_schema=payload.metadata_schema,
            ),
            actor,
        )
        return DataResponse(data=RelationshipTypeResponse.model_validate(item))

    @api.patch(
        "/organization/reference/relationship-types/{type_id}",
        response_model=DataResponse[RelationshipTypeResponse],
    )
    async def update_relationship_type(
        type_id: UUID,
        payload: UpdateRelationshipTypeRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[RelationshipTypeResponse]:
        item = await service.update_relationship_type(
            UpdateRelationshipTypeCommand(
                type_id=type_id,
                revision=payload.revision,
                changes=payload.changes(),
            ),
            actor,
        )
        return DataResponse(data=RelationshipTypeResponse.model_validate(item))

    @api.get(
        "/organization/structure/{version_id}/policy",
        response_model=DataResponse[OrganizationPolicyResponse],
    )
    async def get_policy(
        version_id: UUID, service: Service, actor: CurrentActor
    ) -> DataResponse[OrganizationPolicyResponse]:
        item = await service.get_policy(version_id, actor)
        return DataResponse(data=OrganizationPolicyResponse.model_validate(item))

    @api.put(
        "/organization/structure/{version_id}/policy",
        response_model=DataResponse[OrganizationPolicyResponse],
    )
    async def update_policy(
        version_id: UUID,
        payload: UpdatePolicyRequest,
        service: Service,
        actor: CurrentActor,
    ) -> DataResponse[OrganizationPolicyResponse]:
        item = await service.update_policy(
            UpdatePolicyCommand(
                version_id=version_id,
                version_revision=payload.version_revision,
                policy_revision=payload.revision,
                changes=payload.changes(),
            ),
            actor,
        )
        return DataResponse(data=OrganizationPolicyResponse.model_validate(item))

    return api


router = create_organization_router(
    get_organization_service,
    get_organization_actor,
)
