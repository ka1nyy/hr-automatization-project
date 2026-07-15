"""Ports required by employee use cases."""

from __future__ import annotations

import builtins
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from types import TracebackType
from typing import Any, Protocol, Self
from uuid import UUID

from ..domain.entities import (
    AssignmentReviewRequest,
    Delegation,
    Employee,
    EmployeeAssignment,
    Person,
)


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: UUID
    organization_id: UUID
    permissions: frozenset[str]
    employee_id: UUID | None = None
    accessible_unit_ids: frozenset[UUID] = field(default_factory=frozenset)
    organization_wide: bool = False
    organization_wide_permissions: frozenset[str] = field(default_factory=frozenset)
    permission_unit_ids: Mapping[str, frozenset[UUID]] = field(default_factory=dict)
    permission_unit_stable_keys: Mapping[str, frozenset[UUID]] = field(default_factory=dict)
    self_permissions: frozenset[str] = field(default_factory=frozenset)

    def allows(self, permission: str, unit_id: UUID | None = None) -> bool:
        if "*" in self.permissions:
            return True
        if permission not in self.permissions:
            return False
        if self.organization_wide or permission in self.organization_wide_permissions:
            return True
        if unit_id is None:
            return False
        explicit = self.permission_unit_ids.get(permission)
        if explicit is not None:
            return unit_id in explicit
        return unit_id in self.accessible_unit_ids

    def allows_self(self, permission: str, employee_id: UUID) -> bool:
        return (
            self.employee_id == employee_id
            and permission in self.self_permissions
            and permission in self.permissions
        )

    def unit_ids_for(self, permission: str) -> frozenset[UUID]:
        return self.permission_unit_ids.get(permission, self.accessible_unit_ids)

    def allows_unit(self, permission: str, unit_id: UUID, unit_stable_key: UUID | None) -> bool:
        if self.allows(permission):
            return True
        if self.allows(permission, unit_id):
            return True
        return (
            unit_stable_key is not None
            and unit_stable_key in self.permission_unit_stable_keys.get(permission, frozenset())
        )


@dataclass(frozen=True, slots=True)
class EmployeePolicySnapshot:
    managers_can_create_employee_drafts: bool = False
    managers_can_assign_existing_employees: bool = False
    manager_changes_require_hr_approval: bool = True


@dataclass(frozen=True, slots=True)
class StaffingSlotSnapshot:
    id: UUID
    organization_id: UUID
    organization_unit_id: UUID
    structure_version_id: UUID
    full_time_equivalent: Decimal
    status: str
    effective_from: date
    effective_to: date | None
    organization_unit_stable_key: UUID | None = None
    structure_status: str = "published"
    structure_effective_from: date | None = date.min
    structure_effective_to: date | None = None


@dataclass(frozen=True, slots=True)
class AuditEntry:
    actor_id: UUID
    action: str
    entity_type: str
    entity_id: UUID
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str | None = None
    organization_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class PendingEvent:
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    payload: dict[str, Any]


class PersonRepository(Protocol):
    async def get(self, person_id: UUID) -> Person | None: ...
    async def add(self, person: Person) -> None: ...
    async def update(self, person: Person, expected_revision: int) -> None: ...


class EmployeeRepository(Protocol):
    async def get(self, employee_id: UUID) -> Employee | None: ...
    async def get_by_number(
        self, organization_id: UUID, employee_number: str
    ) -> Employee | None: ...
    async def list_visible(
        self,
        *,
        organization_id: UUID,
        organization_wide: bool,
        unit_ids: frozenset[UUID],
        self_employee_id: UUID | None,
        creator_user_id: UUID,
        offset: int,
        limit: int,
        active: bool | None,
        sort: str,
    ) -> list[Employee]: ...
    async def count_visible(
        self,
        *,
        organization_id: UUID,
        organization_wide: bool,
        unit_ids: frozenset[UUID],
        self_employee_id: UUID | None,
        creator_user_id: UUID,
        active: bool | None,
    ) -> int: ...
    async def add(self, employee: Employee) -> None: ...
    async def update(self, employee: Employee, expected_revision: int) -> None: ...


class AssignmentRepository(Protocol):
    async def get(self, assignment_id: UUID) -> EmployeeAssignment | None: ...
    async def list_for_employee(self, employee_id: UUID) -> list[EmployeeAssignment]: ...
    async def list_for_slot(self, staffing_slot_id: UUID) -> list[EmployeeAssignment]: ...
    async def add(self, assignment: EmployeeAssignment) -> None: ...
    async def update(self, assignment: EmployeeAssignment, expected_revision: int) -> None: ...


class AssignmentReviewRepository(Protocol):
    async def get_pending_for_assignment(
        self, assignment_id: UUID
    ) -> AssignmentReviewRequest | None: ...
    async def add(self, review: AssignmentReviewRequest) -> None: ...
    async def update(self, review: AssignmentReviewRequest, expected_revision: int) -> None: ...


class DelegationRepository(Protocol):
    async def get(self, delegation_id: UUID) -> Delegation | None: ...
    async def list(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID | None,
        at: datetime | None,
        offset: int,
        limit: int,
        sort: str,
    ) -> builtins.list[Delegation]: ...
    async def count(
        self, *, organization_id: UUID, employee_id: UUID | None, at: datetime | None
    ) -> int: ...
    async def list_for_pair(
        self, delegator_id: UUID, delegate_id: UUID
    ) -> builtins.list[Delegation]: ...
    async def add(self, delegation: Delegation) -> None: ...
    async def update(self, delegation: Delegation, expected_revision: int) -> None: ...


class StaffingSlotReader(Protocol):
    async def get(self, staffing_slot_id: UUID) -> StaffingSlotSnapshot | None: ...


class EmployeePolicyReader(Protocol):
    async def current(
        self, organization_id: UUID, *, effective_on: date
    ) -> EmployeePolicySnapshot: ...


class SensitiveDataProtector(Protocol):
    def protect(self, value: str) -> bytes: ...
    def reveal(self, value: bytes) -> str: ...


class AuditSink(Protocol):
    async def append(self, entry: AuditEntry) -> None: ...


class OutboxSink(Protocol):
    async def add(self, event: PendingEvent) -> None: ...


class EmployeeUnitOfWork(Protocol):
    people: PersonRepository
    employees: EmployeeRepository
    assignments: AssignmentRepository
    assignment_reviews: AssignmentReviewRepository
    delegations: DelegationRepository
    staffing_slots: StaffingSlotReader
    policies: EmployeePolicyReader
    audit: AuditSink
    outbox: OutboxSink

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
    async def lock_assignment_resources(
        self, employee_id: UUID, staffing_slot_id: UUID
    ) -> None: ...
    async def lock_delegation_resources(
        self, delegator_employee_id: UUID, delegate_employee_id: UUID
    ) -> None: ...


class EmployeeUnitOfWorkFactory(Protocol):
    def __call__(self) -> EmployeeUnitOfWork: ...
