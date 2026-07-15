"""Transaction-oriented organization use cases.

All business rules live here or in the pure domain layer. The service has no
knowledge of FastAPI, SQLAlchemy, or an authentication-provider implementation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from app.modules.organization.application.authorization import DenyAllOrganizationAuthorizer
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
from app.modules.organization.application.models import (
    OrganizationStructureView,
    OrganizationTreeNode,
    ValidationOutcome,
    VersionComparison,
)
from app.modules.organization.domain.custom_fields import (
    CustomFieldValidationError,
    validate_json_object,
)
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
    non_empty_name,
    normalized_code,
    utc_now,
    validate_date_range,
)
from app.modules.organization.domain.enums import (
    EmploymentType,
    StaffingSlotStatus,
    StructureVersionStatus,
)
from app.modules.organization.domain.errors import (
    DraftValidationError,
    InvalidRelationshipError,
    MultipleRootsError,
    OrganizationError,
    ResourceNotFoundError,
    StaffingSlotNotAvailableError,
    StructureCycleError,
    VersionConflictError,
)
from app.modules.organization.domain.ports import (
    Actor,
    AuditRecord,
    ExternalStructureValidationPort,
    NullExternalStructureValidationPort,
    OrganizationAuthorizationPort,
    OrganizationUnitOfWork,
    OrganizationUnitOfWorkFactory,
    OutboxRecord,
)
from app.modules.organization.domain.validation import (
    OrganizationStructureValidator,
    StructureSnapshot,
    ValidationReport,
)

PERMISSION_ORGANIZATION_READ = "organization.read"
PERMISSION_STRUCTURE_READ = "organization.structure.read"
PERMISSION_DRAFT_CREATE = "organization.structure.draft.create"
PERMISSION_STRUCTURE_EDIT = "organization.structure.edit"
PERMISSION_STRUCTURE_REVIEW = "organization.structure.review"
PERMISSION_STRUCTURE_PUBLISH = "organization.structure.publish"
PERMISSION_UNIT_MANAGE = "organization.unit.manage"
PERMISSION_RELATIONSHIP_MANAGE = "organization.relationship.manage"
PERMISSION_STAFFING_MANAGE = "organization.staffing.manage"


class OrganizationService:
    def __init__(
        self,
        uow_factory: OrganizationUnitOfWorkFactory,
        *,
        authorizer: OrganizationAuthorizationPort | None = None,
        external_validator: ExternalStructureValidationPort | None = None,
        validator: OrganizationStructureValidator | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._authorizer = authorizer or DenyAllOrganizationAuthorizer()
        self._external_validator = external_validator or NullExternalStructureValidationPort()
        self._validator = validator or OrganizationStructureValidator()

    async def get_organization(self, organization_id: UUID, actor: Actor) -> Organization:
        await self._authorizer.require(actor, PERMISSION_ORGANIZATION_READ, organization_id)
        async with self._uow_factory() as uow:
            organization = await uow.organizations.get(organization_id)
            if organization is None:
                raise ResourceNotFoundError("organization", organization_id)
            return organization

    async def read_active_structure(
        self,
        organization_id: UUID,
        actor: Actor,
        *,
        on_date: date | None = None,
    ) -> OrganizationStructureView:
        await self._authorizer.require(actor, PERMISSION_STRUCTURE_READ, organization_id)
        async with self._uow_factory() as uow:
            version = await uow.versions.get_active(
                organization_id, on_date=on_date or date.today()
            )
            if version is None:
                raise ResourceNotFoundError("activeOrganizationStructure", organization_id)
            return await self._build_structure_view(uow, version)

    async def read_structure_version(
        self, version_id: UUID, actor: Actor
    ) -> OrganizationStructureView:
        async with self._uow_factory() as uow:
            version = await self._require_version(uow, version_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_READ, version.organization_id
            )
            return await self._build_structure_view(uow, version)

    async def list_versions(
        self,
        organization_id: UUID,
        actor: Actor,
        *,
        status: StructureVersionStatus | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "-versionNumber",
    ) -> tuple[tuple[OrganizationStructureVersion, ...], int]:
        await self._authorizer.require(actor, PERMISSION_STRUCTURE_READ, organization_id)
        offset = (page - 1) * page_size
        async with self._uow_factory() as uow:
            versions = await uow.versions.list(
                organization_id,
                status=status,
                offset=offset,
                limit=page_size,
                sort=sort,
            )
            total = await uow.versions.count(organization_id, status=status)
            return tuple(versions), total

    async def compare_versions(
        self, from_version_id: UUID, to_version_id: UUID, actor: Actor
    ) -> VersionComparison:
        async with self._uow_factory() as uow:
            from_version = await self._require_version(uow, from_version_id)
            to_version = await self._require_version(uow, to_version_id)
            if from_version.organization_id != to_version.organization_id:
                raise VersionConflictError(
                    "Structure versions from different organizations cannot be compared."
                )
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_READ, from_version.organization_id
            )
            from_units = tuple(
                await uow.units.list_by_version(from_version_id, include_inactive=True)
            )
            to_units = tuple(await uow.units.list_by_version(to_version_id, include_inactive=True))
            from_relationships = tuple(
                await uow.relationships.list_by_version(from_version_id, include_inactive=True)
            )
            to_relationships = tuple(
                await uow.relationships.list_by_version(to_version_id, include_inactive=True)
            )
            from_slots = tuple(await uow.staffing.list_by_version(from_version_id))
            to_slots = tuple(await uow.staffing.list_by_version(to_version_id))
            return self._compare(
                from_version_id,
                to_version_id,
                from_units,
                to_units,
                from_relationships,
                to_relationships,
                from_slots,
                to_slots,
            )

    async def create_draft(
        self, command: CreateDraftCommand, actor: Actor
    ) -> OrganizationStructureVersion:
        await self._authorizer.require(actor, PERMISSION_DRAFT_CREATE, command.organization_id)
        async with self._uow_factory() as uow:
            organization = await uow.organizations.get(command.organization_id)
            if organization is None:
                raise ResourceNotFoundError("organization", command.organization_id)
            base: OrganizationStructureVersion | None
            if command.based_on_version_id is not None:
                base = await self._require_version(uow, command.based_on_version_id)
                if base.organization_id != command.organization_id:
                    raise VersionConflictError("The base version belongs to another organization.")
            else:
                base = await uow.versions.get_active(command.organization_id, on_date=date.today())
            if base is not None and base.status is not StructureVersionStatus.PUBLISHED:
                raise VersionConflictError(
                    "A draft can only be cloned from a published structure version.",
                    details={"baseVersionId": str(base.id), "status": base.status.value},
                )

            version = OrganizationStructureVersion(
                id=uuid4(),
                organization_id=command.organization_id,
                version_number=await uow.versions.next_version_number(command.organization_id),
                name=command.name,
                status=StructureVersionStatus.DRAFT,
                based_on_version_id=base.id if base else None,
                created_by=actor.user_id,
            )
            await uow.versions.add(version)
            if base is not None:
                await self._clone_version_contents(uow, base, version, actor)
            else:
                policy = OrganizationPolicy(
                    id=uuid4(),
                    organization_id=command.organization_id,
                    structure_version_id=version.id,
                    created_by=actor.user_id,
                )
                await uow.policies.add(policy)
            await self._audit(
                uow,
                actor,
                command.organization_id,
                "organizationStructureDraftCreated",
                "organizationStructureVersion",
                version.id,
                before=None,
                after=version,
            )
            await uow.commit()
            return version

    async def add_unit(self, command: AddUnitCommand, actor: Actor) -> OrganizationUnit:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            await self._authorizer.require(
                actor,
                PERMISSION_UNIT_MANAGE,
                version.organization_id,
                unit_id=command.parent_unit_id,
            )
            units = tuple(await uow.units.list_by_version(version.id, include_inactive=True))
            await self._assert_new_unit_values(
                uow,
                version,
                units,
                code=command.code,
                unit_type_id=command.unit_type_id,
                parent_unit_id=command.parent_unit_id,
            )
            version_previous_revision = version.touch(command.version_revision)
            unit = OrganizationUnit(
                id=uuid4(),
                structure_version_id=version.id,
                stable_key=uuid4(),
                code=command.code,
                name=command.name,
                short_name=command.short_name,
                unit_type_id=command.unit_type_id,
                parent_unit_id=command.parent_unit_id,
                sort_order=command.sort_order,
                description=command.description,
                custom_fields=dict(command.custom_fields),
            )
            unit_type = await uow.unit_types.get(unit.unit_type_id)
            self._validate_custom_fields(
                unit.custom_fields,
                unit_type.custom_fields_schema if unit_type is not None else {},
                path="customFields",
            )
            await uow.units.add(unit)
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationUnitCreated",
                "organizationUnit",
                unit.id,
                before=None,
                after=unit,
            )
            await self._event(
                uow,
                version.organization_id,
                "organizationUnitChanged",
                "organizationUnit",
                unit.id,
                {"action": "created", "versionId": str(version.id)},
            )
            await uow.commit()
            return unit

    async def update_unit(self, command: UpdateUnitCommand, actor: Actor) -> OrganizationUnit:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            unit = await self._require_unit_in_version(uow, command.unit_id, version.id)
            await self._authorizer.require(
                actor,
                PERMISSION_UNIT_MANAGE,
                version.organization_id,
                unit_id=unit.id,
            )
            before = self._safe_state(unit)
            unit.assert_revision(command.unit_revision, "organizationUnit", unit.id)
            units = tuple(await uow.units.list_by_version(version.id, include_inactive=True))
            changes = dict(command.changes)
            allowed = {
                "code",
                "name",
                "short_name",
                "unit_type_id",
                "sort_order",
                "description",
                "custom_fields",
            }
            unknown = set(changes) - allowed
            if unknown:
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "Unsupported organization unit fields were supplied.",
                    details={"fields": sorted(unknown)},
                )
            if "code" in changes:
                code = normalized_code(str(changes["code"]))
                if any(
                    item.id != unit.id and item.active and item.code.casefold() == code.casefold()
                    for item in units
                ):
                    raise OrganizationError(
                        "VALIDATION_FAILED",
                        "Unit codes must be unique inside a structure version.",
                        details={"field": "code", "code": code},
                    )
                unit.code = code
            if "name" in changes:
                unit.name = non_empty_name(str(changes["name"]))
            if "short_name" in changes:
                short_name = changes["short_name"]
                unit.short_name = (
                    non_empty_name(str(short_name), field_name="short_name")
                    if short_name is not None
                    else None
                )
            if "unit_type_id" in changes:
                type_id = self._as_uuid(changes["unit_type_id"], "unit_type_id")
                unit_type = await uow.unit_types.get(type_id)
                if (
                    unit_type is None
                    or not unit_type.active
                    or unit_type.organization_id != version.organization_id
                ):
                    raise ResourceNotFoundError("organizationUnitType", type_id)
                unit.unit_type_id = type_id
            if "sort_order" in changes:
                sort_order = int(changes["sort_order"])
                if sort_order < 0:
                    raise OrganizationError(
                        "VALIDATION_FAILED",
                        "sortOrder must not be negative.",
                        details={"field": "sortOrder"},
                    )
                unit.sort_order = sort_order
            if "description" in changes:
                value = changes["description"]
                unit.description = str(value) if value is not None else None
            if "custom_fields" in changes:
                unit.custom_fields = dict(changes["custom_fields"] or {})
            await self._assert_configured_parent_type(
                uow,
                unit_type_id=unit.unit_type_id,
                parent_unit_id=unit.parent_unit_id,
                units=units,
            )
            unit_type = await uow.unit_types.get(unit.unit_type_id)
            self._validate_custom_fields(
                unit.custom_fields,
                unit_type.custom_fields_schema if unit_type is not None else {},
                path="customFields",
            )
            unit_previous_revision = unit.bump_revision()
            version_previous_revision = version.touch(command.version_revision)
            await uow.units.save(unit, expected_revision=unit_previous_revision)
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationUnitChanged",
                "organizationUnit",
                unit.id,
                before=before,
                after=unit,
            )
            await self._event(
                uow,
                version.organization_id,
                "organizationUnitChanged",
                "organizationUnit",
                unit.id,
                {"action": "updated", "versionId": str(version.id)},
            )
            await uow.commit()
            return unit

    async def move_unit(self, command: MoveUnitCommand, actor: Actor) -> OrganizationUnit:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            unit = await self._require_unit_in_version(uow, command.unit_id, version.id)
            await self._authorizer.require(
                actor,
                PERMISSION_UNIT_MANAGE,
                version.organization_id,
                unit_id=unit.id,
            )
            await self._authorizer.require(
                actor,
                PERMISSION_UNIT_MANAGE,
                version.organization_id,
                unit_id=command.parent_unit_id,
            )
            units = tuple(await uow.units.list_by_version(version.id, include_inactive=True))
            self._assert_valid_move(unit, command.parent_unit_id, units)
            await self._assert_configured_parent_type(
                uow,
                unit_type_id=unit.unit_type_id,
                parent_unit_id=command.parent_unit_id,
                units=units,
            )
            before = self._safe_state(unit)
            unit.assert_revision(command.unit_revision, "organizationUnit", unit.id)
            if command.sort_order < 0:
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "sortOrder must not be negative.",
                    details={"field": "sortOrder"},
                )
            unit_previous_revision = unit.bump_revision()
            unit.parent_unit_id = command.parent_unit_id
            unit.sort_order = command.sort_order
            version_previous_revision = version.touch(command.version_revision)
            await uow.units.save(unit, expected_revision=unit_previous_revision)
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationUnitMoved",
                "organizationUnit",
                unit.id,
                before=before,
                after=unit,
            )
            await self._event(
                uow,
                version.organization_id,
                "organizationUnitChanged",
                "organizationUnit",
                unit.id,
                {"action": "moved", "versionId": str(version.id)},
            )
            await uow.commit()
            return unit

    async def reorder_units(
        self, command: ReorderUnitsCommand, actor: Actor
    ) -> tuple[OrganizationUnit, ...]:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            await self._authorizer.require(
                actor,
                PERMISSION_UNIT_MANAGE,
                version.organization_id,
                unit_id=command.parent_unit_id,
            )
            if len({item.unit_id for item in command.items}) != len(command.items):
                raise OrganizationError(
                    "VALIDATION_FAILED", "Each unit may appear only once in a reorder request."
                )
            if len({item.sort_order for item in command.items}) != len(command.items):
                raise OrganizationError(
                    "VALIDATION_FAILED", "sortOrder values must be unique among reordered units."
                )
            changed: list[OrganizationUnit] = []
            before: list[dict[str, Any]] = []
            expected: dict[UUID, int] = {}
            for item in command.items:
                if item.sort_order < 0:
                    raise OrganizationError(
                        "VALIDATION_FAILED",
                        "sortOrder must not be negative.",
                        details={"field": "sortOrder"},
                    )
                unit = await self._require_unit_in_version(uow, item.unit_id, version.id)
                if unit.parent_unit_id != command.parent_unit_id:
                    raise VersionConflictError(
                        "All reordered units must be children of the supplied parent.",
                        details={"unitId": str(unit.id)},
                    )
                unit.assert_revision(item.revision, "organizationUnit", unit.id)
                await self._authorizer.require(
                    actor,
                    PERMISSION_UNIT_MANAGE,
                    version.organization_id,
                    unit_id=unit.id,
                )
                before.append(self._safe_state(unit))
                expected[unit.id] = unit.bump_revision()
                unit.sort_order = item.sort_order
                changed.append(unit)
            version_previous_revision = version.touch(command.version_revision)
            for unit in changed:
                await uow.units.save(unit, expected_revision=expected[unit.id])
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationUnitsReordered",
                "organizationStructureVersion",
                version.id,
                before={"units": before},
                after={"units": [self._safe_state(item) for item in changed]},
            )
            await uow.commit()
            return tuple(changed)

    async def deactivate_unit(
        self, command: DeactivateUnitCommand, actor: Actor
    ) -> OrganizationUnit:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            unit = await self._require_unit_in_version(uow, command.unit_id, version.id)
            await self._authorizer.require(
                actor,
                PERMISSION_UNIT_MANAGE,
                version.organization_id,
                unit_id=unit.id,
            )
            units = tuple(await uow.units.list_by_version(version.id, include_inactive=False))
            if any(item.parent_unit_id == unit.id for item in units):
                raise VersionConflictError(
                    "Move or deactivate child units before deactivating this unit.",
                    details={"unitId": str(unit.id)},
                )
            relationships = tuple(
                await uow.relationships.list_by_version(version.id, include_inactive=False)
            )
            if any(
                item.source_unit_id == unit.id or item.target_unit_id == unit.id
                for item in relationships
            ):
                raise VersionConflictError(
                    "Remove active relationships before deactivating this unit.",
                    details={"unitId": str(unit.id)},
                )
            slots = tuple(await uow.staffing.list_by_version(version.id))
            if any(
                item.organization_unit_id == unit.id
                and item.status not in {StaffingSlotStatus.CLOSED, StaffingSlotStatus.CLOSING}
                for item in slots
            ):
                raise VersionConflictError(
                    "Close active staffing slots before deactivating this unit.",
                    details={"unitId": str(unit.id)},
                )
            unit.assert_revision(command.unit_revision, "organizationUnit", unit.id)
            before = self._safe_state(unit)
            unit_previous_revision = unit.bump_revision()
            unit.active = False
            version_previous_revision = version.touch(command.version_revision)
            await uow.units.save(unit, expected_revision=unit_previous_revision)
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationUnitDeactivated",
                "organizationUnit",
                unit.id,
                before=before,
                after=unit,
                reason=command.reason,
            )
            await self._event(
                uow,
                version.organization_id,
                "organizationUnitChanged",
                "organizationUnit",
                unit.id,
                {"action": "deactivated", "versionId": str(version.id)},
            )
            await uow.commit()
            return unit

    async def list_relationships(
        self, version_id: UUID, actor: Actor, *, include_inactive: bool = False
    ) -> tuple[OrganizationRelationship, ...]:
        async with self._uow_factory() as uow:
            version = await self._require_version(uow, version_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_READ, version.organization_id
            )
            return tuple(
                await uow.relationships.list_by_version(
                    version_id, include_inactive=include_inactive
                )
            )

    async def add_relationship(
        self, command: AddRelationshipCommand, actor: Actor
    ) -> OrganizationRelationship:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            await self._authorizer.require(
                actor,
                PERMISSION_RELATIONSHIP_MANAGE,
                version.organization_id,
                unit_id=command.source_unit_id,
            )
            await self._authorizer.require(
                actor,
                PERMISSION_RELATIONSHIP_MANAGE,
                version.organization_id,
                unit_id=command.target_unit_id,
            )
            relationship = OrganizationRelationship(
                id=uuid4(),
                structure_version_id=version.id,
                relationship_type_id=command.relationship_type_id,
                source_unit_id=command.source_unit_id,
                target_unit_id=command.target_unit_id,
                effective_from=command.effective_from,
                effective_to=command.effective_to,
                metadata=dict(command.metadata),
            )
            await self._assert_relationship_valid(uow, version, relationship)
            version_previous_revision = version.touch(command.version_revision)
            await uow.relationships.add(relationship)
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationRelationshipCreated",
                "organizationRelationship",
                relationship.id,
                before=None,
                after=relationship,
            )
            await self._event(
                uow,
                version.organization_id,
                "organizationUnitChanged",
                "organizationRelationship",
                relationship.id,
                {"action": "relationshipCreated", "versionId": str(version.id)},
            )
            await uow.commit()
            return relationship

    async def update_relationship(
        self, command: UpdateRelationshipCommand, actor: Actor
    ) -> OrganizationRelationship:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            relationship = await self._require_relationship_in_version(
                uow, command.relationship_id, version.id
            )
            await self._authorizer.require(
                actor,
                PERMISSION_RELATIONSHIP_MANAGE,
                version.organization_id,
                unit_id=relationship.source_unit_id,
            )
            relationship.assert_revision(
                command.relationship_revision, "organizationRelationship", relationship.id
            )
            before = self._safe_state(relationship)
            changes = dict(command.changes)
            allowed = {
                "relationship_type_id",
                "source_unit_id",
                "target_unit_id",
                "effective_from",
                "effective_to",
                "metadata",
                "active",
            }
            unknown = set(changes) - allowed
            if unknown:
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "Unsupported organization relationship fields were supplied.",
                    details={"fields": sorted(unknown)},
                )
            if "relationship_type_id" in changes:
                relationship.relationship_type_id = self._as_uuid(
                    changes["relationship_type_id"], "relationship_type_id"
                )
            if "source_unit_id" in changes:
                relationship.source_unit_id = self._as_uuid(
                    changes["source_unit_id"], "source_unit_id"
                )
            if "target_unit_id" in changes:
                relationship.target_unit_id = self._as_uuid(
                    changes["target_unit_id"], "target_unit_id"
                )
            if "effective_from" in changes:
                relationship.effective_from = self._as_date_or_none(
                    changes["effective_from"], "effective_from"
                )
            if "effective_to" in changes:
                relationship.effective_to = self._as_date_or_none(
                    changes["effective_to"], "effective_to"
                )
            if "metadata" in changes:
                relationship.metadata = dict(changes["metadata"] or {})
            if "active" in changes:
                relationship.active = bool(changes["active"])
            validate_date_range(relationship.effective_from, relationship.effective_to)
            await self._authorizer.require(
                actor,
                PERMISSION_RELATIONSHIP_MANAGE,
                version.organization_id,
                unit_id=relationship.source_unit_id,
            )
            await self._authorizer.require(
                actor,
                PERMISSION_RELATIONSHIP_MANAGE,
                version.organization_id,
                unit_id=relationship.target_unit_id,
            )
            await self._assert_relationship_valid(
                uow, version, relationship, exclude_relationship_id=relationship.id
            )
            relationship_previous_revision = relationship.bump_revision()
            version_previous_revision = version.touch(command.version_revision)
            await uow.relationships.save(
                relationship, expected_revision=relationship_previous_revision
            )
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationRelationshipChanged",
                "organizationRelationship",
                relationship.id,
                before=before,
                after=relationship,
            )
            await self._event(
                uow,
                version.organization_id,
                "organizationUnitChanged",
                "organizationRelationship",
                relationship.id,
                {"action": "relationshipUpdated", "versionId": str(version.id)},
            )
            await uow.commit()
            return relationship

    async def remove_relationship(
        self, command: RemoveRelationshipCommand, actor: Actor
    ) -> OrganizationRelationship:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            relationship = await self._require_relationship_in_version(
                uow, command.relationship_id, version.id
            )
            await self._authorizer.require(
                actor,
                PERMISSION_RELATIONSHIP_MANAGE,
                version.organization_id,
                unit_id=relationship.source_unit_id,
            )
            relationship.assert_revision(
                command.relationship_revision, "organizationRelationship", relationship.id
            )
            before = self._safe_state(relationship)
            relationship_previous_revision = relationship.bump_revision()
            relationship.active = False
            version_previous_revision = version.touch(command.version_revision)
            await uow.relationships.save(
                relationship, expected_revision=relationship_previous_revision
            )
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationRelationshipRemoved",
                "organizationRelationship",
                relationship.id,
                before=before,
                after=relationship,
                reason=command.reason,
            )
            await uow.commit()
            return relationship

    async def list_positions(
        self,
        organization_id: UUID,
        actor: Actor,
        *,
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 20,
        sort: str = "name",
    ) -> tuple[tuple[PositionDefinition, ...], int]:
        await self._authorizer.require(actor, PERMISSION_STRUCTURE_READ, organization_id)
        async with self._uow_factory() as uow:
            positions = await uow.positions.list(
                organization_id,
                include_inactive=include_inactive,
                offset=(page - 1) * page_size,
                limit=page_size,
                sort=sort,
            )
            total = await uow.positions.count(organization_id, include_inactive=include_inactive)
            return tuple(positions), total

    async def create_position(
        self, command: CreatePositionCommand, actor: Actor
    ) -> PositionDefinition:
        await self._authorizer.require(actor, PERMISSION_STAFFING_MANAGE, command.organization_id)
        async with self._uow_factory() as uow:
            organization = await uow.organizations.get(command.organization_id)
            if organization is None:
                raise ResourceNotFoundError("organization", command.organization_id)
            existing = await uow.positions.list(
                command.organization_id, include_inactive=True, offset=0, limit=10_000
            )
            code = normalized_code(command.code)
            if any(item.code.casefold() == code.casefold() for item in existing):
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "Position definition codes must be unique within an organization.",
                    details={"field": "code", "code": code},
                )
            position = PositionDefinition(
                id=uuid4(),
                organization_id=command.organization_id,
                code=code,
                name=command.name,
                description=command.description,
                job_family=command.job_family,
                grade=command.grade,
                custom_fields=dict(command.custom_fields),
            )
            self._validate_custom_fields(position.custom_fields, {}, path="customFields")
            await uow.positions.add(position)
            await self._audit(
                uow,
                actor,
                command.organization_id,
                "positionDefinitionCreated",
                "positionDefinition",
                position.id,
                before=None,
                after=position,
            )
            await uow.commit()
            return position

    async def update_position(
        self, command: UpdatePositionCommand, actor: Actor
    ) -> PositionDefinition:
        async with self._uow_factory() as uow:
            position = await uow.positions.get(command.position_id)
            if position is None:
                raise ResourceNotFoundError("positionDefinition", command.position_id)
            await self._authorizer.require(
                actor, PERMISSION_STAFFING_MANAGE, position.organization_id
            )
            position.assert_revision(command.revision, "positionDefinition", position.id)
            before = self._safe_state(position)
            changes = dict(command.changes)
            allowed = {
                "code",
                "name",
                "description",
                "job_family",
                "grade",
                "active",
                "custom_fields",
            }
            unknown = set(changes) - allowed
            if unknown:
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "Unsupported position fields were supplied.",
                    details={"fields": sorted(unknown)},
                )
            if "code" in changes:
                code = normalized_code(str(changes["code"]))
                existing = await uow.positions.list(
                    position.organization_id, include_inactive=True, offset=0, limit=10_000
                )
                if any(
                    item.id != position.id and item.code.casefold() == code.casefold()
                    for item in existing
                ):
                    raise OrganizationError(
                        "VALIDATION_FAILED",
                        "Position definition codes must be unique within an organization.",
                        details={"field": "code", "code": code},
                    )
                position.code = code
            if "name" in changes:
                position.name = non_empty_name(str(changes["name"]))
            for field_name in ("description", "job_family", "grade"):
                if field_name in changes:
                    value = changes[field_name]
                    setattr(position, field_name, str(value) if value is not None else None)
            if "active" in changes:
                position.active = bool(changes["active"])
            if "custom_fields" in changes:
                position.custom_fields = dict(changes["custom_fields"] or {})
            self._validate_custom_fields(position.custom_fields, {}, path="customFields")
            previous_revision = position.bump_revision()
            position.updated_at = utc_now()
            await uow.positions.save(position, expected_revision=previous_revision)
            await self._audit(
                uow,
                actor,
                position.organization_id,
                "positionDefinitionChanged",
                "positionDefinition",
                position.id,
                before=before,
                after=position,
            )
            await uow.commit()
            return position

    async def list_staffing_slots(
        self,
        organization_id: UUID,
        actor: Actor,
        *,
        version_id: UUID | None = None,
        unit_id: UUID | None = None,
        status: StaffingSlotStatus | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "organizationUnitId",
    ) -> tuple[tuple[StaffingSlot, ...], int]:
        await self._authorizer.require(
            actor, PERMISSION_STRUCTURE_READ, organization_id, unit_id=unit_id
        )
        async with self._uow_factory() as uow:
            if version_id is not None:
                version = await self._require_version(uow, version_id)
                if version.organization_id != organization_id:
                    raise VersionConflictError("The version belongs to another organization.")
            slots = await uow.staffing.list(
                organization_id,
                version_id=version_id,
                unit_id=unit_id,
                status=status,
                offset=(page - 1) * page_size,
                limit=page_size,
                sort=sort,
            )
            total = await uow.staffing.count(
                organization_id,
                version_id=version_id,
                unit_id=unit_id,
                status=status,
            )
            return tuple(slots), total

    async def create_staffing_slot(
        self, command: CreateStaffingSlotCommand, actor: Actor
    ) -> StaffingSlot:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            await self._authorizer.require(
                actor,
                PERMISSION_STAFFING_MANAGE,
                version.organization_id,
                unit_id=command.organization_unit_id,
            )
            policy = await self._policy_for_version(uow, version)
            if not policy.managers_can_create_staffing_slots:
                # Requiring the same permission without a unit context distinguishes
                # organization-wide HR/admin grants from manager-scoped grants without
                # hardcoding a role or position title.
                await self._authorizer.require(
                    actor,
                    PERMISSION_STAFFING_MANAGE,
                    version.organization_id,
                )
            slot = StaffingSlot(
                id=uuid4(),
                structure_version_id=version.id,
                stable_key=uuid4(),
                organization_unit_id=command.organization_unit_id,
                position_definition_id=command.position_definition_id,
                reports_to_slot_id=command.reports_to_slot_id,
                head_of_unit=command.head_of_unit,
                full_time_equivalent=command.full_time_equivalent,
                employment_type=command.employment_type,
                status=command.status,
                effective_from=command.effective_from,
                effective_to=command.effective_to,
                custom_fields=dict(command.custom_fields),
            )
            await self._assert_staffing_slot_valid(uow, version, slot)
            version_previous_revision = version.touch(command.version_revision)
            await uow.staffing.add(slot)
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "staffingSlotCreated",
                "staffingSlot",
                slot.id,
                before=None,
                after=slot,
            )
            await self._event(
                uow,
                version.organization_id,
                "staffingSlotCreated",
                "staffingSlot",
                slot.id,
                {"versionId": str(version.id), "unitId": str(slot.organization_unit_id)},
            )
            await uow.commit()
            return slot

    async def update_staffing_slot(
        self, command: UpdateStaffingSlotCommand, actor: Actor
    ) -> StaffingSlot:
        async with self._uow_factory() as uow:
            slot = await uow.staffing.get(command.slot_id)
            if slot is None:
                raise ResourceNotFoundError("staffingSlot", command.slot_id)
            version = await self._require_editable_version(uow, slot.structure_version_id)
            await self._authorizer.require(
                actor,
                PERMISSION_STAFFING_MANAGE,
                version.organization_id,
                unit_id=slot.organization_unit_id,
            )
            slot.assert_revision(command.slot_revision, "staffingSlot", slot.id)
            before = self._safe_state(slot)
            changes = dict(command.changes)
            allowed = {
                "organization_unit_id",
                "position_definition_id",
                "reports_to_slot_id",
                "head_of_unit",
                "full_time_equivalent",
                "employment_type",
                "status",
                "effective_from",
                "effective_to",
                "custom_fields",
            }
            unknown = set(changes) - allowed
            if unknown:
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "Unsupported staffing slot fields were supplied.",
                    details={"fields": sorted(unknown)},
                )
            uuid_fields = ("organization_unit_id", "position_definition_id")
            for field_name in uuid_fields:
                if field_name in changes:
                    setattr(slot, field_name, self._as_uuid(changes[field_name], field_name))
            if "reports_to_slot_id" in changes:
                value = changes["reports_to_slot_id"]
                slot.reports_to_slot_id = (
                    self._as_uuid(value, "reports_to_slot_id") if value is not None else None
                )
            if "head_of_unit" in changes:
                slot.head_of_unit = bool(changes["head_of_unit"])
            if "full_time_equivalent" in changes:
                slot.full_time_equivalent = Decimal(str(changes["full_time_equivalent"]))
            if "employment_type" in changes:
                slot.employment_type = EmploymentType(str(changes["employment_type"]))
            if "status" in changes:
                slot.status = StaffingSlotStatus(str(changes["status"]))
            if "effective_from" in changes:
                slot.effective_from = self._as_date_or_none(
                    changes["effective_from"], "effective_from"
                )
            if "effective_to" in changes:
                slot.effective_to = self._as_date_or_none(changes["effective_to"], "effective_to")
            if "custom_fields" in changes:
                slot.custom_fields = dict(changes["custom_fields"] or {})
            slot.validate_fte()
            validate_date_range(slot.effective_from, slot.effective_to)
            await self._authorizer.require(
                actor,
                PERMISSION_STAFFING_MANAGE,
                version.organization_id,
                unit_id=slot.organization_unit_id,
            )
            await self._assert_staffing_slot_valid(uow, version, slot, exclude_slot_id=slot.id)
            slot_previous_revision = slot.bump_revision()
            version_previous_revision = version.touch(command.version_revision)
            await uow.staffing.save(slot, expected_revision=slot_previous_revision)
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "staffingSlotChanged",
                "staffingSlot",
                slot.id,
                before=before,
                after=slot,
            )
            await uow.commit()
            return slot

    async def close_staffing_slot(
        self, command: CloseStaffingSlotCommand, actor: Actor
    ) -> StaffingSlot:
        async with self._uow_factory() as uow:
            slot = await uow.staffing.get(command.slot_id)
            if slot is None:
                raise ResourceNotFoundError("staffingSlot", command.slot_id)
            version = await self._require_editable_version(uow, slot.structure_version_id)
            await self._authorizer.require(
                actor,
                PERMISSION_STAFFING_MANAGE,
                version.organization_id,
                unit_id=slot.organization_unit_id,
            )
            direct_reports = tuple(
                item
                for item in await uow.staffing.list_by_version(version.id)
                if item.id != slot.id
                and item.reports_to_slot_id == slot.id
                and item.status is not StaffingSlotStatus.CLOSED
                and not (
                    item.status is StaffingSlotStatus.CLOSING
                    and item.effective_to is not None
                    and item.effective_to <= command.effective_to
                )
            )
            if direct_reports:
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "A staffing slot with active direct reports cannot be closed.",
                    details={
                        "staffingSlotId": str(slot.id),
                        "directReportSlotIds": [str(item.id) for item in direct_reports],
                    },
                )
            before = self._safe_state(slot)
            slot_previous_revision = slot.close(
                effective_to=command.effective_to, expected_revision=command.slot_revision
            )
            version_previous_revision = version.touch(command.version_revision)
            await uow.staffing.save(slot, expected_revision=slot_previous_revision)
            await uow.versions.save(version, expected_revision=version_previous_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                (
                    "staffingSlotClosureScheduled"
                    if slot.status is StaffingSlotStatus.CLOSING
                    else "staffingSlotClosed"
                ),
                "staffingSlot",
                slot.id,
                before=before,
                after=slot,
                reason=command.reason,
            )
            await self._event(
                uow,
                version.organization_id,
                (
                    "staffingSlotClosureScheduled"
                    if slot.status is StaffingSlotStatus.CLOSING
                    else "staffingSlotVacated"
                ),
                "staffingSlot",
                slot.id,
                {"versionId": str(version.id), "effectiveTo": command.effective_to.isoformat()},
            )
            await uow.commit()
            return slot

    async def list_unit_types(
        self,
        organization_id: UUID,
        actor: Actor,
        *,
        include_inactive: bool = False,
    ) -> tuple[OrganizationUnitType, ...]:
        await self._authorizer.require(actor, PERMISSION_STRUCTURE_READ, organization_id)
        async with self._uow_factory() as uow:
            return tuple(
                await uow.unit_types.list(organization_id, include_inactive=include_inactive)
            )

    async def create_unit_type(
        self, command: CreateUnitTypeCommand, actor: Actor
    ) -> OrganizationUnitType:
        await self._authorizer.require(actor, PERMISSION_STRUCTURE_EDIT, command.organization_id)
        async with self._uow_factory() as uow:
            existing = await uow.unit_types.list(command.organization_id, include_inactive=True)
            code = normalized_code(command.code)
            if any(item.code.casefold() == code.casefold() for item in existing):
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "Unit type codes must be unique within an organization.",
                    details={"field": "code", "code": code},
                )
            for parent_type_id in command.allowed_parent_type_ids:
                parent_type = await uow.unit_types.get(parent_type_id)
                if parent_type is None or parent_type.organization_id != command.organization_id:
                    raise ResourceNotFoundError("organizationUnitType", parent_type_id)
            unit_type = OrganizationUnitType(
                id=uuid4(),
                organization_id=command.organization_id,
                code=code,
                name=command.name,
                description=command.description,
                allowed_parent_type_ids=command.allowed_parent_type_ids,
                custom_fields_schema=dict(command.custom_fields_schema),
            )
            self._validate_custom_fields(
                unit_type.custom_fields_schema, {}, path="customFieldsSchema"
            )
            await uow.unit_types.add(unit_type)
            await self._audit(
                uow,
                actor,
                command.organization_id,
                "organizationUnitTypeCreated",
                "organizationUnitType",
                unit_type.id,
                before=None,
                after=unit_type,
            )
            await uow.commit()
            return unit_type

    async def update_unit_type(
        self, command: UpdateUnitTypeCommand, actor: Actor
    ) -> OrganizationUnitType:
        async with self._uow_factory() as uow:
            unit_type = await uow.unit_types.get(command.type_id)
            if unit_type is None:
                raise ResourceNotFoundError("organizationUnitType", command.type_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_EDIT, unit_type.organization_id
            )
            unit_type.assert_revision(command.revision, "organizationUnitType", unit_type.id)
            before = self._safe_state(unit_type)
            changes = dict(command.changes)
            allowed = {
                "code",
                "name",
                "description",
                "active",
                "allowed_parent_type_ids",
                "custom_fields_schema",
            }
            unknown = set(changes) - allowed
            if unknown:
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "Unsupported unit type fields were supplied.",
                    details={"fields": sorted(unknown)},
                )
            if "code" in changes:
                code = normalized_code(str(changes["code"]))
                existing = await uow.unit_types.list(
                    unit_type.organization_id, include_inactive=True
                )
                if any(
                    item.id != unit_type.id and item.code.casefold() == code.casefold()
                    for item in existing
                ):
                    raise OrganizationError(
                        "VALIDATION_FAILED",
                        "Unit type codes must be unique within an organization.",
                        details={"field": "code", "code": code},
                    )
                unit_type.code = code
            if "name" in changes:
                unit_type.name = non_empty_name(str(changes["name"]))
            if "description" in changes:
                value = changes["description"]
                unit_type.description = str(value) if value is not None else None
            if "active" in changes:
                unit_type.active = bool(changes["active"])
            if "allowed_parent_type_ids" in changes:
                parent_ids = tuple(
                    self._as_uuid(item, "allowed_parent_type_ids")
                    for item in changes["allowed_parent_type_ids"] or ()
                )
                for parent_type_id in parent_ids:
                    parent_type = await uow.unit_types.get(parent_type_id)
                    if (
                        parent_type is None
                        or parent_type.organization_id != unit_type.organization_id
                    ):
                        raise ResourceNotFoundError("organizationUnitType", parent_type_id)
                unit_type.allowed_parent_type_ids = parent_ids
            if "custom_fields_schema" in changes:
                unit_type.custom_fields_schema = dict(changes["custom_fields_schema"] or {})
            self._validate_custom_fields(
                unit_type.custom_fields_schema, {}, path="customFieldsSchema"
            )
            previous_revision = unit_type.bump_revision()
            unit_type.updated_at = utc_now()
            await uow.unit_types.save(unit_type, expected_revision=previous_revision)
            await self._audit(
                uow,
                actor,
                unit_type.organization_id,
                "organizationUnitTypeChanged",
                "organizationUnitType",
                unit_type.id,
                before=before,
                after=unit_type,
            )
            await uow.commit()
            return unit_type

    async def list_relationship_types(
        self,
        organization_id: UUID,
        actor: Actor,
        *,
        include_inactive: bool = False,
    ) -> tuple[OrganizationRelationshipType, ...]:
        await self._authorizer.require(actor, PERMISSION_STRUCTURE_READ, organization_id)
        async with self._uow_factory() as uow:
            return tuple(
                await uow.relationship_types.list(
                    organization_id, include_inactive=include_inactive
                )
            )

    async def create_relationship_type(
        self, command: CreateRelationshipTypeCommand, actor: Actor
    ) -> OrganizationRelationshipType:
        await self._authorizer.require(actor, PERMISSION_STRUCTURE_EDIT, command.organization_id)
        async with self._uow_factory() as uow:
            existing = await uow.relationship_types.list(
                command.organization_id, include_inactive=True
            )
            code = normalized_code(command.code)
            if any(item.code.casefold() == code.casefold() for item in existing):
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "Relationship type codes must be unique within an organization.",
                    details={"field": "code", "code": code},
                )
            relationship_type = OrganizationRelationshipType(
                id=uuid4(),
                organization_id=command.organization_id,
                code=code,
                name=command.name,
                description=command.description,
                directed=command.directed,
                prevents_cycles=command.prevents_cycles,
                allow_self_link=command.allow_self_link,
                metadata_schema=dict(command.metadata_schema),
            )
            self._validate_custom_fields(
                relationship_type.metadata_schema, {}, path="metadataSchema"
            )
            await uow.relationship_types.add(relationship_type)
            await self._audit(
                uow,
                actor,
                command.organization_id,
                "organizationRelationshipTypeCreated",
                "organizationRelationshipType",
                relationship_type.id,
                before=None,
                after=relationship_type,
            )
            await uow.commit()
            return relationship_type

    async def update_relationship_type(
        self, command: UpdateRelationshipTypeCommand, actor: Actor
    ) -> OrganizationRelationshipType:
        async with self._uow_factory() as uow:
            relationship_type = await uow.relationship_types.get(command.type_id)
            if relationship_type is None:
                raise ResourceNotFoundError("organizationRelationshipType", command.type_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_EDIT, relationship_type.organization_id
            )
            relationship_type.assert_revision(
                command.revision, "organizationRelationshipType", relationship_type.id
            )
            before = self._safe_state(relationship_type)
            changes = dict(command.changes)
            allowed = {
                "code",
                "name",
                "description",
                "directed",
                "prevents_cycles",
                "allow_self_link",
                "active",
                "metadata_schema",
            }
            unknown = set(changes) - allowed
            if unknown:
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "Unsupported relationship type fields were supplied.",
                    details={"fields": sorted(unknown)},
                )
            if "code" in changes:
                code = normalized_code(str(changes["code"]))
                existing = await uow.relationship_types.list(
                    relationship_type.organization_id, include_inactive=True
                )
                if any(
                    item.id != relationship_type.id and item.code.casefold() == code.casefold()
                    for item in existing
                ):
                    raise OrganizationError(
                        "VALIDATION_FAILED",
                        "Relationship type codes must be unique within an organization.",
                        details={"field": "code", "code": code},
                    )
                relationship_type.code = code
            if "name" in changes:
                relationship_type.name = non_empty_name(str(changes["name"]))
            if "description" in changes:
                value = changes["description"]
                relationship_type.description = str(value) if value is not None else None
            for field_name in ("directed", "prevents_cycles", "allow_self_link", "active"):
                if field_name in changes:
                    setattr(relationship_type, field_name, bool(changes[field_name]))
            if "metadata_schema" in changes:
                relationship_type.metadata_schema = dict(changes["metadata_schema"] or {})
            self._validate_custom_fields(
                relationship_type.metadata_schema, {}, path="metadataSchema"
            )
            previous_revision = relationship_type.bump_revision()
            relationship_type.updated_at = utc_now()
            await uow.relationship_types.save(
                relationship_type, expected_revision=previous_revision
            )
            await self._audit(
                uow,
                actor,
                relationship_type.organization_id,
                "organizationRelationshipTypeChanged",
                "organizationRelationshipType",
                relationship_type.id,
                before=before,
                after=relationship_type,
            )
            await uow.commit()
            return relationship_type

    async def get_policy(self, version_id: UUID, actor: Actor) -> OrganizationPolicy:
        async with self._uow_factory() as uow:
            version = await self._require_version(uow, version_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_READ, version.organization_id
            )
            policy = await uow.policies.get_for_version(version.id)
            if policy is None:
                policy = await uow.policies.get_default(version.organization_id)
            if policy is None:
                return OrganizationPolicy(
                    id=uuid4(),
                    organization_id=version.organization_id,
                    structure_version_id=version.id,
                    created_by=version.created_by,
                )
            return policy

    async def update_policy(self, command: UpdatePolicyCommand, actor: Actor) -> OrganizationPolicy:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_EDIT, version.organization_id
            )
            policy = await uow.policies.get_for_version(version.id)
            if policy is None:
                base = await uow.policies.get_default(version.organization_id)
                policy = (
                    base.copy_for_version(version.id, actor.user_id)
                    if base is not None
                    else OrganizationPolicy(
                        id=uuid4(),
                        organization_id=version.organization_id,
                        structure_version_id=version.id,
                        created_by=actor.user_id,
                    )
                )
                if command.policy_revision != 1:
                    policy.assert_revision(command.policy_revision, "organizationPolicy", policy.id)
                is_new = True
            else:
                policy.assert_revision(command.policy_revision, "organizationPolicy", policy.id)
                is_new = False
            before = None if is_new else self._safe_state(policy)
            allowed = {
                "managers_can_create_employee_drafts",
                "managers_can_assign_existing_employees",
                "manager_changes_require_hr_approval",
                "managers_can_create_staffing_slots",
                "staffing_changes_require_finance_review",
                "structure_publish_requires_review",
                "allow_multiple_unit_heads",
                "allow_cross_unit_relationships",
            }
            unknown = set(command.changes) - allowed
            if unknown:
                raise OrganizationError(
                    "VALIDATION_FAILED",
                    "Unsupported organization policy fields were supplied.",
                    details={"fields": sorted(unknown)},
                )
            for field_name, value in command.changes.items():
                setattr(policy, field_name, bool(value))
            if is_new:
                await uow.policies.add(policy)
            else:
                previous_policy_revision = policy.bump_revision()
                policy.updated_at = utc_now()
                await uow.policies.save(policy, expected_revision=previous_policy_revision)
            previous_version_revision = version.touch(command.version_revision)
            await uow.versions.save(version, expected_revision=previous_version_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationPolicyChanged",
                "organizationPolicy",
                policy.id,
                before=before,
                after=policy,
            )
            await uow.commit()
            return policy

    async def validate_draft(self, version_id: UUID, actor: Actor) -> ValidationOutcome:
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, version_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_EDIT, version.organization_id
            )
            report = await self._validate_version(uow, version)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationStructureValidated",
                "organizationStructureVersion",
                version.id,
                before=None,
                after={
                    "isValid": report.is_valid,
                    "errorCount": report.error_count,
                    "warningCount": report.warning_count,
                    "issues": [item.as_dict() for item in report.issues],
                },
            )
            await uow.commit()
            return ValidationOutcome(version.id, version.revision, report)

    async def submit_for_review(
        self, command: SubmitReviewCommand, actor: Actor
    ) -> StructureReviewRequest:
        reason = non_empty_name(command.reason, field_name="reason")
        async with self._uow_factory() as uow:
            version = await self._require_editable_version(uow, command.version_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_EDIT, version.organization_id
            )
            report = await self._validate_version(uow, version)
            if not report.is_valid:
                raise DraftValidationError([item.as_dict() for item in report.issues])
            existing = await uow.review_requests.get_pending_for_version(version.id)
            if existing is not None:
                raise VersionConflictError(
                    "A review request is already pending for this structure version.",
                    details={"reviewRequestId": str(existing.id)},
                )
            previous_version_revision = version.submit_for_review(command.revision)
            review_request = StructureReviewRequest(
                id=uuid4(),
                organization_id=version.organization_id,
                structure_version_id=version.id,
                submitted_by=actor.user_id,
                submission_reason=reason,
            )
            await uow.review_requests.add(review_request)
            await uow.versions.save(version, expected_revision=previous_version_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationStructureSubmittedForReview",
                "organizationStructureVersion",
                version.id,
                before={"status": StructureVersionStatus.DRAFT.value},
                after={
                    "status": version.status.value,
                    "revision": version.revision,
                    "reviewRequestId": str(review_request.id),
                },
                reason=reason,
            )
            await uow.commit()
            return review_request

    async def return_for_correction(
        self, command: ReturnForCorrectionCommand, actor: Actor
    ) -> OrganizationStructureVersion:
        reason = non_empty_name(command.reason, field_name="reason")
        async with self._uow_factory() as uow:
            version = await self._require_version(uow, command.version_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_REVIEW, version.organization_id
            )
            review_request = await uow.review_requests.get_pending_for_version(version.id)
            if review_request is None:
                raise VersionConflictError(
                    "No pending review request exists for this structure version."
                )
            previous_review_revision = review_request.return_for_correction(
                actor.user_id, reason, command.review_revision
            )
            previous_version_revision = version.return_for_correction(command.revision)
            await uow.review_requests.save(
                review_request, expected_revision=previous_review_revision
            )
            await uow.versions.save(version, expected_revision=previous_version_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationStructureReturnedForCorrection",
                "organizationStructureVersion",
                version.id,
                before={"status": StructureVersionStatus.IN_REVIEW.value},
                after={"status": version.status.value, "revision": version.revision},
                reason=reason,
            )
            await uow.commit()
            return version

    async def publish_structure(
        self, command: PublishStructureCommand, actor: Actor
    ) -> OrganizationStructureVersion:
        reason = non_empty_name(command.reason, field_name="reason")
        async with self._uow_factory() as uow:
            version = await self._require_version(uow, command.version_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_PUBLISH, version.organization_id
            )
            if version.status not in {
                StructureVersionStatus.DRAFT,
                StructureVersionStatus.IN_REVIEW,
            }:
                raise VersionConflictError(
                    "Only a draft or reviewed structure can be published.",
                    details={"versionId": str(version.id), "status": version.status.value},
                )
            version.assert_revision(command.revision, "organizationStructureVersion", version.id)
            report = await self._validate_version(
                uow,
                version,
                effective_from=command.effective_from,
            )
            if not report.is_valid:
                raise DraftValidationError([item.as_dict() for item in report.issues])
            policy = await self._policy_for_version(uow, version)
            review_request = await uow.review_requests.get_pending_for_version(version.id)
            staffing_changed = await self._staffing_changed_from_base(uow, version)
            review_reasons: list[str] = []
            if policy.structure_publish_requires_review:
                review_reasons.append("structurePolicy")
            if policy.staffing_changes_require_finance_review and staffing_changed:
                review_reasons.append("staffingFinancePolicy")
            review_required = bool(review_reasons)
            if review_required:
                if version.status is not StructureVersionStatus.IN_REVIEW:
                    raise VersionConflictError(
                        "Organization policy requires review before publication.",
                        details={"reviewReasons": review_reasons},
                    )
                if review_request is None:
                    raise VersionConflictError(
                        "A pending review request is required before publication."
                    )
                if command.review_revision is None:
                    raise OrganizationError(
                        "VALIDATION_FAILED",
                        "reviewRevision is required when publication review is enabled.",
                        details={"field": "reviewRevision"},
                    )
                previous_review_revision = review_request.approve(
                    actor.user_id, reason, command.review_revision
                )
                await uow.review_requests.save(
                    review_request, expected_revision=previous_review_revision
                )
            elif review_request is not None and version.status is StructureVersionStatus.IN_REVIEW:
                expected_review_revision = command.review_revision or review_request.revision
                previous_review_revision = review_request.approve(
                    actor.user_id, reason, expected_review_revision
                )
                await uow.review_requests.save(
                    review_request, expected_revision=previous_review_revision
                )

            published_versions = tuple(
                await uow.versions.list(
                    version.organization_id,
                    status=StructureVersionStatus.PUBLISHED,
                    offset=0,
                    limit=10_000,
                )
            )
            closed_version_ids: list[str] = []
            for published in published_versions:
                if published.id == version.id:
                    continue
                start = published.effective_from or date.min
                end = published.effective_to or date.max
                if end < command.effective_from:
                    continue
                if start >= command.effective_from:
                    raise VersionConflictError(
                        "The publication effective date overlaps another published version.",
                        details={
                            "conflictingVersionId": str(published.id),
                            "conflictingEffectiveFrom": (
                                published.effective_from.isoformat()
                                if published.effective_from
                                else None
                            ),
                        },
                    )
                previous_revision = published.revision
                published.effective_to = command.effective_from - timedelta(days=1)
                published.bump_revision()
                await uow.versions.save(published, expected_revision=previous_revision)
                closed_version_ids.append(str(published.id))

            previous_version_revision = version.publish(
                expected_revision=command.revision,
                effective_from=command.effective_from,
                actor_id=actor.user_id,
            )
            await uow.versions.save(version, expected_revision=previous_version_revision)
            await self._audit(
                uow,
                actor,
                version.organization_id,
                "organizationStructurePublished",
                "organizationStructureVersion",
                version.id,
                before={
                    "status": (
                        StructureVersionStatus.IN_REVIEW.value
                        if review_request is not None
                        else StructureVersionStatus.DRAFT.value
                    ),
                    "revision": command.revision,
                },
                after={
                    **self._safe_state(version),
                    "closedVersionIds": closed_version_ids,
                },
                reason=reason,
            )
            await self._event(
                uow,
                version.organization_id,
                "organizationStructurePublished",
                "organizationStructureVersion",
                version.id,
                {
                    "organizationId": str(version.organization_id),
                    "versionNumber": version.version_number,
                    "effectiveFrom": command.effective_from.isoformat(),
                    "revision": version.revision,
                },
            )
            await uow.commit()
            return version

    async def list_review_requests(
        self, version_id: UUID, actor: Actor
    ) -> tuple[StructureReviewRequest, ...]:
        async with self._uow_factory() as uow:
            version = await self._require_version(uow, version_id)
            await self._authorizer.require(
                actor, PERMISSION_STRUCTURE_REVIEW, version.organization_id
            )
            return tuple(await uow.review_requests.list_for_version(version.id))

    async def _validate_version(
        self,
        uow: OrganizationUnitOfWork,
        version: OrganizationStructureVersion,
        *,
        effective_from: date | None = None,
    ) -> ValidationReport:
        snapshot = await self._snapshot(uow, version)
        internal_report = self._validator.validate(snapshot)
        external_issues = tuple(
            await self._external_validator.validate_structure_version(
                version.id,
                effective_from=effective_from,
            )
        )
        return ValidationReport(internal_report.issues + external_issues)

    async def _snapshot(
        self, uow: OrganizationUnitOfWork, version: OrganizationStructureVersion
    ) -> StructureSnapshot:
        policy = await self._policy_for_version(uow, version)
        return StructureSnapshot(
            version=version,
            units=tuple(await uow.units.list_by_version(version.id, include_inactive=True)),
            relationships=tuple(
                await uow.relationships.list_by_version(version.id, include_inactive=True)
            ),
            staffing_slots=tuple(await uow.staffing.list_by_version(version.id)),
            unit_types=tuple(
                await uow.unit_types.list(version.organization_id, include_inactive=True)
            ),
            relationship_types=tuple(
                await uow.relationship_types.list(version.organization_id, include_inactive=True)
            ),
            position_definitions=tuple(
                await uow.positions.list(
                    version.organization_id,
                    include_inactive=True,
                    offset=0,
                    limit=100_000,
                )
            ),
            policy=policy,
        )

    async def _policy_for_version(
        self, uow: OrganizationUnitOfWork, version: OrganizationStructureVersion
    ) -> OrganizationPolicy:
        policy = await uow.policies.get_for_version(version.id)
        if policy is None:
            policy = await uow.policies.get_default(version.organization_id)
        return policy or OrganizationPolicy(
            id=uuid4(),
            organization_id=version.organization_id,
            structure_version_id=version.id,
            created_by=version.created_by,
        )

    async def _staffing_changed_from_base(
        self,
        uow: OrganizationUnitOfWork,
        version: OrganizationStructureVersion,
    ) -> bool:
        current_slots = tuple(await uow.staffing.list_by_version(version.id))
        if version.based_on_version_id is None:
            return bool(current_slots)
        base_slots = tuple(await uow.staffing.list_by_version(version.based_on_version_id))
        current_units = tuple(await uow.units.list_by_version(version.id, include_inactive=True))
        base_units = tuple(
            await uow.units.list_by_version(version.based_on_version_id, include_inactive=True)
        )
        current_unit_keys = {item.id: item.stable_key for item in current_units}
        base_unit_keys = {item.id: item.stable_key for item in base_units}
        current_slot_keys = {item.id: item.stable_key for item in current_slots}
        base_slot_keys = {item.id: item.stable_key for item in base_slots}
        current_projection = {
            item.stable_key: self._slot_projection(item, current_unit_keys, current_slot_keys)
            for item in current_slots
        }
        base_projection = {
            item.stable_key: self._slot_projection(item, base_unit_keys, base_slot_keys)
            for item in base_slots
        }
        return current_projection != base_projection

    async def _build_structure_view(
        self,
        uow: OrganizationUnitOfWork,
        version: OrganizationStructureVersion,
    ) -> OrganizationStructureView:
        units = tuple(await uow.units.list_by_version(version.id, include_inactive=False))
        relationships = tuple(
            await uow.relationships.list_by_version(version.id, include_inactive=False)
        )
        staffing_slots = tuple(await uow.staffing.list_by_version(version.id))
        return OrganizationStructureView(
            version=version,
            root=self._build_tree(units),
            relationships=relationships,
            staffing_slots=staffing_slots,
        )

    @staticmethod
    def _build_tree(units: Sequence[OrganizationUnit]) -> OrganizationTreeNode | None:
        active_units = tuple(item for item in units if item.active)
        roots = sorted(
            (item for item in active_units if item.parent_unit_id is None),
            key=lambda item: (item.sort_order, item.code, str(item.id)),
        )
        if not roots:
            return None
        children: dict[UUID, list[OrganizationUnit]] = defaultdict(list)
        for unit in active_units:
            if unit.parent_unit_id is not None:
                children[unit.parent_unit_id].append(unit)
        for child_list in children.values():
            child_list.sort(key=lambda item: (item.sort_order, item.code, str(item.id)))

        def make_node(unit: OrganizationUnit, ancestors: frozenset[UUID]) -> OrganizationTreeNode:
            if unit.id in ancestors:
                return OrganizationTreeNode(unit=unit)
            next_ancestors = ancestors | {unit.id}
            return OrganizationTreeNode(
                unit=unit,
                children=tuple(
                    make_node(child, next_ancestors) for child in children.get(unit.id, [])
                ),
            )

        return make_node(roots[0], frozenset())

    async def _clone_version_contents(
        self,
        uow: OrganizationUnitOfWork,
        base: OrganizationStructureVersion,
        target: OrganizationStructureVersion,
        actor: Actor,
    ) -> None:
        base_units = tuple(await uow.units.list_by_version(base.id, include_inactive=True))
        unit_id_map = {unit.id: uuid4() for unit in base_units}
        for unit in base_units:
            cloned_unit = replace(
                unit,
                id=unit_id_map[unit.id],
                structure_version_id=target.id,
                parent_unit_id=(
                    unit_id_map[unit.parent_unit_id] if unit.parent_unit_id is not None else None
                ),
                revision=1,
                custom_fields=dict(unit.custom_fields),
            )
            await uow.units.add(cloned_unit)

        base_relationships = tuple(
            await uow.relationships.list_by_version(base.id, include_inactive=True)
        )
        for relationship in base_relationships:
            source_id = unit_id_map.get(relationship.source_unit_id)
            target_id = unit_id_map.get(relationship.target_unit_id)
            if source_id is None or target_id is None:
                raise VersionConflictError(
                    "The base version contains an external relationship reference.",
                    details={"relationshipId": str(relationship.id)},
                )
            cloned_relationship = replace(
                relationship,
                id=uuid4(),
                structure_version_id=target.id,
                source_unit_id=source_id,
                target_unit_id=target_id,
                revision=1,
                metadata=dict(relationship.metadata),
            )
            await uow.relationships.add(cloned_relationship)

        base_slots = tuple(await uow.staffing.list_by_version(base.id))
        slot_id_map = {slot.id: uuid4() for slot in base_slots}
        for slot in base_slots:
            unit_id = unit_id_map.get(slot.organization_unit_id)
            if unit_id is None:
                raise VersionConflictError(
                    "The base version contains an external staffing unit reference.",
                    details={"staffingSlotId": str(slot.id)},
                )
            reports_to_id = (
                slot_id_map.get(slot.reports_to_slot_id)
                if slot.reports_to_slot_id is not None
                else None
            )
            if slot.reports_to_slot_id is not None and reports_to_id is None:
                raise VersionConflictError(
                    "The base version contains an external staffing reporting reference.",
                    details={"staffingSlotId": str(slot.id)},
                )
            cloned_slot = replace(
                slot,
                id=slot_id_map[slot.id],
                structure_version_id=target.id,
                organization_unit_id=unit_id,
                reports_to_slot_id=reports_to_id,
                revision=1,
                custom_fields=dict(slot.custom_fields),
            )
            await uow.staffing.add(cloned_slot)

        policy = await uow.policies.get_for_version(base.id)
        if policy is None:
            policy = await uow.policies.get_default(base.organization_id)
        cloned_policy = (
            policy.copy_for_version(target.id, actor.user_id)
            if policy is not None
            else OrganizationPolicy(
                id=uuid4(),
                organization_id=target.organization_id,
                structure_version_id=target.id,
                created_by=actor.user_id,
            )
        )
        await uow.policies.add(cloned_policy)

    async def _assert_new_unit_values(
        self,
        uow: OrganizationUnitOfWork,
        version: OrganizationStructureVersion,
        units: Sequence[OrganizationUnit],
        *,
        code: str,
        unit_type_id: UUID,
        parent_unit_id: UUID | None,
    ) -> None:
        normalized = normalized_code(code)
        if any(item.active and item.code.casefold() == normalized.casefold() for item in units):
            raise OrganizationError(
                "VALIDATION_FAILED",
                "Unit codes must be unique inside a structure version.",
                details={"field": "code", "code": normalized},
            )
        unit_type = await uow.unit_types.get(unit_type_id)
        if (
            unit_type is None
            or not unit_type.active
            or unit_type.organization_id != version.organization_id
        ):
            raise ResourceNotFoundError("organizationUnitType", unit_type_id)
        if parent_unit_id is None:
            root = next(
                (item for item in units if item.active and item.parent_unit_id is None), None
            )
            if root is not None:
                raise MultipleRootsError(existing_root_id=root.id)
            return
        parent = next((item for item in units if item.id == parent_unit_id), None)
        if parent is None or not parent.active or parent.structure_version_id != version.id:
            raise ResourceNotFoundError("parentOrganizationUnit", parent_unit_id)
        await self._assert_configured_parent_type(
            uow,
            unit_type_id=unit_type.id,
            parent_unit_id=parent.id,
            units=units,
        )

    @staticmethod
    async def _assert_configured_parent_type(
        uow: OrganizationUnitOfWork,
        *,
        unit_type_id: UUID,
        parent_unit_id: UUID | None,
        units: Sequence[OrganizationUnit],
    ) -> None:
        if parent_unit_id is None:
            return
        unit_type = await uow.unit_types.get(unit_type_id)
        parent = next((item for item in units if item.id == parent_unit_id), None)
        if unit_type is None:
            raise ResourceNotFoundError("organizationUnitType", unit_type_id)
        if parent is None:
            raise ResourceNotFoundError("parentOrganizationUnit", parent_unit_id)
        if (
            unit_type.allowed_parent_type_ids
            and parent.unit_type_id not in unit_type.allowed_parent_type_ids
        ):
            raise OrganizationError(
                "VALIDATION_FAILED",
                "The configured unit type does not allow this parent type.",
                details={
                    "unitTypeId": str(unit_type.id),
                    "parentUnitTypeId": str(parent.unit_type_id),
                },
            )

    @staticmethod
    def _assert_valid_move(
        unit: OrganizationUnit,
        parent_unit_id: UUID | None,
        units: Sequence[OrganizationUnit],
    ) -> None:
        if parent_unit_id == unit.id:
            raise StructureCycleError(unit_id=unit.id)
        by_id = {item.id: item for item in units}
        if parent_unit_id is None:
            root = next(
                (
                    item
                    for item in units
                    if item.active and item.parent_unit_id is None and item.id != unit.id
                ),
                None,
            )
            if root is not None:
                raise MultipleRootsError(existing_root_id=root.id)
            return
        parent = by_id.get(parent_unit_id)
        if (
            parent is None
            or not parent.active
            or parent.structure_version_id != unit.structure_version_id
        ):
            raise ResourceNotFoundError("parentOrganizationUnit", parent_unit_id)
        seen: set[UUID] = set()
        current: OrganizationUnit | None = parent
        while current is not None:
            if current.id == unit.id:
                raise StructureCycleError(unit_id=unit.id)
            if current.id in seen:
                raise StructureCycleError(unit_id=current.id)
            seen.add(current.id)
            current = by_id.get(current.parent_unit_id) if current.parent_unit_id else None

    async def _assert_relationship_valid(
        self,
        uow: OrganizationUnitOfWork,
        version: OrganizationStructureVersion,
        candidate: OrganizationRelationship,
        *,
        exclude_relationship_id: UUID | None = None,
    ) -> None:
        if not candidate.active:
            return
        relationship_type = await uow.relationship_types.get(candidate.relationship_type_id)
        if (
            relationship_type is None
            or not relationship_type.active
            or relationship_type.organization_id != version.organization_id
        ):
            raise ResourceNotFoundError(
                "organizationRelationshipType", candidate.relationship_type_id
            )
        source = await self._require_unit_in_version(uow, candidate.source_unit_id, version.id)
        target = await self._require_unit_in_version(uow, candidate.target_unit_id, version.id)
        if not source.active or not target.active:
            raise InvalidRelationshipError(
                "Relationship endpoints must be active organization units."
            )
        candidate.ensure_not_self_link(relationship_type)
        validate_date_range(candidate.effective_from, candidate.effective_to)
        self._validate_custom_fields(
            candidate.metadata, relationship_type.metadata_schema, path="metadata"
        )
        relationships = tuple(
            await uow.relationships.list_by_version(version.id, include_inactive=False)
        )
        if any(
            item.id != exclude_relationship_id
            and item.relationship_type_id == candidate.relationship_type_id
            and item.source_unit_id == candidate.source_unit_id
            and item.target_unit_id == candidate.target_unit_id
            and item.effective_from == candidate.effective_from
            and item.effective_to == candidate.effective_to
            for item in relationships
        ):
            raise InvalidRelationshipError("Duplicate active relationships are not allowed.")
        if relationship_type.prevents_cycles:
            adjacency: dict[UUID, list[UUID]] = defaultdict(list)
            for item in relationships:
                if (
                    item.id != exclude_relationship_id
                    and item.relationship_type_id == relationship_type.id
                    and item.active
                ):
                    adjacency[item.source_unit_id].append(item.target_unit_id)
            if self._path_exists(adjacency, candidate.target_unit_id, candidate.source_unit_id):
                raise InvalidRelationshipError(
                    "The configured relationship type prohibits cycles.",
                    details={"relationshipTypeId": str(relationship_type.id)},
                )
        policy = await self._policy_for_version(uow, version)
        if not policy.allow_cross_unit_relationships:
            units = tuple(await uow.units.list_by_version(version.id, include_inactive=False))
            by_id = {item.id: item for item in units}
            if self._top_branch(source.id, by_id) != self._top_branch(target.id, by_id):
                raise InvalidRelationshipError(
                    "Cross-unit relationships are disabled by organization policy."
                )

    async def _assert_staffing_slot_valid(
        self,
        uow: OrganizationUnitOfWork,
        version: OrganizationStructureVersion,
        candidate: StaffingSlot,
        *,
        exclude_slot_id: UUID | None = None,
    ) -> None:
        candidate.validate_fte()
        validate_date_range(candidate.effective_from, candidate.effective_to)
        if candidate.status in {StaffingSlotStatus.CLOSING, StaffingSlotStatus.CLOSED}:
            raise StaffingSlotNotAvailableError(candidate.id, candidate.status.value)
        self._validate_custom_fields(candidate.custom_fields, {}, path="customFields")
        unit = await self._require_unit_in_version(uow, candidate.organization_unit_id, version.id)
        if not unit.active:
            raise StaffingSlotNotAvailableError(candidate.id, candidate.status.value)
        position = await uow.positions.get(candidate.position_definition_id)
        if (
            position is None
            or not position.active
            or position.organization_id != version.organization_id
        ):
            raise ResourceNotFoundError("positionDefinition", candidate.position_definition_id)
        slots = tuple(await uow.staffing.list_by_version(version.id))
        active_slots = tuple(
            item
            for item in slots
            if item.id != exclude_slot_id
            and item.status not in {StaffingSlotStatus.CLOSED, StaffingSlotStatus.CLOSING}
        )
        if candidate.reports_to_slot_id is not None:
            manager = next(
                (item for item in slots if item.id == candidate.reports_to_slot_id), None
            )
            if manager is None or manager.structure_version_id != version.id:
                raise ResourceNotFoundError("reportingStaffingSlot", candidate.reports_to_slot_id)
            if manager.status in {StaffingSlotStatus.CLOSING, StaffingSlotStatus.CLOSED}:
                raise StaffingSlotNotAvailableError(manager.id, manager.status.value)
            reports_to = {
                item.id: item.reports_to_slot_id
                for item in active_slots
                if item.reports_to_slot_id is not None
            }
            current: UUID | None = candidate.reports_to_slot_id
            seen: set[UUID] = set()
            while current is not None:
                if current == candidate.id:
                    raise StructureCycleError(unit_id=candidate.organization_unit_id)
                if current in seen:
                    raise StructureCycleError(unit_id=candidate.organization_unit_id)
                seen.add(current)
                current = reports_to.get(current)
        policy = await self._policy_for_version(uow, version)
        if (
            candidate.head_of_unit
            and not policy.allow_multiple_unit_heads
            and any(
                item.head_of_unit and item.organization_unit_id == candidate.organization_unit_id
                for item in active_slots
            )
        ):
            raise OrganizationError(
                "VALIDATION_FAILED",
                "The organization unit already has an active head staffing slot.",
                details={"organizationUnitId": str(candidate.organization_unit_id)},
            )

    @staticmethod
    def _path_exists(adjacency: Mapping[UUID, Sequence[UUID]], start: UUID, goal: UUID) -> bool:
        stack = [start]
        seen: set[UUID] = set()
        while stack:
            current = stack.pop()
            if current == goal:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(adjacency.get(current, ()))
        return False

    @staticmethod
    def _top_branch(unit_id: UUID, units: Mapping[UUID, OrganizationUnit]) -> UUID:
        current = units[unit_id]
        seen: set[UUID] = set()
        while current.parent_unit_id is not None and current.parent_unit_id in units:
            if current.id in seen:
                return current.id
            seen.add(current.id)
            parent = units[current.parent_unit_id]
            if parent.parent_unit_id is None:
                return current.id
            current = parent
        return current.id

    @staticmethod
    async def _require_version(
        uow: OrganizationUnitOfWork, version_id: UUID
    ) -> OrganizationStructureVersion:
        version = await uow.versions.get(version_id)
        if version is None:
            raise ResourceNotFoundError("organizationStructureVersion", version_id)
        return version

    async def _require_editable_version(
        self, uow: OrganizationUnitOfWork, version_id: UUID
    ) -> OrganizationStructureVersion:
        version = await self._require_version(uow, version_id)
        version.ensure_editable()
        return version

    @staticmethod
    async def _require_unit_in_version(
        uow: OrganizationUnitOfWork, unit_id: UUID, version_id: UUID
    ) -> OrganizationUnit:
        unit = await uow.units.get(unit_id)
        if unit is None or unit.structure_version_id != version_id:
            raise ResourceNotFoundError("organizationUnit", unit_id)
        return unit

    @staticmethod
    async def _require_relationship_in_version(
        uow: OrganizationUnitOfWork, relationship_id: UUID, version_id: UUID
    ) -> OrganizationRelationship:
        relationship = await uow.relationships.get(relationship_id)
        if relationship is None or relationship.structure_version_id != version_id:
            raise ResourceNotFoundError("organizationRelationship", relationship_id)
        return relationship

    def _compare(
        self,
        from_version_id: UUID,
        to_version_id: UUID,
        from_units: tuple[OrganizationUnit, ...],
        to_units: tuple[OrganizationUnit, ...],
        from_relationships: tuple[OrganizationRelationship, ...],
        to_relationships: tuple[OrganizationRelationship, ...],
        from_slots: tuple[StaffingSlot, ...],
        to_slots: tuple[StaffingSlot, ...],
    ) -> VersionComparison:
        from_unit_by_key = {item.stable_key: item for item in from_units}
        to_unit_by_key = {item.stable_key: item for item in to_units}
        added_unit_keys = to_unit_by_key.keys() - from_unit_by_key.keys()
        removed_unit_keys = from_unit_by_key.keys() - to_unit_by_key.keys()
        changed_units: list[dict[str, Any]] = []
        for stable_key in sorted(from_unit_by_key.keys() & to_unit_by_key.keys(), key=str):
            unit_before = from_unit_by_key[stable_key]
            unit_after = to_unit_by_key[stable_key]
            before_projection = self._unit_projection(unit_before, from_unit_by_key)
            after_projection = self._unit_projection(unit_after, to_unit_by_key)
            if before_projection != after_projection:
                changed_units.append(
                    {
                        "stableKey": str(stable_key),
                        "before": before_projection,
                        "after": after_projection,
                    }
                )

        from_unit_stable = {item.id: item.stable_key for item in from_units}
        to_unit_stable = {item.id: item.stable_key for item in to_units}

        def relationship_key(
            item: OrganizationRelationship, unit_stable: Mapping[UUID, UUID]
        ) -> tuple[Any, ...]:
            return (
                item.relationship_type_id,
                unit_stable.get(item.source_unit_id),
                unit_stable.get(item.target_unit_id),
                item.effective_from,
                item.effective_to,
                item.active,
                self._freeze_json(item.metadata),
            )

        from_relationship_by_key = {
            relationship_key(item, from_unit_stable): item for item in from_relationships
        }
        to_relationship_by_key = {
            relationship_key(item, to_unit_stable): item for item in to_relationships
        }
        added_relationship_keys = to_relationship_by_key.keys() - from_relationship_by_key.keys()
        removed_relationship_keys = from_relationship_by_key.keys() - to_relationship_by_key.keys()

        from_slot_by_key = {item.stable_key: item for item in from_slots}
        to_slot_by_key = {item.stable_key: item for item in to_slots}
        added_slot_keys = to_slot_by_key.keys() - from_slot_by_key.keys()
        removed_slot_keys = from_slot_by_key.keys() - to_slot_by_key.keys()
        from_slot_stable = {item.id: item.stable_key for item in from_slots}
        to_slot_stable = {item.id: item.stable_key for item in to_slots}
        changed_slots: list[dict[str, Any]] = []
        for stable_key in sorted(from_slot_by_key.keys() & to_slot_by_key.keys(), key=str):
            slot_before = from_slot_by_key[stable_key]
            slot_after = to_slot_by_key[stable_key]
            before_projection = self._slot_projection(
                slot_before, from_unit_stable, from_slot_stable
            )
            after_projection = self._slot_projection(slot_after, to_unit_stable, to_slot_stable)
            if before_projection != after_projection:
                changed_slots.append(
                    {
                        "stableKey": str(stable_key),
                        "before": before_projection,
                        "after": after_projection,
                    }
                )
        return VersionComparison(
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            added_units=tuple(to_unit_by_key[item] for item in sorted(added_unit_keys, key=str)),
            removed_units=tuple(
                from_unit_by_key[item] for item in sorted(removed_unit_keys, key=str)
            ),
            changed_units=tuple(changed_units),
            added_relationships=tuple(
                to_relationship_by_key[item] for item in sorted(added_relationship_keys, key=str)
            ),
            removed_relationships=tuple(
                from_relationship_by_key[item]
                for item in sorted(removed_relationship_keys, key=str)
            ),
            added_staffing_slots=tuple(
                to_slot_by_key[item] for item in sorted(added_slot_keys, key=str)
            ),
            removed_staffing_slots=tuple(
                from_slot_by_key[item] for item in sorted(removed_slot_keys, key=str)
            ),
            changed_staffing_slots=tuple(changed_slots),
        )

    @staticmethod
    def _unit_projection(
        unit: OrganizationUnit, unit_by_key: Mapping[UUID, OrganizationUnit]
    ) -> dict[str, Any]:
        id_to_key = {item.id: item.stable_key for item in unit_by_key.values()}
        return {
            "code": unit.code,
            "name": unit.name,
            "shortName": unit.short_name,
            "unitTypeId": str(unit.unit_type_id),
            "parentStableKey": (
                str(id_to_key.get(unit.parent_unit_id)) if unit.parent_unit_id else None
            ),
            "sortOrder": unit.sort_order,
            "description": unit.description,
            "active": unit.active,
            "customFields": unit.custom_fields,
        }

    @staticmethod
    def _slot_projection(
        slot: StaffingSlot,
        unit_stable: Mapping[UUID, UUID],
        slot_stable: Mapping[UUID, UUID],
    ) -> dict[str, Any]:
        return {
            "organizationUnitStableKey": str(unit_stable.get(slot.organization_unit_id)),
            "positionDefinitionId": str(slot.position_definition_id),
            "reportsToStableKey": (
                str(slot_stable.get(slot.reports_to_slot_id)) if slot.reports_to_slot_id else None
            ),
            "headOfUnit": slot.head_of_unit,
            "fullTimeEquivalent": str(slot.full_time_equivalent),
            "employmentType": slot.employment_type.value,
            "status": slot.status.value,
            "effectiveFrom": (slot.effective_from.isoformat() if slot.effective_from else None),
            "effectiveTo": slot.effective_to.isoformat() if slot.effective_to else None,
            "customFields": slot.custom_fields,
        }

    @staticmethod
    def _freeze_json(value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(
                sorted(
                    (str(key), OrganizationService._freeze_json(item))
                    for key, item in value.items()
                )
            )
        if isinstance(value, list):
            return tuple(OrganizationService._freeze_json(item) for item in value)
        return value

    async def _audit(
        self,
        uow: OrganizationUnitOfWork,
        actor: Actor,
        organization_id: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        *,
        before: Any,
        after: Any,
        reason: str | None = None,
    ) -> None:
        await uow.audit.add(
            AuditRecord(
                id=uuid4(),
                organization_id=organization_id,
                actor_id=actor.user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                before=self._safe_state(before) if before is not None else None,
                after=self._safe_state(after) if after is not None else None,
                reason=reason,
                request_id=actor.request_id,
                occurred_at=utc_now(),
            )
        )

    async def _event(
        self,
        uow: OrganizationUnitOfWork,
        organization_id: UUID,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        await uow.outbox.add(
            OutboxRecord(
                id=uuid4(),
                organization_id=organization_id,
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=self._safe_state(payload),
                occurred_at=utc_now(),
            )
        )

    @classmethod
    def _safe_state(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if is_dataclass(value) and not isinstance(value, type):
            return {item.name: cls._safe_state(getattr(value, item.name)) for item in fields(value)}
        if isinstance(value, Mapping):
            return {str(key): cls._safe_state(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set, frozenset)):
            return [cls._safe_state(item) for item in value]
        return str(value)

    @staticmethod
    def _as_uuid(value: Any, field_name: str) -> UUID:
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (TypeError, ValueError) as exc:
            raise OrganizationError(
                "VALIDATION_FAILED",
                f"{field_name} must be a UUID.",
                details={"field": field_name},
            ) from exc

    @staticmethod
    def _as_date_or_none(value: Any, field_name: str) -> date | None:
        if value is None or isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError) as exc:
            raise OrganizationError(
                "VALIDATION_FAILED",
                f"{field_name} must be an ISO date.",
                details={"field": field_name},
            ) from exc

    @staticmethod
    def _validate_custom_fields(
        value: Mapping[str, Any], schema: Mapping[str, Any], *, path: str
    ) -> None:
        try:
            validate_json_object(value, schema, path=path)
        except CustomFieldValidationError as exc:
            raise OrganizationError(
                "VALIDATION_FAILED",
                "Extension fields do not conform to their configured schema.",
                details={"issues": list(exc.issues)},
            ) from exc
