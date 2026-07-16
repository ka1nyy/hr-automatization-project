"""Employee, assignment, and delegation use cases."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..domain.entities import (
    AssignmentReviewRequest,
    Delegation,
    Employee,
    EmployeeAssignment,
    Person,
    ranges_overlap,
    utc_now,
)
from ..domain.enums import (
    AssignmentStatus,
    DelegationScopeType,
    DelegationStatus,
    EmploymentStatus,
)
from ..domain.errors import EmployeeDomainError
from .commands import (
    CreateAssignmentCommand,
    CreateDelegationCommand,
    CreateEmployeeCommand,
    EndAssignmentCommand,
    HireEmployeeCommand,
    ReviewAssignmentCommand,
    RevokeDelegationCommand,
    TerminateEmployeeCommand,
    TransferEmployeeCommand,
    UpdateEmployeeCommand,
)
from .ports import (
    Actor,
    AuditEntry,
    EmployeeUnitOfWork,
    EmployeeUnitOfWorkFactory,
    PendingEvent,
    SensitiveDataProtector,
    StaffingSlotSnapshot,
)
from .views import DelegationPage, EmployeeDetails, EmployeePage


class EmployeeService:
    """Coordinates pure domain rules and transactional persistence ports."""

    def __init__(
        self,
        uow_factory: EmployeeUnitOfWorkFactory,
        sensitive_data: SensitiveDataProtector,
    ) -> None:
        self._uow_factory = uow_factory
        self._sensitive_data = sensitive_data

    async def create_employee(
        self, actor: Actor, command: CreateEmployeeCommand
    ) -> EmployeeDetails:
        self._require(actor, "employees.create")
        if command.iin is not None and (len(command.iin) != 12 or not command.iin.isdecimal()):
            raise EmployeeDomainError(
                "VALIDATION_FAILED",
                "IIN must contain exactly 12 digits.",
                {"field": "iin"},
                422,
            )
        protected_iin = self._sensitive_data.protect(command.iin) if command.iin else None
        person = Person(
            first_name=command.first_name,
            last_name=command.last_name,
            middle_name=command.middle_name,
            display_name=command.display_name,
            protected_iin=protected_iin,
            birth_date=command.birth_date,
            personal_email=command.personal_email,
            phone=command.phone,
        )
        employee = Employee(
            organization_id=actor.organization_id,
            created_by=actor.user_id,
            person_id=person.id,
            employee_number=command.employee_number,
            hire_date=command.hire_date,
            corporate_email=command.corporate_email,
            employment_status=command.employment_status,
        )
        async with self._uow_factory() as uow:
            policy = await uow.policies.current(actor.organization_id, effective_on=date.today())
            if not actor.allows("employees.create") and (
                not policy.managers_can_create_employee_drafts
                or command.employment_status is not EmploymentStatus.DRAFT
            ):
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "Managers may only create employee drafts when organization policy allows it.",
                    {"requiredStatus": EmploymentStatus.DRAFT.value},
                    403,
                )
            if (
                await uow.employees.get_by_number(actor.organization_id, employee.employee_number)
                is not None
            ):
                raise EmployeeDomainError(
                    "VALIDATION_FAILED",
                    "Employee number already exists.",
                    {"field": "employeeNumber"},
                    422,
                )
            await uow.people.add(person)
            await uow.employees.add(employee)
            await uow.audit.append(
                AuditEntry(
                    actor.user_id,
                    "employee.created",
                    "employee",
                    employee.id,
                    None,
                    self._safe_employee(employee, person),
                    organization_id=actor.organization_id,
                )
            )
            await uow.outbox.add(
                PendingEvent(
                    "employeeCreated",
                    "employee",
                    employee.id,
                    {"employeeId": str(employee.id), "organizationId": str(actor.organization_id)},
                )
            )
            await uow.commit()
        return EmployeeDetails(employee, person, ())

    async def update_employee(
        self, actor: Actor, command: UpdateEmployeeCommand
    ) -> EmployeeDetails:
        self._require(actor, "employees.edit")
        async with self._uow_factory() as uow:
            employee = await self._get_employee(uow, command.employee_id)
            person = await self._get_person(uow, employee.person_id)
            assignments = await uow.assignments.list_for_employee(employee.id)
            await self._require_employee_scope(actor, uow, employee, assignments, "employees.edit")
            if not actor.allows("employees.edit") and any(
                value is not None
                for value in (
                    command.employment_status,
                    command.active,
                    command.termination_date,
                )
            ):
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "Employment status, activation, and termination changes require "
                    "organization-wide HR authority.",
                    {},
                    403,
                )
            if command.revision != employee.revision:
                raise self._concurrency(command.revision, employee.revision)
            before = self._safe_employee(employee, person)
            employee_revision = employee.revision
            person_revision = person.revision

            if command.corporate_email is not None:
                employee.corporate_email = command.corporate_email
            if command.employment_status is not None:
                employee.employment_status = command.employment_status
            if command.active is not None:
                employee.active = command.active
            if command.termination_date is not None:
                if command.termination_date < employee.hire_date:
                    raise EmployeeDomainError(
                        "VALIDATION_FAILED",
                        "Termination date cannot precede hire date.",
                        {},
                        422,
                    )
                employee.termination_date = command.termination_date
            employee.revision += 1
            employee.updated_at = utc_now()

            person_changed = False
            for attribute in (
                "first_name",
                "last_name",
                "middle_name",
                "display_name",
                "personal_email",
                "phone",
            ):
                value = getattr(command, attribute)
                if value is not None:
                    setattr(person, attribute, value)
                    person_changed = True
            if person_changed:
                person.revision += 1
                person.updated_at = utc_now()
                await uow.people.update(person, person_revision)
            await uow.employees.update(employee, employee_revision)
            await uow.audit.append(
                AuditEntry(
                    actor.user_id,
                    "employee.changed",
                    "employee",
                    employee.id,
                    before,
                    self._safe_employee(employee, person),
                    organization_id=actor.organization_id,
                )
            )
            await uow.commit()
            return EmployeeDetails(employee, person, tuple(assignments))

    async def get_employee(
        self, actor: Actor, employee_id: UUID, *, include_sensitive: bool = False
    ) -> EmployeeDetails:
        self._require(actor, "employees.read")
        if include_sensitive:
            try:
                self._require(actor, "employees.read_sensitive")
            except EmployeeDomainError as exc:
                raise EmployeeDomainError(
                    "SENSITIVE_DATA_FORBIDDEN",
                    "Sensitive employee data requires explicit permission.",
                    {},
                    403,
                ) from exc
        async with self._uow_factory() as uow:
            employee = await self._get_employee(uow, employee_id)
            person = await self._get_person(uow, employee.person_id)
            assignments = await uow.assignments.list_for_employee(employee.id)
            await self._require_employee_scope(actor, uow, employee, assignments, "employees.read")
            if include_sensitive:
                try:
                    await self._require_employee_scope(
                        actor,
                        uow,
                        employee,
                        assignments,
                        "employees.read_sensitive",
                    )
                except EmployeeDomainError as exc:
                    raise EmployeeDomainError(
                        "SENSITIVE_DATA_FORBIDDEN",
                        "Sensitive employee data is outside the permitted scope.",
                        {},
                        403,
                    ) from exc
            iin = None
            if include_sensitive and person.protected_iin is not None:
                iin = self._sensitive_data.reveal(person.protected_iin)
            return EmployeeDetails(employee, person, tuple(assignments), iin)

    async def list_employees(
        self,
        actor: Actor,
        *,
        page: int,
        page_size: int,
        active: bool | None,
        sort: str = "employeeNumber",
    ) -> EmployeePage:
        self._require(actor, "employees.read")
        offset = (page - 1) * page_size
        async with self._uow_factory() as uow:
            organization_wide = actor.allows("employees.read")
            self_employee_id = (
                actor.employee_id
                if actor.employee_id is not None
                and actor.allows_self("employees.read", actor.employee_id)
                else None
            )
            employees = await uow.employees.list_visible(
                organization_id=actor.organization_id,
                organization_wide=organization_wide,
                unit_ids=actor.unit_ids_for("employees.read"),
                self_employee_id=self_employee_id,
                creator_user_id=actor.user_id,
                active=active,
                offset=offset,
                limit=page_size,
                sort=sort,
            )
            results: list[EmployeeDetails] = []
            for employee in employees:
                assignments = await uow.assignments.list_for_employee(employee.id)
                if not await self._has_employee_scope(
                    actor, uow, employee, assignments, "employees.read"
                ):
                    continue
                person = await self._get_person(uow, employee.person_id)
                results.append(EmployeeDetails(employee, person, tuple(assignments)))
            total = await uow.employees.count_visible(
                organization_id=actor.organization_id,
                organization_wide=organization_wide,
                unit_ids=actor.unit_ids_for("employees.read"),
                self_employee_id=self_employee_id,
                creator_user_id=actor.user_id,
                active=active,
            )
            return EmployeePage(tuple(results), total)

    async def create_assignment(
        self, actor: Actor, command: CreateAssignmentCommand
    ) -> EmployeeAssignment:
        self._require(actor, "employees.assign")
        async with self._uow_factory() as uow:
            await uow.lock_assignment_resources(command.employee_id, command.staffing_slot_id)
            employee = await self._get_employee(uow, command.employee_id)
            slot = await uow.staffing_slots.get(command.staffing_slot_id)
            if slot is None:
                raise EmployeeDomainError(
                    "RESOURCE_NOT_FOUND", "Staffing slot was not found.", {}, 404
                )
            self._require_slot_scope(actor, slot, "employees.assign")
            if employee.organization_id != actor.organization_id:
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "The employee belongs to another organization.",
                    {},
                    403,
                )
            policy = await uow.policies.current(
                actor.organization_id, effective_on=command.effective_from
            )
            manager_scoped = not actor.allows("employees.assign")
            if manager_scoped and not policy.managers_can_assign_existing_employees:
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "Organization policy does not allow managers to assign existing employees.",
                    {},
                    403,
                )
            self._validate_active_structure(command.effective_from, slot)
            self._validate_slot_dates(command.effective_from, command.effective_to, slot)
            if slot.status not in {"approved", "vacant", "occupied", "closing"}:
                raise EmployeeDomainError(
                    "STAFFING_SLOT_NOT_AVAILABLE",
                    "The staffing slot is not available for assignment.",
                    {"status": slot.status},
                )
            assignment = EmployeeAssignment(
                employee_id=command.employee_id,
                staffing_slot_id=command.staffing_slot_id,
                assignment_type=command.assignment_type,
                full_time_equivalent=command.full_time_equivalent,
                effective_from=command.effective_from,
                effective_to=command.effective_to,
                primary=command.primary,
                acting=command.acting,
                source_document_id=command.source_document_id,
                status=(
                    AssignmentStatus.PENDING_REVIEW
                    if manager_scoped and policy.manager_changes_require_hr_approval
                    else AssignmentStatus.ENDED
                    if command.effective_to is not None and command.effective_to < date.today()
                    else AssignmentStatus.ACTIVE
                    if command.effective_from <= date.today()
                    and (command.effective_to is None or command.effective_to >= date.today())
                    else AssignmentStatus.PLANNED
                ),
            )
            await self._ensure_assignment_capacity(uow, assignment, slot)
            await uow.assignments.add(assignment)
            review_request: AssignmentReviewRequest | None = None
            if assignment.status is AssignmentStatus.PENDING_REVIEW:
                review_request = AssignmentReviewRequest(
                    organization_id=actor.organization_id,
                    assignment_id=assignment.id,
                    submitted_by=actor.user_id,
                    submission_reason=(
                        "Organization policy requires HR approval for manager changes."
                    ),
                )
                await uow.assignment_reviews.add(review_request)
            await uow.audit.append(
                AuditEntry(
                    actor.user_id,
                    (
                        "employee.assignment.review.requested"
                        if assignment.status is AssignmentStatus.PENDING_REVIEW
                        else "employee.assignment.started"
                    ),
                    "employee_assignment",
                    assignment.id,
                    None,
                    self._safe_assignment(assignment),
                    organization_id=actor.organization_id,
                )
            )
            await uow.outbox.add(
                PendingEvent(
                    (
                        "employeeAssignmentReviewRequested"
                        if assignment.status is AssignmentStatus.PENDING_REVIEW
                        else "employeeAssignmentStarted"
                    ),
                    "employee_assignment",
                    assignment.id,
                    {
                        "assignmentId": str(assignment.id),
                        "employeeId": str(assignment.employee_id),
                        "staffingSlotId": str(assignment.staffing_slot_id),
                        "reviewRequestId": (
                            str(review_request.id) if review_request is not None else None
                        ),
                    },
                )
            )
            await uow.commit()
            return assignment

    async def review_assignment(
        self, actor: Actor, command: ReviewAssignmentCommand
    ) -> EmployeeAssignment:
        """Resolve a manager-submitted assignment using organization-wide HR authority."""

        self._require(actor, "employees.assign")
        if not actor.allows("employees.assign"):
            raise EmployeeDomainError(
                "AUTH_SCOPE_VIOLATION",
                "Assignment reviews require organization-wide assignment authority.",
                {},
                403,
            )
        if not command.reason.strip():
            raise EmployeeDomainError("VALIDATION_FAILED", "A reason is required.", {}, 422)
        async with self._uow_factory() as uow:
            assignment = await uow.assignments.get(command.assignment_id)
            if assignment is None:
                raise EmployeeDomainError(
                    "RESOURCE_NOT_FOUND", "Assignment was not found.", {}, 404
                )
            review_request = await uow.assignment_reviews.get_pending_for_assignment(assignment.id)
            if review_request is None:
                raise EmployeeDomainError(
                    "VERSION_CONFLICT",
                    "No pending review exists for this assignment.",
                    {},
                )
            await uow.lock_assignment_resources(assignment.employee_id, assignment.staffing_slot_id)
            employee = await self._get_employee(uow, assignment.employee_id)
            slot = await uow.staffing_slots.get(assignment.staffing_slot_id)
            if slot is None:
                raise EmployeeDomainError(
                    "RESOURCE_NOT_FOUND", "Staffing slot was not found.", {}, 404
                )
            self._require_slot_scope(actor, slot, "employees.assign")
            if employee.organization_id != actor.organization_id:
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "The employee belongs to another organization.",
                    {},
                    403,
                )
            if command.approved:
                self._validate_active_structure(assignment.effective_from, slot)
                self._validate_slot_dates(assignment.effective_from, assignment.effective_to, slot)
                if slot.status not in {"approved", "vacant", "occupied", "closing"}:
                    raise EmployeeDomainError(
                        "STAFFING_SLOT_NOT_AVAILABLE",
                        "The staffing slot is no longer available for assignment.",
                        {"status": slot.status},
                    )
                await self._ensure_assignment_capacity(uow, assignment, slot)
            before = self._safe_assignment(assignment)
            expected_revision = assignment.revision
            assignment.resolve_review(approved=command.approved, expected_revision=command.revision)
            await uow.assignments.update(assignment, expected_revision)
            review_expected_revision = review_request.revision
            review_request.resolve(
                approved=command.approved,
                actor_id=actor.user_id,
                reason=command.reason,
                expected_revision=command.revision,
            )
            await uow.assignment_reviews.update(review_request, review_expected_revision)
            action = (
                "employee.assignment.review.approved"
                if command.approved
                else "employee.assignment.review.rejected"
            )
            await uow.audit.append(
                AuditEntry(
                    actor.user_id,
                    action,
                    "employee_assignment",
                    assignment.id,
                    before,
                    self._safe_assignment(assignment),
                    command.reason,
                    organization_id=actor.organization_id,
                )
            )
            await uow.outbox.add(
                PendingEvent(
                    (
                        "employeeAssignmentStarted"
                        if command.approved
                        else "employeeAssignmentReviewRejected"
                    ),
                    "employee_assignment",
                    assignment.id,
                    {
                        "assignmentId": str(assignment.id),
                        "reviewRequestId": str(review_request.id),
                        "employeeId": str(assignment.employee_id),
                        "approved": command.approved,
                    },
                )
            )
            await uow.commit()
            return assignment

    async def end_assignment(
        self, actor: Actor, command: EndAssignmentCommand
    ) -> EmployeeAssignment:
        self._require(actor, "employees.assign")
        if not command.reason.strip():
            raise EmployeeDomainError("VALIDATION_FAILED", "A reason is required.", {}, 422)
        async with self._uow_factory() as uow:
            assignment = await uow.assignments.get(command.assignment_id)
            if assignment is None:
                raise EmployeeDomainError(
                    "RESOURCE_NOT_FOUND", "Assignment was not found.", {}, 404
                )
            slot = await uow.staffing_slots.get(assignment.staffing_slot_id)
            if slot is None:
                raise EmployeeDomainError(
                    "RESOURCE_NOT_FOUND", "Staffing slot was not found.", {}, 404
                )
            self._require_slot_scope(actor, slot, "employees.assign")
            self._validate_slot_dates(assignment.effective_from, command.effective_to, slot)
            before = self._safe_assignment(assignment)
            expected = assignment.revision
            assignment.end(effective_to=command.effective_to, expected_revision=command.revision)
            await uow.assignments.update(assignment, expected)
            await uow.audit.append(
                AuditEntry(
                    actor.user_id,
                    (
                        "employee.assignment.end.scheduled"
                        if command.effective_to > date.today()
                        else "employee.assignment.ended"
                    ),
                    "employee_assignment",
                    assignment.id,
                    before,
                    self._safe_assignment(assignment),
                    command.reason,
                    organization_id=actor.organization_id,
                )
            )
            await uow.outbox.add(
                PendingEvent(
                    (
                        "employeeAssignmentEndScheduled"
                        if command.effective_to > date.today()
                        else "employeeAssignmentEnded"
                    ),
                    "employee_assignment",
                    assignment.id,
                    {
                        "assignmentId": str(assignment.id),
                        "effectiveTo": command.effective_to.isoformat(),
                    },
                )
            )
            await uow.commit()
            return assignment

    async def hire_employee(self, actor: Actor, command: HireEmployeeCommand) -> EmployeeDetails:
        """Create an active employment record, optionally with its primary assignment."""

        self._require(actor, "employees.hire")
        if command.iin is not None and (len(command.iin) != 12 or not command.iin.isdecimal()):
            raise EmployeeDomainError(
                "VALIDATION_FAILED",
                "IIN must contain exactly 12 digits.",
                {"field": "iin"},
                422,
            )
        if command.staffing_slot_id is None and not actor.allows("employees.hire"):
            raise EmployeeDomainError(
                "AUTH_SCOPE_VIOLATION",
                "Unit-scoped hiring requires a staffing slot.",
                {},
                403,
            )
        protected_iin = self._sensitive_data.protect(command.iin) if command.iin else None
        person = Person(
            first_name=command.first_name,
            last_name=command.last_name,
            middle_name=command.middle_name,
            display_name=command.display_name,
            protected_iin=protected_iin,
            birth_date=command.birth_date,
            personal_email=command.personal_email,
            phone=command.phone,
        )
        employee = Employee(
            organization_id=actor.organization_id,
            created_by=actor.user_id,
            person_id=person.id,
            employee_number=command.employee_number,
            hire_date=command.hire_date,
            corporate_email=command.corporate_email,
            employment_status=EmploymentStatus.ACTIVE,
        )
        async with self._uow_factory() as uow:
            if (
                await uow.employees.get_by_number(actor.organization_id, employee.employee_number)
                is not None
            ):
                raise EmployeeDomainError(
                    "VALIDATION_FAILED",
                    "Employee number already exists.",
                    {"field": "employeeNumber"},
                    422,
                )
            assignment: EmployeeAssignment | None = None
            if command.staffing_slot_id is not None:
                await uow.lock_assignment_resources(employee.id, command.staffing_slot_id)
                slot = await uow.staffing_slots.get(command.staffing_slot_id)
                if slot is None:
                    raise EmployeeDomainError(
                        "RESOURCE_NOT_FOUND", "Staffing slot was not found.", {}, 404
                    )
                self._require_slot_scope(actor, slot, "employees.hire")
                self._validate_active_structure(command.hire_date, slot)
                self._validate_slot_dates(command.hire_date, None, slot)
                if slot.status not in {"approved", "vacant", "occupied", "closing"}:
                    raise EmployeeDomainError(
                        "STAFFING_SLOT_NOT_AVAILABLE",
                        "The staffing slot is not available for assignment.",
                        {"status": slot.status},
                    )
                assignment = EmployeeAssignment(
                    employee_id=employee.id,
                    staffing_slot_id=command.staffing_slot_id,
                    assignment_type=command.assignment_type,
                    full_time_equivalent=command.full_time_equivalent,
                    effective_from=command.hire_date,
                    primary=True,
                    status=(
                        AssignmentStatus.ACTIVE
                        if command.hire_date <= date.today()
                        else AssignmentStatus.PLANNED
                    ),
                )
                await self._ensure_assignment_capacity(uow, assignment, slot)
            await uow.people.add(person)
            await uow.employees.add(employee)
            if assignment is not None:
                await uow.assignments.add(assignment)
            after = self._safe_employee(employee, person)
            if assignment is not None:
                after["assignmentId"] = str(assignment.id)
                after["staffingSlotId"] = str(assignment.staffing_slot_id)
            await uow.audit.append(
                AuditEntry(
                    actor.user_id,
                    "employee.hired",
                    "employee",
                    employee.id,
                    None,
                    after,
                    organization_id=actor.organization_id,
                )
            )
            await uow.outbox.add(
                PendingEvent(
                    "employeeHired",
                    "employee",
                    employee.id,
                    {
                        "employeeId": str(employee.id),
                        "organizationId": str(actor.organization_id),
                        "assignmentId": str(assignment.id) if assignment is not None else None,
                        "hireDate": command.hire_date.isoformat(),
                    },
                )
            )
            await uow.commit()
        assignments = (assignment,) if assignment is not None else ()
        return EmployeeDetails(employee, person, assignments)

    async def terminate_employee(
        self, actor: Actor, command: TerminateEmployeeCommand
    ) -> EmployeeDetails:
        """End employment and every assignment still open on the termination date."""

        self._require(actor, "employees.terminate")
        if not command.reason.strip():
            raise EmployeeDomainError("VALIDATION_FAILED", "A reason is required.", {}, 422)
        async with self._uow_factory() as uow:
            employee = await self._get_employee(uow, command.employee_id)
            person = await self._get_person(uow, employee.person_id)
            assignments = await uow.assignments.list_for_employee(employee.id)
            await self._require_employee_scope(
                actor, uow, employee, assignments, "employees.terminate"
            )
            if command.revision != employee.revision:
                raise self._concurrency(command.revision, employee.revision)
            if command.termination_date < employee.hire_date:
                raise EmployeeDomainError(
                    "VALIDATION_FAILED",
                    "Termination date cannot precede hire date.",
                    {},
                    422,
                )
            if employee.employment_status is EmploymentStatus.ENDED or not employee.active:
                raise EmployeeDomainError(
                    "VERSION_CONFLICT",
                    "The employee is already terminated.",
                    {"employmentStatus": employee.employment_status.value},
                )
            before = self._safe_employee(employee, person)
            expected_employee_revision = employee.revision
            employee.termination_date = command.termination_date
            terminates_now = command.termination_date <= date.today()
            if terminates_now:
                employee.employment_status = EmploymentStatus.ENDED
                employee.active = False
            employee.revision += 1
            employee.updated_at = utc_now()
            await uow.employees.update(employee, expected_employee_revision)
            for assignment in assignments:
                if assignment.status in {AssignmentStatus.CANCELLED, AssignmentStatus.ENDED}:
                    continue
                expected_assignment_revision = assignment.revision
                if (
                    assignment.status is AssignmentStatus.PENDING_REVIEW
                    or assignment.effective_from > command.termination_date
                ):
                    assignment.status = AssignmentStatus.CANCELLED
                    assignment.revision += 1
                    assignment.updated_at = utc_now()
                    await uow.assignments.update(assignment, expected_assignment_revision)
                    continue
                if (
                    assignment.effective_to is not None
                    and assignment.effective_to <= command.termination_date
                ):
                    continue
                assignment.end(
                    effective_to=command.termination_date,
                    expected_revision=expected_assignment_revision,
                )
                await uow.assignments.update(assignment, expected_assignment_revision)
            await uow.audit.append(
                AuditEntry(
                    actor.user_id,
                    "employee.terminated" if terminates_now else "employee.termination.scheduled",
                    "employee",
                    employee.id,
                    before,
                    self._safe_employee(employee, person),
                    command.reason,
                    organization_id=actor.organization_id,
                )
            )
            await uow.outbox.add(
                PendingEvent(
                    "employeeTerminated" if terminates_now else "employeeTerminationScheduled",
                    "employee",
                    employee.id,
                    {
                        "employeeId": str(employee.id),
                        "terminationDate": command.termination_date.isoformat(),
                    },
                )
            )
            await uow.commit()
            return EmployeeDetails(employee, person, tuple(assignments))

    async def transfer_employee(
        self, actor: Actor, command: TransferEmployeeCommand
    ) -> EmployeeDetails:
        """Atomically end the current primary assignment and start one in another slot."""

        self._require(actor, "employees.transfer")
        if not command.reason.strip():
            raise EmployeeDomainError("VALIDATION_FAILED", "A reason is required.", {}, 422)
        async with self._uow_factory() as uow:
            employee = await self._get_employee(uow, command.employee_id)
            person = await self._get_person(uow, employee.person_id)
            assignments = await uow.assignments.list_for_employee(employee.id)
            await self._require_employee_scope(
                actor, uow, employee, assignments, "employees.transfer"
            )
            if employee.employment_status is EmploymentStatus.ENDED or not employee.active:
                raise EmployeeDomainError(
                    "VERSION_CONFLICT",
                    "A terminated employee cannot be transferred.",
                    {"employmentStatus": employee.employment_status.value},
                )
            current = next(
                (
                    item
                    for item in assignments
                    if item.primary and item.effective_status() is AssignmentStatus.ACTIVE
                ),
                None,
            )
            if current is None:
                raise EmployeeDomainError(
                    "VERSION_CONFLICT",
                    "The employee has no active primary assignment to transfer.",
                    {},
                )
            if current.staffing_slot_id == command.staffing_slot_id:
                raise EmployeeDomainError(
                    "VALIDATION_FAILED",
                    "The transfer target must differ from the current staffing slot.",
                    {"field": "staffingSlotId"},
                    422,
                )
            if command.effective_from <= current.effective_from:
                raise EmployeeDomainError(
                    "ASSIGNMENT_DATE_CONFLICT",
                    "The transfer must start after the current assignment start date.",
                    {"currentEffectiveFrom": current.effective_from.isoformat()},
                )
            await uow.lock_assignment_resources(employee.id, current.staffing_slot_id)
            await uow.lock_assignment_resources(employee.id, command.staffing_slot_id)
            slot = await uow.staffing_slots.get(command.staffing_slot_id)
            if slot is None:
                raise EmployeeDomainError(
                    "RESOURCE_NOT_FOUND", "Staffing slot was not found.", {}, 404
                )
            self._require_slot_scope(actor, slot, "employees.transfer")
            self._validate_active_structure(command.effective_from, slot)
            self._validate_slot_dates(command.effective_from, None, slot)
            if slot.status not in {"approved", "vacant", "occupied", "closing"}:
                raise EmployeeDomainError(
                    "STAFFING_SLOT_NOT_AVAILABLE",
                    "The staffing slot is not available for assignment.",
                    {"status": slot.status},
                )
            before = self._safe_assignment(current)
            expected_current_revision = current.revision
            current.end(
                effective_to=command.effective_from - timedelta(days=1),
                expected_revision=expected_current_revision,
            )
            await uow.assignments.update(current, expected_current_revision)
            assignment = EmployeeAssignment(
                employee_id=employee.id,
                staffing_slot_id=command.staffing_slot_id,
                assignment_type=command.assignment_type,
                full_time_equivalent=command.full_time_equivalent,
                effective_from=command.effective_from,
                primary=True,
                status=(
                    AssignmentStatus.ACTIVE
                    if command.effective_from <= date.today()
                    else AssignmentStatus.PLANNED
                ),
            )
            await self._ensure_assignment_capacity(uow, assignment, slot)
            await uow.assignments.add(assignment)
            after = self._safe_assignment(assignment)
            after["previousAssignmentId"] = str(current.id)
            await uow.audit.append(
                AuditEntry(
                    actor.user_id,
                    "employee.transferred",
                    "employee_assignment",
                    assignment.id,
                    before,
                    after,
                    command.reason,
                    organization_id=actor.organization_id,
                )
            )
            await uow.outbox.add(
                PendingEvent(
                    "employeeTransferred",
                    "employee_assignment",
                    assignment.id,
                    {
                        "employeeId": str(employee.id),
                        "previousAssignmentId": str(current.id),
                        "assignmentId": str(assignment.id),
                        "fromStaffingSlotId": str(current.staffing_slot_id),
                        "toStaffingSlotId": str(command.staffing_slot_id),
                        "effectiveFrom": command.effective_from.isoformat(),
                    },
                )
            )
            await uow.commit()
            return EmployeeDetails(
                employee, person, tuple(await uow.assignments.list_for_employee(employee.id))
            )

    async def has_employee_permission(
        self, actor: Actor, employee_id: UUID, permission: str
    ) -> bool:
        """Report whether the actor holds the permission within the employee's scope."""

        if "*" not in actor.permissions and permission not in actor.permissions:
            return False
        async with self._uow_factory() as uow:
            employee = await uow.employees.get(employee_id)
            if employee is None:
                return False
            assignments = await uow.assignments.list_for_employee(employee.id)
            return await self._has_employee_scope(actor, uow, employee, assignments, permission)

    async def create_delegation(self, actor: Actor, command: CreateDelegationCommand) -> Delegation:
        self._require(actor, "delegations.manage")
        now = utc_now()
        delegation = Delegation(
            delegator_employee_id=command.delegator_employee_id,
            delegate_employee_id=command.delegate_employee_id,
            scope_type=command.scope_type,
            scope_reference=command.scope_reference,
            delegated_permissions=command.delegated_permissions,
            effective_from=command.effective_from,
            effective_to=command.effective_to,
            reason=command.reason,
            source_document_id=command.source_document_id,
            created_by=actor.user_id,
            status=(
                DelegationStatus.ACTIVE
                if command.effective_from <= now
                else DelegationStatus.SCHEDULED
            ),
        )
        async with self._uow_factory() as uow:
            await uow.lock_delegation_resources(
                command.delegator_employee_id, command.delegate_employee_id
            )
            delegator = await self._get_employee(uow, command.delegator_employee_id)
            delegate = await self._get_employee(uow, command.delegate_employee_id)
            if (
                delegator.organization_id != actor.organization_id
                or delegate.organization_id != actor.organization_id
            ):
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "Both delegation participants must belong to the actor's organization.",
                    {},
                    403,
                )
            organization_wide = actor.allows("delegations.manage")
            if not organization_wide and actor.employee_id != delegator.id:
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "Scoped users may only delegate their own authority.",
                    {},
                    403,
                )
            if not organization_wide:
                self._validate_delegated_authority(actor, command)
            await self._require_employee_scope(
                actor,
                uow,
                delegator,
                await uow.assignments.list_for_employee(delegator.id),
                "delegations.manage",
            )
            await self._require_employee_scope(
                actor,
                uow,
                delegate,
                await uow.assignments.list_for_employee(delegate.id),
                "delegations.manage",
            )
            existing = await uow.delegations.list_for_pair(
                command.delegator_employee_id, command.delegate_employee_id
            )
            for item in existing:
                if item.effective_status(now) in {
                    DelegationStatus.REVOKED,
                    DelegationStatus.EXPIRED,
                }:
                    continue
                if (
                    ranges_overlap(
                        delegation.effective_from.date(),
                        delegation.effective_to.date(),
                        item.effective_from.date(),
                        item.effective_to.date(),
                    )
                    and delegation.scope_type is item.scope_type
                    and delegation.scope_reference == item.scope_reference
                    and set(delegation.delegated_permissions).intersection(
                        item.delegated_permissions
                    )
                ):
                    raise EmployeeDomainError(
                        "DELEGATION_DATE_CONFLICT",
                        "An overlapping delegation already grants this authority.",
                        {"existingDelegationId": str(item.id)},
                    )
            await uow.delegations.add(delegation)
            await uow.audit.append(
                AuditEntry(
                    actor.user_id,
                    "delegation.started",
                    "delegation",
                    delegation.id,
                    None,
                    self._safe_delegation(delegation),
                    command.reason,
                    organization_id=actor.organization_id,
                )
            )
            await uow.outbox.add(
                PendingEvent(
                    "delegationStarted",
                    "delegation",
                    delegation.id,
                    {"delegationId": str(delegation.id)},
                )
            )
            await uow.commit()
            return delegation

    async def revoke_delegation(self, actor: Actor, command: RevokeDelegationCommand) -> Delegation:
        self._require(actor, "delegations.manage")
        if not command.reason.strip():
            raise EmployeeDomainError("VALIDATION_FAILED", "A reason is required.", {}, 422)
        async with self._uow_factory() as uow:
            delegation = await uow.delegations.get(command.delegation_id)
            if delegation is None:
                raise EmployeeDomainError(
                    "RESOURCE_NOT_FOUND", "Delegation was not found.", {}, 404
                )
            delegator_assignments = await uow.assignments.list_for_employee(
                delegation.delegator_employee_id
            )
            delegator = await self._get_employee(uow, delegation.delegator_employee_id)
            await self._require_employee_scope(
                actor,
                uow,
                delegator,
                delegator_assignments,
                "delegations.manage",
            )
            before = self._safe_delegation(delegation)
            expected = delegation.revision
            delegation.revoke(revoked_at=utc_now(), expected_revision=command.revision)
            await uow.delegations.update(delegation, expected)
            await uow.audit.append(
                AuditEntry(
                    actor.user_id,
                    "delegation.revoked",
                    "delegation",
                    delegation.id,
                    before,
                    self._safe_delegation(delegation),
                    command.reason,
                    organization_id=actor.organization_id,
                )
            )
            await uow.outbox.add(
                PendingEvent(
                    "delegationRevoked",
                    "delegation",
                    delegation.id,
                    {"delegationId": str(delegation.id)},
                )
            )
            await uow.commit()
            return delegation

    async def list_delegations(
        self,
        actor: Actor,
        *,
        employee_id: UUID | None,
        active_at: Any | None,
        page: int,
        page_size: int,
        sort: str = "-effectiveFrom",
    ) -> DelegationPage:
        self._require(actor, "delegations.manage")
        async with self._uow_factory() as uow:
            if employee_id is None and not actor.allows("delegations.manage"):
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "A unit-scoped delegation query requires employeeId.",
                    {},
                    403,
                )
            if employee_id is not None:
                employee = await self._get_employee(uow, employee_id)
                await self._require_employee_scope(
                    actor,
                    uow,
                    employee,
                    await uow.assignments.list_for_employee(employee.id),
                    "delegations.manage",
                )
            items = await uow.delegations.list(
                organization_id=actor.organization_id,
                employee_id=employee_id,
                at=active_at,
                offset=(page - 1) * page_size,
                limit=page_size,
                sort=sort,
            )
            total = await uow.delegations.count(
                organization_id=actor.organization_id,
                employee_id=employee_id,
                at=active_at,
            )
            return DelegationPage(tuple(items), total)

    @staticmethod
    def _validate_delegated_authority(actor: Actor, command: CreateDelegationCommand) -> None:
        missing = sorted(
            permission
            for permission in command.delegated_permissions
            if "*" not in actor.permissions and permission not in actor.permissions
        )
        if missing:
            raise EmployeeDomainError(
                "AUTH_SCOPE_VIOLATION",
                "A delegation cannot grant permissions the delegator does not hold.",
                {"permissions": missing},
                403,
            )
        if command.scope_type is DelegationScopeType.UNIT:
            try:
                unit_id = UUID(command.scope_reference or "")
            except ValueError as exc:
                raise EmployeeDomainError(
                    "VALIDATION_FAILED",
                    "A unit delegation requires a valid unit scopeReference.",
                    {"field": "scopeReference"},
                    422,
                ) from exc
            outside = [
                permission
                for permission in command.delegated_permissions
                if not actor.allows(permission, unit_id)
            ]
            if outside:
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "The requested unit delegation exceeds the delegator's unit scope.",
                    {"permissions": sorted(outside), "unitId": str(unit_id)},
                    403,
                )
        elif command.scope_type in {
            DelegationScopeType.PERMISSIONS,
            DelegationScopeType.ORGANIZATION,
        }:
            if (
                command.scope_type is DelegationScopeType.ORGANIZATION
                and command.scope_reference != str(actor.organization_id)
            ):
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "The organization delegation reference does not match the actor context.",
                    {},
                    403,
                )
            outside = [
                permission
                for permission in command.delegated_permissions
                if not actor.allows(permission)
            ]
            if outside:
                raise EmployeeDomainError(
                    "AUTH_SCOPE_VIOLATION",
                    "Organization-wide delegation requires organization-wide authority.",
                    {"permissions": sorted(outside)},
                    403,
                )

    @staticmethod
    def _require(actor: Actor, permission: str) -> None:
        if "*" not in actor.permissions and permission not in actor.permissions:
            raise EmployeeDomainError(
                "AUTH_FORBIDDEN", "The operation is not permitted.", {"permission": permission}, 403
            )

    @staticmethod
    async def _get_employee(uow: EmployeeUnitOfWork, employee_id: UUID) -> Employee:
        employee = await uow.employees.get(employee_id)
        if employee is None:
            raise EmployeeDomainError("RESOURCE_NOT_FOUND", "Employee was not found.", {}, 404)
        return employee

    @staticmethod
    async def _get_person(uow: EmployeeUnitOfWork, person_id: UUID) -> Person:
        person = await uow.people.get(person_id)
        if person is None:
            raise EmployeeDomainError("RESOURCE_NOT_FOUND", "Person was not found.", {}, 404)
        return person

    @staticmethod
    def _concurrency(expected: int, actual: int) -> EmployeeDomainError:
        return EmployeeDomainError(
            "CONCURRENCY_CONFLICT",
            "The record was changed by another user.",
            {"expectedRevision": expected, "actualRevision": actual},
        )

    @staticmethod
    def _require_slot_scope(actor: Actor, slot: StaffingSlotSnapshot, permission: str) -> None:
        if slot.organization_id != actor.organization_id:
            raise EmployeeDomainError(
                "AUTH_SCOPE_VIOLATION", "The resource belongs to another organization.", {}, 403
            )
        if not actor.allows_unit(
            permission,
            slot.organization_unit_id,
            slot.organization_unit_stable_key,
        ):
            raise EmployeeDomainError(
                "AUTH_SCOPE_VIOLATION", "The resource is outside the permitted unit scope.", {}, 403
            )

    async def _has_employee_scope(
        self,
        actor: Actor,
        uow: EmployeeUnitOfWork,
        employee: Employee,
        assignments: list[EmployeeAssignment],
        permission: str,
    ) -> bool:
        if employee.organization_id != actor.organization_id:
            return False
        if actor.allows_self(permission, employee.id):
            return True
        if actor.allows(permission):
            return True
        if (
            employee.created_by == actor.user_id
            and employee.employment_status is EmploymentStatus.DRAFT
            and permission in {"employees.read", "employees.edit"}
        ):
            return True
        for assignment in assignments:
            if (
                assignment.status is AssignmentStatus.CANCELLED
                or assignment.effective_from > date.today()
                or (assignment.effective_to is not None and assignment.effective_to < date.today())
            ):
                continue
            slot = await uow.staffing_slots.get(assignment.staffing_slot_id)
            if (
                slot is not None
                and slot.organization_id == actor.organization_id
                and actor.allows_unit(
                    permission,
                    slot.organization_unit_id,
                    slot.organization_unit_stable_key,
                )
            ):
                return True
        return False

    async def _require_employee_scope(
        self,
        actor: Actor,
        uow: EmployeeUnitOfWork,
        employee: Employee,
        assignments: list[EmployeeAssignment],
        permission: str,
    ) -> None:
        if not await self._has_employee_scope(actor, uow, employee, assignments, permission):
            raise EmployeeDomainError(
                "AUTH_SCOPE_VIOLATION", "The employee is outside the permitted unit scope.", {}, 403
            )

    @staticmethod
    def _peak_fte(candidate: EmployeeAssignment, existing: list[EmployeeAssignment]) -> Decimal:
        """Calculate temporal peak rather than summing disjoint overlapping subperiods."""

        checkpoints = {candidate.effective_from}
        for item in existing:
            checkpoints.add(max(candidate.effective_from, item.effective_from))
            if item.effective_to is not None and item.effective_to < date.max:
                after_end = item.effective_to + timedelta(days=1)
                if candidate.effective_to is None or after_end <= candidate.effective_to:
                    checkpoints.add(after_end)
        return max(
            (
                candidate.full_time_equivalent
                + sum(
                    (
                        item.full_time_equivalent
                        for item in existing
                        if item.effective_from <= checkpoint
                        and (item.effective_to is None or checkpoint <= item.effective_to)
                    ),
                    Decimal("0"),
                )
                for checkpoint in checkpoints
                if candidate.effective_to is None or checkpoint <= candidate.effective_to
            ),
            default=candidate.full_time_equivalent,
        )

    async def _ensure_assignment_capacity(
        self,
        uow: EmployeeUnitOfWork,
        assignment: EmployeeAssignment,
        slot: StaffingSlotSnapshot,
    ) -> None:
        employee_assignments = [
            item
            for item in await uow.assignments.list_for_employee(assignment.employee_id)
            if item.id != assignment.id
            and item.status is not AssignmentStatus.CANCELLED
            and assignment.overlaps(item)
        ]
        if assignment.primary and any(item.primary for item in employee_assignments):
            raise EmployeeDomainError(
                "EMPLOYEE_ALREADY_ASSIGNED",
                "The employee already has a primary assignment for this period.",
                {},
            )
        employee_fte = self._peak_fte(assignment, employee_assignments)
        if employee_fte > Decimal("1"):
            raise EmployeeDomainError(
                "STAFFING_FTE_EXCEEDED",
                "The employee's assignments exceed 1.0 FTE for this period.",
                {"calculatedFte": str(employee_fte)},
            )
        slot_assignments = [
            item
            for item in await uow.assignments.list_for_slot(slot.id)
            if item.id != assignment.id
            and item.status is not AssignmentStatus.CANCELLED
            and assignment.overlaps(item)
        ]
        slot_fte = self._peak_fte(assignment, slot_assignments)
        if slot_fte > slot.full_time_equivalent:
            raise EmployeeDomainError(
                "STAFFING_FTE_EXCEEDED",
                "Assignments exceed the staffing slot's approved FTE.",
                {
                    "calculatedFte": str(slot_fte),
                    "slotFte": str(slot.full_time_equivalent),
                },
            )

    @staticmethod
    def _validate_active_structure(effective_from: date, slot: StaffingSlotSnapshot) -> None:
        if (
            slot.structure_status != "published"
            or slot.structure_effective_from is None
            or effective_from < slot.structure_effective_from
            or (
                slot.structure_effective_to is not None
                and effective_from > slot.structure_effective_to
            )
        ):
            raise EmployeeDomainError(
                "STAFFING_SLOT_NOT_AVAILABLE",
                "Assignments must target the published structure effective on the "
                "assignment start date.",
                {
                    "structureStatus": slot.structure_status,
                    "effectiveFrom": effective_from.isoformat(),
                },
            )

    @staticmethod
    def _validate_slot_dates(
        effective_from: date, effective_to: date | None, slot: StaffingSlotSnapshot
    ) -> None:
        if effective_from < slot.effective_from or (
            slot.effective_to is not None
            and (effective_to is None or effective_to > slot.effective_to)
        ):
            raise EmployeeDomainError(
                "ASSIGNMENT_DATE_CONFLICT",
                "Assignment dates must fit within the staffing slot dates.",
                {},
            )
        if effective_to is not None and effective_to < effective_from:
            raise EmployeeDomainError(
                "ASSIGNMENT_DATE_CONFLICT",
                "Assignment end date cannot precede its start date.",
                {},
            )

    @staticmethod
    def _safe_employee(employee: Employee, person: Person) -> dict[str, Any]:
        return {
            "id": str(employee.id),
            "organizationId": str(employee.organization_id),
            "createdBy": str(employee.created_by),
            "personId": str(person.id),
            "employeeNumber": employee.employee_number,
            "displayName": person.display_name,
            "employmentStatus": employee.employment_status.value,
            "hireDate": employee.hire_date.isoformat(),
            "terminationDate": employee.termination_date.isoformat()
            if employee.termination_date
            else None,
            "corporateEmail": employee.corporate_email,
            "active": employee.active,
            "revision": employee.revision,
        }

    @staticmethod
    def _safe_assignment(assignment: EmployeeAssignment) -> dict[str, Any]:
        return {
            "id": str(assignment.id),
            "employeeId": str(assignment.employee_id),
            "staffingSlotId": str(assignment.staffing_slot_id),
            "assignmentType": assignment.assignment_type.value,
            "fullTimeEquivalent": str(assignment.full_time_equivalent),
            "effectiveFrom": assignment.effective_from.isoformat(),
            "effectiveTo": assignment.effective_to.isoformat() if assignment.effective_to else None,
            "primary": assignment.primary,
            "acting": assignment.acting,
            "status": assignment.status.value,
            "revision": assignment.revision,
        }

    @staticmethod
    def _safe_delegation(delegation: Delegation) -> dict[str, Any]:
        return {
            "id": str(delegation.id),
            "delegatorEmployeeId": str(delegation.delegator_employee_id),
            "delegateEmployeeId": str(delegation.delegate_employee_id),
            "scopeType": delegation.scope_type.value,
            "scopeReference": delegation.scope_reference,
            "delegatedPermissions": list(delegation.delegated_permissions),
            "effectiveFrom": delegation.effective_from.isoformat(),
            "effectiveTo": delegation.effective_to.isoformat(),
            "status": delegation.effective_status().value,
            "revision": delegation.revision,
        }
