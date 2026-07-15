"""Fast in-memory port implementations for employee use-case tests."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from app.modules.employees.application.ports import (
    EmployeePolicySnapshot,
    StaffingSlotSnapshot,
)
from app.modules.employees.domain.entities import (
    AssignmentReviewRequest,
    Delegation,
    Employee,
    EmployeeAssignment,
    Person,
)
from app.modules.employees.domain.enums import AssignmentReviewStatus, AssignmentStatus


class People:
    def __init__(self) -> None:
        self.items: dict[UUID, Person] = {}

    async def get(self, person_id: UUID) -> Person | None:
        return self.items.get(person_id)

    async def add(self, person: Person) -> None:
        self.items[person.id] = person

    async def update(self, person: Person, expected_revision: int) -> None:
        self.items[person.id] = person


class Employees:
    def __init__(self) -> None:
        self.items: dict[UUID, Employee] = {}
        self.assignments: Assignments | None = None
        self.slots: Slots | None = None

    async def get(self, employee_id: UUID) -> Employee | None:
        return self.items.get(employee_id)

    async def get_by_number(self, organization_id: UUID, employee_number: str) -> Employee | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.organization_id == organization_id
                and item.employee_number == employee_number
            ),
            None,
        )

    def _visible(
        self,
        *,
        organization_id: UUID,
        organization_wide: bool,
        unit_ids: frozenset[UUID],
        self_employee_id: UUID | None,
        creator_user_id: UUID,
        active: bool | None,
    ) -> list[Employee]:
        items = [
            item
            for item in self.items.values()
            if item.organization_id == organization_id and (active is None or item.active is active)
        ]
        if organization_wide:
            return items
        visible: list[Employee] = []
        for item in items:
            if item.id == self_employee_id or (
                item.created_by == creator_user_id and item.employment_status.value == "draft"
            ):
                visible.append(item)
                continue
            if self.assignments is None or self.slots is None:
                continue
            for assignment in self.assignments.items.values():
                slot = self.slots.items.get(assignment.staffing_slot_id)
                if (
                    assignment.employee_id == item.id
                    and assignment.status is not AssignmentStatus.CANCELLED
                    and assignment.effective_from <= date.today()
                    and (assignment.effective_to is None or assignment.effective_to >= date.today())
                    and slot is not None
                    and slot.organization_id == organization_id
                    and slot.organization_unit_id in unit_ids
                ):
                    visible.append(item)
                    break
        return visible

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
    ) -> list[Employee]:
        items = self._visible(
            organization_id=organization_id,
            organization_wide=organization_wide,
            unit_ids=unit_ids,
            self_employee_id=self_employee_id,
            creator_user_id=creator_user_id,
            active=active,
        )
        attribute = {
            "employeeNumber": "employee_number",
            "hireDate": "hire_date",
            "createdAt": "created_at",
        }[sort.removeprefix("-")]
        items.sort(key=lambda item: str(item.id))
        items.sort(key=lambda item: getattr(item, attribute), reverse=sort.startswith("-"))
        return items[offset : offset + limit]

    async def count_visible(
        self,
        *,
        organization_id: UUID,
        organization_wide: bool,
        unit_ids: frozenset[UUID],
        self_employee_id: UUID | None,
        creator_user_id: UUID,
        active: bool | None,
    ) -> int:
        return len(
            self._visible(
                organization_id=organization_id,
                organization_wide=organization_wide,
                unit_ids=unit_ids,
                self_employee_id=self_employee_id,
                creator_user_id=creator_user_id,
                active=active,
            )
        )

    async def add(self, employee: Employee) -> None:
        self.items[employee.id] = employee

    async def update(self, employee: Employee, expected_revision: int) -> None:
        self.items[employee.id] = employee


class Assignments:
    def __init__(self) -> None:
        self.items: dict[UUID, EmployeeAssignment] = {}

    async def get(self, assignment_id: UUID) -> EmployeeAssignment | None:
        return self.items.get(assignment_id)

    async def list_for_employee(self, employee_id: UUID) -> list[EmployeeAssignment]:
        return [item for item in self.items.values() if item.employee_id == employee_id]

    async def list_for_slot(self, staffing_slot_id: UUID) -> list[EmployeeAssignment]:
        return [item for item in self.items.values() if item.staffing_slot_id == staffing_slot_id]

    async def add(self, assignment: EmployeeAssignment) -> None:
        self.items[assignment.id] = assignment

    async def update(self, assignment: EmployeeAssignment, expected_revision: int) -> None:
        self.items[assignment.id] = assignment


class AssignmentReviews:
    def __init__(self) -> None:
        self.items: dict[UUID, AssignmentReviewRequest] = {}

    async def get_pending_for_assignment(
        self, assignment_id: UUID
    ) -> AssignmentReviewRequest | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.assignment_id == assignment_id
                and item.status is AssignmentReviewStatus.PENDING
            ),
            None,
        )

    async def add(self, review: AssignmentReviewRequest) -> None:
        self.items[review.id] = review

    async def update(self, review: AssignmentReviewRequest, expected_revision: int) -> None:
        self.items[review.id] = review


class Delegations:
    def __init__(self, employees: Employees) -> None:
        self.items: dict[UUID, Delegation] = {}
        self._employees = employees

    async def get(self, delegation_id: UUID) -> Delegation | None:
        return self.items.get(delegation_id)

    async def list(
        self,
        *,
        organization_id: UUID,
        employee_id: UUID | None,
        at: datetime | None,
        offset: int,
        limit: int,
        sort: str,
    ) -> list[Delegation]:
        items = [
            item
            for item in self.items.values()
            if self._employees.items[item.delegator_employee_id].organization_id == organization_id
        ]
        if employee_id is not None:
            items = [
                item
                for item in items
                if employee_id in {item.delegator_employee_id, item.delegate_employee_id}
            ]
        if at is not None:
            items = [item for item in items if item.effective_from <= at < item.effective_to]
        attribute = {
            "effectiveFrom": "effective_from",
            "createdAt": "created_at",
            "status": "status",
        }[sort.removeprefix("-")]
        items.sort(key=lambda item: str(item.id))
        items.sort(
            key=lambda item: (
                getattr(item, attribute).value
                if attribute == "status"
                else getattr(item, attribute)
            ),
            reverse=sort.startswith("-"),
        )
        return items[offset : offset + limit]

    async def count(
        self, *, organization_id: UUID, employee_id: UUID | None, at: datetime | None
    ) -> int:
        return len(
            await self.list(
                organization_id=organization_id,
                employee_id=employee_id,
                at=at,
                offset=0,
                limit=10_000,
                sort="-effectiveFrom",
            )
        )

    async def list_for_pair(self, delegator_id: UUID, delegate_id: UUID) -> list[Delegation]:
        return [
            item
            for item in self.items.values()
            if item.delegator_employee_id == delegator_id
            and item.delegate_employee_id == delegate_id
        ]

    async def add(self, delegation: Delegation) -> None:
        self.items[delegation.id] = delegation

    async def update(self, delegation: Delegation, expected_revision: int) -> None:
        self.items[delegation.id] = delegation


class Slots:
    def __init__(self) -> None:
        self.items: dict[UUID, StaffingSlotSnapshot] = {}

    async def get(self, staffing_slot_id: UUID) -> StaffingSlotSnapshot | None:
        return self.items.get(staffing_slot_id)


class Sink:
    def __init__(self) -> None:
        self.items: list[Any] = []

    async def append(self, item: Any) -> None:
        self.items.append(item)

    async def add(self, item: Any) -> None:
        self.items.append(item)


class Policies:
    def __init__(self) -> None:
        self.snapshot = EmployeePolicySnapshot(
            managers_can_create_employee_drafts=True,
            managers_can_assign_existing_employees=True,
            manager_changes_require_hr_approval=False,
        )

    async def current(self, organization_id: UUID, *, effective_on: date) -> EmployeePolicySnapshot:
        del organization_id, effective_on
        return self.snapshot


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.people = People()
        self.employees = Employees()
        self.assignments = Assignments()
        self.assignment_reviews = AssignmentReviews()
        self.staffing_slots = Slots()
        self.employees.assignments = self.assignments
        self.employees.slots = self.staffing_slots
        self.delegations = Delegations(self.employees)
        self.policies = Policies()
        self.audit = Sink()
        self.outbox = Sink()
        self.commits = 0

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None

    async def lock_assignment_resources(self, employee_id: UUID, staffing_slot_id: UUID) -> None:
        del employee_id, staffing_slot_id

    async def lock_delegation_resources(
        self, delegator_employee_id: UUID, delegate_employee_id: UUID
    ) -> None:
        del delegator_employee_id, delegate_employee_id

    def __call__(self) -> FakeUnitOfWork:
        return self


class TestProtector:
    __test__ = False

    def protect(self, value: str) -> bytes:
        return value[::-1].encode()

    def reveal(self, value: bytes) -> str:
        return value.decode()[::-1]
