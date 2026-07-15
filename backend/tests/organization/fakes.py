"""In-memory organization ports with realistic filtering and revision checks."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.modules.organization.application.service import OrganizationService
from app.modules.organization.domain.entities import (
    Organization,
    OrganizationPolicy,
    OrganizationRelationship,
    OrganizationRelationshipType,
    OrganizationStructureVersion,
    OrganizationUnit,
    OrganizationUnitType,
    PositionDefinition,
    RevisionedEntity,
    StaffingSlot,
    StructureReviewRequest,
)
from app.modules.organization.domain.enums import (
    EmploymentType,
    StaffingSlotStatus,
    StructureVersionStatus,
)
from app.modules.organization.domain.errors import ConcurrencyConflictError, PermissionDeniedError
from app.modules.organization.domain.ports import Actor, AuditRecord, OutboxRecord
from app.modules.organization.domain.validation import ValidationIssue


class RevisionedStore[RevisionedT: RevisionedEntity]:
    """Keeps the persisted revision apart from the mutable entity instance."""

    entity_name = "entity"

    def __init__(self) -> None:
        self.items: dict[UUID, RevisionedT] = {}
        self.persisted_revisions: dict[UUID, int] = {}
        self.save_calls: list[tuple[UUID, int]] = []

    def seed(self, item: RevisionedT) -> RevisionedT:
        self.items[item.id] = item
        self.persisted_revisions[item.id] = item.revision
        return item

    async def get(self, item_id: UUID) -> RevisionedT | None:
        return self.items.get(item_id)

    async def add(self, item: RevisionedT) -> None:
        self.seed(item)

    async def save(self, item: RevisionedT, *, expected_revision: int) -> None:
        persisted_revision = self.persisted_revisions.get(item.id)
        if persisted_revision != expected_revision:
            raise ConcurrencyConflictError(self.entity_name, item.id, expected_revision)
        self.items[item.id] = item
        self.persisted_revisions[item.id] = item.revision
        self.save_calls.append((item.id, expected_revision))


class OrganizationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Organization] = {}

    def seed(self, item: Organization) -> Organization:
        self.items[item.id] = item
        return item

    async def get(self, organization_id: UUID) -> Organization | None:
        return self.items.get(organization_id)

    async def list(self) -> Sequence[Organization]:
        return tuple(self.items.values())

    async def add(self, organization: Organization) -> None:
        self.seed(organization)


class VersionRepository(RevisionedStore[OrganizationStructureVersion]):
    entity_name = "organizationStructureVersion"

    async def list(
        self,
        organization_id: UUID,
        *,
        status: StructureVersionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
        sort: str = "-versionNumber",
    ) -> Sequence[OrganizationStructureVersion]:
        items = [
            item
            for item in self.items.values()
            if item.organization_id == organization_id and (status is None or item.status is status)
        ]
        attribute = {"versionNumber": "version_number", "createdAt": "created_at"}[
            sort.removeprefix("-")
        ]
        items.sort(key=lambda item: str(item.id))
        items.sort(key=lambda item: getattr(item, attribute), reverse=sort.startswith("-"))
        return tuple(items[offset : offset + limit])

    async def count(
        self, organization_id: UUID, *, status: StructureVersionStatus | None = None
    ) -> int:
        return len(await self.list(organization_id, status=status, offset=0, limit=100_000))

    async def get_active(
        self, organization_id: UUID, *, on_date: date
    ) -> OrganizationStructureVersion | None:
        candidates = [
            item
            for item in self.items.values()
            if item.organization_id == organization_id
            and item.status is StructureVersionStatus.PUBLISHED
            and (item.effective_from is None or item.effective_from <= on_date)
            and (item.effective_to is None or item.effective_to >= on_date)
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (item.effective_from or date.min, item.version_number),
        )

    async def next_version_number(self, organization_id: UUID) -> int:
        numbers = [
            item.version_number
            for item in self.items.values()
            if item.organization_id == organization_id
        ]
        return max(numbers, default=0) + 1


class UnitTypeRepository(RevisionedStore[OrganizationUnitType]):
    entity_name = "organizationUnitType"

    async def list(
        self, organization_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationUnitType]:
        return tuple(
            item
            for item in self.items.values()
            if item.organization_id == organization_id and (include_inactive or item.active)
        )


class RelationshipTypeRepository(RevisionedStore[OrganizationRelationshipType]):
    entity_name = "organizationRelationshipType"

    async def list(
        self, organization_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationRelationshipType]:
        return tuple(
            item
            for item in self.items.values()
            if item.organization_id == organization_id and (include_inactive or item.active)
        )


class PolicyRepository(RevisionedStore[OrganizationPolicy]):
    entity_name = "organizationPolicy"

    async def get_for_version(self, version_id: UUID) -> OrganizationPolicy | None:
        return next(
            (item for item in self.items.values() if item.structure_version_id == version_id),
            None,
        )

    async def get_default(self, organization_id: UUID) -> OrganizationPolicy | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.organization_id == organization_id and item.structure_version_id is None
            ),
            None,
        )


class ReviewRequestRepository(RevisionedStore[StructureReviewRequest]):
    entity_name = "structureReviewRequest"

    async def get_pending_for_version(self, version_id: UUID) -> StructureReviewRequest | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.structure_version_id == version_id and item.status.value == "pending"
            ),
            None,
        )

    async def list_for_version(self, version_id: UUID) -> Sequence[StructureReviewRequest]:
        return tuple(
            item for item in self.items.values() if item.structure_version_id == version_id
        )


class UnitRepository(RevisionedStore[OrganizationUnit]):
    entity_name = "organizationUnit"

    async def list_by_version(
        self, version_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationUnit]:
        items = [
            item
            for item in self.items.values()
            if item.structure_version_id == version_id and (include_inactive or item.active)
        ]
        items.sort(key=lambda item: (item.sort_order, item.code, str(item.id)))
        return tuple(items)


class RelationshipRepository(RevisionedStore[OrganizationRelationship]):
    entity_name = "organizationRelationship"

    async def list_by_version(
        self, version_id: UUID, *, include_inactive: bool = False
    ) -> Sequence[OrganizationRelationship]:
        return tuple(
            item
            for item in self.items.values()
            if item.structure_version_id == version_id and (include_inactive or item.active)
        )


class PositionRepository(RevisionedStore[PositionDefinition]):
    entity_name = "positionDefinition"

    async def list(
        self,
        organization_id: UUID,
        *,
        include_inactive: bool = False,
        offset: int = 0,
        limit: int = 100,
        sort: str = "name",
    ) -> Sequence[PositionDefinition]:
        items = [
            item
            for item in self.items.values()
            if item.organization_id == organization_id and (include_inactive or item.active)
        ]
        attribute = {"code": "code", "name": "name", "createdAt": "created_at"}[
            sort.removeprefix("-")
        ]
        items.sort(key=lambda item: str(item.id))
        items.sort(key=lambda item: getattr(item, attribute), reverse=sort.startswith("-"))
        return tuple(items[offset : offset + limit])

    async def count(self, organization_id: UUID, *, include_inactive: bool = False) -> int:
        return len(
            await self.list(
                organization_id, include_inactive=include_inactive, offset=0, limit=100_000
            )
        )


class StaffingRepository(RevisionedStore[StaffingSlot]):
    entity_name = "staffingSlot"

    def __init__(self, versions: VersionRepository) -> None:
        super().__init__()
        self._versions = versions

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
        version_ids = {
            item.id
            for item in self._versions.items.values()
            if item.organization_id == organization_id
        }
        items = [
            item
            for item in self.items.values()
            if item.structure_version_id in version_ids
            and (version_id is None or item.structure_version_id == version_id)
            and (unit_id is None or item.organization_unit_id == unit_id)
            and (status is None or item.effective_status() is status)
        ]
        attribute = {
            "organizationUnitId": "organization_unit_id",
            "status": "status",
            "fullTimeEquivalent": "full_time_equivalent",
        }[sort.removeprefix("-")]
        items.sort(key=lambda item: str(item.id))
        items.sort(
            key=lambda item: (
                getattr(item, attribute).value
                if attribute == "status"
                else str(getattr(item, attribute))
                if attribute == "organization_unit_id"
                else getattr(item, attribute)
            ),
            reverse=sort.startswith("-"),
        )
        return tuple(items[offset : offset + limit])

    async def count(
        self,
        organization_id: UUID,
        *,
        version_id: UUID | None = None,
        unit_id: UUID | None = None,
        status: StaffingSlotStatus | None = None,
    ) -> int:
        return len(
            await self.list(
                organization_id,
                version_id=version_id,
                unit_id=unit_id,
                status=status,
                offset=0,
                limit=100_000,
            )
        )

    async def list_by_version(self, version_id: UUID) -> Sequence[StaffingSlot]:
        return tuple(
            item for item in self.items.values() if item.structure_version_id == version_id
        )


class Sink[SinkT]:
    def __init__(self) -> None:
        self.items: list[SinkT] = []

    async def add(self, item: SinkT) -> None:
        self.items.append(item)


class FakeOrganizationUnitOfWork:
    def __init__(self) -> None:
        self.organizations = OrganizationRepository()
        self.versions = VersionRepository()
        self.unit_types = UnitTypeRepository()
        self.relationship_types = RelationshipTypeRepository()
        self.policies = PolicyRepository()
        self.review_requests = ReviewRequestRepository()
        self.units = UnitRepository()
        self.relationships = RelationshipRepository()
        self.positions = PositionRepository()
        self.staffing = StaffingRepository(self.versions)
        self.audit: Sink[AuditRecord] = Sink()
        self.outbox: Sink[OutboxRecord] = Sink()
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self._snapshot: dict[str, Any] | None = None

    async def __aenter__(self) -> FakeOrganizationUnitOfWork:
        revisioned_repositories = (
            self.versions,
            self.unit_types,
            self.relationship_types,
            self.policies,
            self.review_requests,
            self.units,
            self.relationships,
            self.positions,
            self.staffing,
        )
        self._snapshot = {
            "organizations": deepcopy(self.organizations.items),
            "revisioned": [
                (
                    deepcopy(repository.items),
                    dict(repository.persisted_revisions),
                    list(repository.save_calls),
                )
                for repository in revisioned_repositories
            ],
            "audit": list(self.audit.items),
            "outbox": list(self.outbox.items),
        }
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, _exc: BaseException | None, _traceback: Any
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1
        if self._snapshot is None:
            return
        self.organizations.items = self._snapshot["organizations"]
        revisioned_repositories = (
            self.versions,
            self.unit_types,
            self.relationship_types,
            self.policies,
            self.review_requests,
            self.units,
            self.relationships,
            self.positions,
            self.staffing,
        )
        for repository, state in zip(
            revisioned_repositories, self._snapshot["revisioned"], strict=True
        ):
            repository.items, repository.persisted_revisions, repository.save_calls = state
        self.audit.items = self._snapshot["audit"]
        self.outbox.items = self._snapshot["outbox"]

    def __call__(self) -> FakeOrganizationUnitOfWork:
        return self


@dataclass(frozen=True, slots=True)
class AuthorizationCall:
    actor: Actor
    permission: str
    organization_id: UUID
    unit_id: UUID | None


class RecordingAuthorizer:
    def __init__(self, *, deny_organization_wide: frozenset[str] = frozenset()) -> None:
        self.calls: list[AuthorizationCall] = []
        self.deny_organization_wide = deny_organization_wide

    async def require(
        self,
        actor: Actor,
        permission: str,
        organization_id: UUID,
        *,
        unit_id: UUID | None = None,
    ) -> None:
        self.calls.append(AuthorizationCall(actor, permission, organization_id, unit_id))
        if unit_id is None and permission in self.deny_organization_wide:
            raise PermissionDeniedError(permission)


class StubExternalValidator:
    def __init__(self, issues: Sequence[ValidationIssue] = ()) -> None:
        self.issues = tuple(issues)
        self.version_ids: list[UUID] = []
        self.effective_dates: list[date | None] = []

    async def validate_structure_version(
        self, version_id: UUID, *, effective_from: date | None = None
    ) -> Sequence[ValidationIssue]:
        self.version_ids.append(version_id)
        self.effective_dates.append(effective_from)
        return self.issues


@dataclass(slots=True)
class OrganizationScenario:
    organization: Organization
    actor: Actor
    uow: FakeOrganizationUnitOfWork
    authorizer: RecordingAuthorizer
    service: OrganizationService

    def add_version(
        self,
        *,
        status: StructureVersionStatus = StructureVersionStatus.DRAFT,
        name: str = "Working structure",
        based_on: OrganizationStructureVersion | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
    ) -> OrganizationStructureVersion:
        version = OrganizationStructureVersion(
            id=uuid4(),
            organization_id=self.organization.id,
            version_number=max(
                (
                    item.version_number
                    for item in self.uow.versions.items.values()
                    if item.organization_id == self.organization.id
                ),
                default=0,
            )
            + 1,
            name=name,
            status=status,
            based_on_version_id=based_on.id if based_on is not None else None,
            effective_from=effective_from,
            effective_to=effective_to,
            created_by=self.actor.user_id,
            published_by=(
                self.actor.user_id if status is StructureVersionStatus.PUBLISHED else None
            ),
        )
        return self.uow.versions.seed(version)

    def add_unit_type(
        self,
        *,
        code: str = "DEPARTMENT",
        name: str = "Department",
        allowed_parent_type_ids: tuple[UUID, ...] = (),
        active: bool = True,
    ) -> OrganizationUnitType:
        unit_type = OrganizationUnitType(
            id=uuid4(),
            organization_id=self.organization.id,
            code=code,
            name=name,
            allowed_parent_type_ids=allowed_parent_type_ids,
            active=active,
        )
        return self.uow.unit_types.seed(unit_type)

    def add_unit(
        self,
        version: OrganizationStructureVersion,
        unit_type: OrganizationUnitType,
        *,
        code: str,
        name: str | None = None,
        parent: OrganizationUnit | None = None,
        sort_order: int = 0,
        stable_key: UUID | None = None,
        active: bool = True,
        custom_fields: dict[str, Any] | None = None,
    ) -> OrganizationUnit:
        unit = OrganizationUnit(
            id=uuid4(),
            structure_version_id=version.id,
            stable_key=stable_key or uuid4(),
            code=code,
            name=name or code.title(),
            unit_type_id=unit_type.id,
            parent_unit_id=parent.id if parent is not None else None,
            sort_order=sort_order,
            active=active,
            custom_fields=dict(custom_fields or {}),
        )
        return self.uow.units.seed(unit)

    def add_policy(
        self,
        version: OrganizationStructureVersion | None,
        **changes: bool,
    ) -> OrganizationPolicy:
        policy = OrganizationPolicy(
            id=uuid4(),
            organization_id=self.organization.id,
            structure_version_id=version.id if version is not None else None,
            created_by=self.actor.user_id,
        )
        for field_name, value in changes.items():
            setattr(policy, field_name, value)
        return self.uow.policies.seed(policy)

    def add_relationship_type(
        self,
        *,
        code: str = "DOTTED_LINE",
        prevents_cycles: bool = True,
        allow_self_link: bool = False,
    ) -> OrganizationRelationshipType:
        relationship_type = OrganizationRelationshipType(
            id=uuid4(),
            organization_id=self.organization.id,
            code=code,
            name=code.replace("_", " ").title(),
            prevents_cycles=prevents_cycles,
            allow_self_link=allow_self_link,
        )
        return self.uow.relationship_types.seed(relationship_type)

    def add_position(self, *, code: str = "MANAGER") -> PositionDefinition:
        position = PositionDefinition(
            id=uuid4(),
            organization_id=self.organization.id,
            code=code,
            name=code.replace("_", " ").title(),
        )
        return self.uow.positions.seed(position)

    def add_slot(
        self,
        version: OrganizationStructureVersion,
        unit: OrganizationUnit,
        position: PositionDefinition,
        *,
        reports_to: StaffingSlot | None = None,
        head_of_unit: bool = False,
        stable_key: UUID | None = None,
        status: StaffingSlotStatus = StaffingSlotStatus.PLANNED,
        custom_fields: dict[str, Any] | None = None,
    ) -> StaffingSlot:
        slot = StaffingSlot(
            id=uuid4(),
            structure_version_id=version.id,
            stable_key=stable_key or uuid4(),
            organization_unit_id=unit.id,
            position_definition_id=position.id,
            reports_to_slot_id=reports_to.id if reports_to is not None else None,
            head_of_unit=head_of_unit,
            full_time_equivalent=Decimal("1"),
            employment_type=EmploymentType.PERMANENT,
            status=status,
            custom_fields=dict(custom_fields or {}),
        )
        return self.uow.staffing.seed(slot)

    def add_valid_draft(
        self, **policy_changes: bool
    ) -> tuple[
        OrganizationStructureVersion,
        OrganizationUnitType,
        OrganizationUnit,
        OrganizationPolicy,
    ]:
        version = self.add_version()
        unit_type = self.add_unit_type()
        root = self.add_unit(version, unit_type, code="ROOT", name="Corporate Center")
        policy_values = {
            "structure_publish_requires_review": False,
            "staffing_changes_require_finance_review": False,
            **policy_changes,
        }
        policy = self.add_policy(version, **policy_values)
        return version, unit_type, root, policy
