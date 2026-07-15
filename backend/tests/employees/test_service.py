"""Employee, assignment, delegation, and sensitive-data behavior."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from app.modules.employees.application.commands import (
    CreateAssignmentCommand,
    CreateDelegationCommand,
    CreateEmployeeCommand,
    EndAssignmentCommand,
    ReviewAssignmentCommand,
    RevokeDelegationCommand,
    UpdateEmployeeCommand,
)
from app.modules.employees.application.ports import (
    Actor,
    EmployeePolicySnapshot,
    StaffingSlotSnapshot,
)
from app.modules.employees.application.service import EmployeeService
from app.modules.employees.domain.enums import (
    AssignmentStatus,
    AssignmentType,
    DelegationScopeType,
    DelegationStatus,
    EmploymentStatus,
)
from app.modules.employees.domain.errors import EmployeeDomainError

from .fakes import FakeUnitOfWork, TestProtector


@pytest.fixture
def organization_id():  # type: ignore[no-untyped-def]
    return uuid4()


@pytest.fixture
def actor(organization_id):  # type: ignore[no-untyped-def]
    return Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset(
            {
                "employees.read",
                "employees.read_sensitive",
                "employees.create",
                "employees.edit",
                "employees.assign",
                "delegations.manage",
            }
        ),
        organization_wide=True,
    )


@pytest.fixture
def uow():  # type: ignore[no-untyped-def]
    return FakeUnitOfWork()


@pytest.fixture
def service(uow):  # type: ignore[no-untyped-def]
    return EmployeeService(uow, TestProtector())


async def create_employee(service: EmployeeService, actor: Actor, number: str):
    return await service.create_employee(
        actor,
        CreateEmployeeCommand(
            first_name="Aruzhan",
            last_name="Sarsenova",
            employee_number=number,
            hire_date=date(2026, 1, 1),
            iin="900101350001",
        ),
    )


def add_slot(
    uow: FakeUnitOfWork,
    organization_id,
    *,
    fte: str = "1.0",
    unit_id=None,  # type: ignore[no-untyped-def]
    structure_status: str = "published",
    structure_effective_to: date | None = None,
    effective_to: date | None = None,
    status: str = "vacant",
):  # type: ignore[no-untyped-def]
    slot = StaffingSlotSnapshot(
        id=uuid4(),
        organization_id=organization_id,
        organization_unit_id=unit_id or uuid4(),
        structure_version_id=uuid4(),
        full_time_equivalent=Decimal(fte),
        status=status,
        effective_from=date(2026, 1, 1),
        effective_to=effective_to,
        structure_status=structure_status,
        structure_effective_to=structure_effective_to,
    )
    uow.staffing_slots.items[slot.id] = slot
    return slot


@pytest.mark.asyncio
async def test_employee_assignment_is_persisted_and_emits_audit_and_outbox(
    service, uow, actor, organization_id
):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "E-001")
    slot = add_slot(uow, organization_id)
    assignment = await service.create_assignment(
        actor,
        CreateAssignmentCommand(
            employee_id=employee.employee.id,
            staffing_slot_id=slot.id,
            assignment_type=AssignmentType.PERMANENT,
            full_time_equivalent=Decimal("1.0"),
            effective_from=date(2026, 1, 1),
            primary=True,
        ),
    )
    assert assignment.primary is True
    assert assignment.id in uow.assignments.items
    assert uow.audit.items[-1].action == "employee.assignment.started"
    assert uow.outbox.items[-1].event_type == "employeeAssignmentStarted"


@pytest.mark.asyncio
async def test_fte_overflow_is_rejected(service, uow, actor, organization_id):  # type: ignore[no-untyped-def]
    first = await create_employee(service, actor, "E-010")
    second = await create_employee(service, actor, "E-011")
    slot = add_slot(uow, organization_id)
    for employee, fte in ((first, "0.75"), (second, "0.50")):
        command = CreateAssignmentCommand(
            employee_id=employee.employee.id,
            staffing_slot_id=slot.id,
            assignment_type=AssignmentType.PART_TIME,
            full_time_equivalent=Decimal(fte),
            effective_from=date(2026, 1, 1),
        )
        if employee is first:
            await service.create_assignment(actor, command)
        else:
            with pytest.raises(EmployeeDomainError, match="approved FTE") as caught:
                await service.create_assignment(actor, command)
            assert caught.value.code == "STAFFING_FTE_EXCEEDED"


@pytest.mark.asyncio
async def test_acting_assignment_sets_acting_flag(service, uow, actor, organization_id):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "E-020")
    slot = add_slot(uow, organization_id)
    assignment = await service.create_assignment(
        actor,
        CreateAssignmentCommand(
            employee_id=employee.employee.id,
            staffing_slot_id=slot.id,
            assignment_type=AssignmentType.ACTING,
            full_time_equivalent=Decimal("0.5"),
            effective_from=date(2026, 2, 1),
            effective_to=date(2026, 2, 28),
        ),
    )
    assert assignment.acting is True


@pytest.mark.asyncio
async def test_stale_assignment_end_is_rejected(service, uow, actor, organization_id):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "E-030")
    slot = add_slot(uow, organization_id)
    assignment = await service.create_assignment(
        actor,
        CreateAssignmentCommand(
            employee_id=employee.employee.id,
            staffing_slot_id=slot.id,
            assignment_type=AssignmentType.PERMANENT,
            full_time_equivalent=Decimal("1"),
            effective_from=date(2026, 1, 1),
            primary=True,
        ),
    )
    with pytest.raises(EmployeeDomainError) as caught:
        await service.end_assignment(
            actor,
            EndAssignmentCommand(
                assignment_id=assignment.id,
                effective_to=date(2026, 3, 1),
                revision=99,
                reason="Correction",
            ),
        )
    assert caught.value.code == "CONCURRENCY_CONFLICT"


@pytest.mark.asyncio
async def test_delegation_revocation_and_expiration(service, actor):  # type: ignore[no-untyped-def]
    delegator = await create_employee(service, actor, "E-040")
    delegate = await create_employee(service, actor, "E-041")
    now = datetime.now(UTC)
    delegation = await service.create_delegation(
        actor,
        CreateDelegationCommand(
            delegator_employee_id=delegator.employee.id,
            delegate_employee_id=delegate.employee.id,
            scope_type=DelegationScopeType.UNIT,
            scope_reference=str(uuid4()),
            delegated_permissions=("employees.read",),
            effective_from=now - timedelta(hours=1),
            effective_to=now + timedelta(days=1),
            reason="Business continuity",
        ),
    )
    assert delegation.effective_status(now) is DelegationStatus.ACTIVE
    revoked = await service.revoke_delegation(
        actor,
        RevokeDelegationCommand(
            delegation_id=delegation.id,
            revision=delegation.revision,
            reason="Delegator returned",
        ),
    )
    assert revoked.effective_status(now) is DelegationStatus.REVOKED

    expired = await service.create_delegation(
        actor,
        CreateDelegationCommand(
            delegator_employee_id=delegator.employee.id,
            delegate_employee_id=delegate.employee.id,
            scope_type=DelegationScopeType.PROCESS,
            scope_reference="invoice-approval",
            delegated_permissions=("organization.read",),
            effective_from=now - timedelta(days=2),
            effective_to=now - timedelta(days=1),
            reason="Historical delegation",
        ),
    )
    assert expired.effective_status(now) is DelegationStatus.EXPIRED


@pytest.mark.asyncio
async def test_sensitive_data_requires_permission_and_is_never_in_public_view(service, actor):  # type: ignore[no-untyped-def]
    details = await create_employee(service, actor, "E-050")
    public = await service.get_employee(actor, details.employee.id)
    assert public.revealed_iin is None
    sensitive = await service.get_employee(actor, details.employee.id, include_sensitive=True)
    assert sensitive.revealed_iin == "900101350001"

    restricted = Actor(
        user_id=uuid4(),
        organization_id=actor.organization_id,
        permissions=frozenset({"employees.read"}),
        organization_wide=True,
    )
    with pytest.raises(EmployeeDomainError) as caught:
        await service.get_employee(restricted, details.employee.id, include_sensitive=True)
    assert caught.value.code == "SENSITIVE_DATA_FORBIDDEN"


@pytest.mark.asyncio
async def test_sensitive_permission_uses_its_own_unit_scope(service, uow, actor, organization_id):  # type: ignore[no-untyped-def]
    first = await create_employee(service, actor, "SENSITIVE-A")
    second = await create_employee(service, actor, "SENSITIVE-B")
    first_unit = uuid4()
    second_unit = uuid4()
    for employee, unit_id in ((first, first_unit), (second, second_unit)):
        slot = add_slot(uow, organization_id, unit_id=unit_id)
        await service.create_assignment(
            actor,
            CreateAssignmentCommand(
                employee_id=employee.employee.id,
                staffing_slot_id=slot.id,
                assignment_type=AssignmentType.PERMANENT,
                full_time_equivalent=Decimal("1"),
                effective_from=date.today(),
            ),
        )

    scoped_sensitive = Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset({"employees.read", "employees.read_sensitive"}),
        organization_wide_permissions=frozenset({"employees.read"}),
        permission_unit_ids={"employees.read_sensitive": frozenset({first_unit})},
    )
    with pytest.raises(EmployeeDomainError) as caught:
        await service.get_employee(scoped_sensitive, second.employee.id, include_sensitive=True)
    assert caught.value.code == "SENSITIVE_DATA_FORBIDDEN"


@pytest.mark.asyncio
async def test_cross_unit_assignment_is_rejected(service, uow, actor, organization_id):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "E-060")
    slot = add_slot(uow, organization_id)
    scoped_actor = Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset({"employees.assign"}),
        accessible_unit_ids=frozenset({uuid4()}),
    )
    with pytest.raises(EmployeeDomainError) as caught:
        await service.create_assignment(
            scoped_actor,
            CreateAssignmentCommand(
                employee_id=employee.employee.id,
                staffing_slot_id=slot.id,
                assignment_type=AssignmentType.PERMANENT,
                full_time_equivalent=Decimal("1"),
                effective_from=date(2026, 1, 1),
            ),
        )
    assert caught.value.code == "AUTH_SCOPE_VIOLATION"


@pytest.mark.asyncio
async def test_manager_can_create_only_drafts_and_cannot_activate_them(
    service, uow, organization_id
):  # type: ignore[no-untyped-def]
    manager = Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset({"employees.create", "employees.read", "employees.edit"}),
    )
    uow.policies.snapshot = EmployeePolicySnapshot(managers_can_create_employee_drafts=True)
    details = await create_employee(service, manager, "M-DRAFT-001")
    assert details.employee.employment_status is EmploymentStatus.DRAFT

    with pytest.raises(EmployeeDomainError) as caught:
        await service.update_employee(
            manager,
            UpdateEmployeeCommand(
                employee_id=details.employee.id,
                revision=details.employee.revision,
                employment_status=EmploymentStatus.ACTIVE,
            ),
        )
    assert caught.value.code == "AUTH_SCOPE_VIOLATION"


@pytest.mark.asyncio
async def test_manager_assignment_policy_and_hr_review_flow(service, uow, actor, organization_id):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "M-ASSIGN-001")
    unit_id = uuid4()
    slot = add_slot(uow, organization_id, unit_id=unit_id)
    manager = Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset({"employees.assign"}),
        accessible_unit_ids=frozenset({unit_id}),
        permission_unit_ids={"employees.assign": frozenset({unit_id})},
    )
    command = CreateAssignmentCommand(
        employee_id=employee.employee.id,
        staffing_slot_id=slot.id,
        assignment_type=AssignmentType.PERMANENT,
        full_time_equivalent=Decimal("1"),
        effective_from=date.today(),
        primary=True,
    )
    uow.policies.snapshot = EmployeePolicySnapshot(managers_can_assign_existing_employees=False)
    with pytest.raises(EmployeeDomainError) as denied:
        await service.create_assignment(manager, command)
    assert denied.value.code == "AUTH_SCOPE_VIOLATION"

    uow.policies.snapshot = EmployeePolicySnapshot(
        managers_can_assign_existing_employees=True,
        manager_changes_require_hr_approval=True,
    )
    pending = await service.create_assignment(manager, command)
    assert pending.status is AssignmentStatus.PENDING_REVIEW
    assert len(uow.assignment_reviews.items) == 1
    assert uow.outbox.items[-1].event_type == "employeeAssignmentReviewRequested"

    approved = await service.review_assignment(
        actor,
        ReviewAssignmentCommand(
            assignment_id=pending.id,
            approved=True,
            revision=pending.revision,
            reason="HR verified the assignment.",
        ),
    )
    assert approved.status is AssignmentStatus.ACTIVE
    assert uow.outbox.items[-1].event_type == "employeeAssignmentStarted"

    rejected_employee = await create_employee(service, actor, "M-ASSIGN-002")
    rejected_slot = add_slot(uow, organization_id, unit_id=unit_id)
    rejected_pending = await service.create_assignment(
        manager,
        CreateAssignmentCommand(
            employee_id=rejected_employee.employee.id,
            staffing_slot_id=rejected_slot.id,
            assignment_type=AssignmentType.PERMANENT,
            full_time_equivalent=Decimal("1"),
            effective_from=date.today(),
            primary=True,
        ),
    )
    rejected = await service.review_assignment(
        actor,
        ReviewAssignmentCommand(
            assignment_id=rejected_pending.id,
            approved=False,
            revision=rejected_pending.revision,
            reason="Required documentation is missing.",
        ),
    )
    assert rejected.status is AssignmentStatus.CANCELLED
    assert uow.outbox.items[-1].event_type == "employeeAssignmentReviewRejected"


@pytest.mark.asyncio
async def test_future_assignment_does_not_grant_early_directory_visibility(
    service, uow, actor, organization_id
):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "FUTURE-001")
    unit_id = uuid4()
    slot = add_slot(uow, organization_id, unit_id=unit_id)
    await service.create_assignment(
        actor,
        CreateAssignmentCommand(
            employee_id=employee.employee.id,
            staffing_slot_id=slot.id,
            assignment_type=AssignmentType.PERMANENT,
            full_time_equivalent=Decimal("1"),
            effective_from=date.today() + timedelta(days=30),
            primary=True,
        ),
    )
    director = Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset({"employees.read"}),
        accessible_unit_ids=frozenset({unit_id}),
    )
    page = await service.list_employees(director, page=1, page_size=20, active=True)
    assert page.items == ()
    assert page.total == 0


@pytest.mark.asyncio
async def test_organization_wide_reader_cannot_cross_employee_ownership(service, actor):  # type: ignore[no-untyped-def]
    other_actor = Actor(
        user_id=uuid4(),
        organization_id=uuid4(),
        permissions=actor.permissions,
        organization_wide=True,
    )
    other = await create_employee(service, other_actor, "OTHER-ORG-001")
    with pytest.raises(EmployeeDomainError) as caught:
        await service.get_employee(actor, other.employee.id)
    assert caught.value.code == "AUTH_SCOPE_VIOLATION"

    page = await service.list_employees(actor, page=1, page_size=20, active=True)
    assert all(item.employee.organization_id == actor.organization_id for item in page.items)


@pytest.mark.asyncio
async def test_employee_list_applies_allowlisted_sort_before_pagination(service, actor):  # type: ignore[no-untyped-def]
    await create_employee(service, actor, "SORT-001")
    await create_employee(service, actor, "SORT-002")

    page = await service.list_employees(
        actor,
        page=1,
        page_size=1,
        active=True,
        sort="-employeeNumber",
    )

    assert page.total == 2
    assert [item.employee.employee_number for item in page.items] == ["SORT-002"]


@pytest.mark.asyncio
async def test_future_scheduled_end_still_blocks_overlapping_primary_assignment(
    service, uow, actor, organization_id
):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "TEMPORAL-001")
    first_slot = add_slot(uow, organization_id)
    first = await service.create_assignment(
        actor,
        CreateAssignmentCommand(
            employee_id=employee.employee.id,
            staffing_slot_id=first_slot.id,
            assignment_type=AssignmentType.PERMANENT,
            full_time_equivalent=Decimal("0.5"),
            effective_from=date.today() - timedelta(days=10),
            primary=True,
        ),
    )
    scheduled = await service.end_assignment(
        actor,
        EndAssignmentCommand(
            assignment_id=first.id,
            effective_to=date.today() + timedelta(days=30),
            revision=first.revision,
            reason="Future transfer date",
        ),
    )
    assert scheduled.status is AssignmentStatus.SCHEDULED_END
    assert scheduled.effective_status() is AssignmentStatus.ACTIVE
    assert uow.outbox.items[-1].event_type == "employeeAssignmentEndScheduled"
    second_slot = add_slot(uow, organization_id)
    with pytest.raises(EmployeeDomainError) as caught:
        await service.create_assignment(
            actor,
            CreateAssignmentCommand(
                employee_id=employee.employee.id,
                staffing_slot_id=second_slot.id,
                assignment_type=AssignmentType.CONCURRENT,
                full_time_equivalent=Decimal("0.5"),
                effective_from=date.today() + timedelta(days=1),
                primary=True,
            ),
        )
    assert caught.value.code == "EMPLOYEE_ALREADY_ASSIGNED"


@pytest.mark.asyncio
async def test_assignment_end_must_remain_within_staffing_slot(
    service, uow, actor, organization_id
):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "SLOT-END-001")
    slot_end = date.today() + timedelta(days=10)
    slot = add_slot(uow, organization_id, effective_to=slot_end)
    assignment = await service.create_assignment(
        actor,
        CreateAssignmentCommand(
            employee_id=employee.employee.id,
            staffing_slot_id=slot.id,
            assignment_type=AssignmentType.PERMANENT,
            full_time_equivalent=Decimal("1"),
            effective_from=date.today(),
            effective_to=slot_end,
        ),
    )

    with pytest.raises(EmployeeDomainError) as caught:
        await service.end_assignment(
            actor,
            EndAssignmentCommand(
                assignment_id=assignment.id,
                effective_to=slot_end + timedelta(days=1),
                revision=assignment.revision,
                reason="Invalid extension",
            ),
        )

    assert caught.value.code == "ASSIGNMENT_DATE_CONFLICT"
    assert assignment.effective_to == slot_end


@pytest.mark.asyncio
async def test_future_closing_slot_remains_assignable_within_its_remaining_dates(
    service, uow, actor, organization_id
):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "CLOSING-SLOT-001")
    slot_end = date.today() + timedelta(days=30)
    slot = add_slot(
        uow,
        organization_id,
        status="closing",
        effective_to=slot_end,
    )

    assignment = await service.create_assignment(
        actor,
        CreateAssignmentCommand(
            employee_id=employee.employee.id,
            staffing_slot_id=slot.id,
            assignment_type=AssignmentType.TEMPORARY,
            full_time_equivalent=Decimal("1"),
            effective_from=date.today(),
            effective_to=slot_end,
        ),
    )

    assert assignment.staffing_slot_id == slot.id


@pytest.mark.asyncio
async def test_ended_assignment_cannot_be_reactivated_by_a_later_end_date(
    service, uow, actor, organization_id
):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "END-ONCE-001")
    slot = add_slot(uow, organization_id)
    assignment = await service.create_assignment(
        actor,
        CreateAssignmentCommand(
            employee_id=employee.employee.id,
            staffing_slot_id=slot.id,
            assignment_type=AssignmentType.PERMANENT,
            full_time_equivalent=Decimal("1"),
            effective_from=date.today() - timedelta(days=5),
        ),
    )
    ended = await service.end_assignment(
        actor,
        EndAssignmentCommand(
            assignment_id=assignment.id,
            effective_to=date.today(),
            revision=assignment.revision,
            reason="Assignment completed",
        ),
    )

    with pytest.raises(EmployeeDomainError) as caught:
        await service.end_assignment(
            actor,
            EndAssignmentCommand(
                assignment_id=ended.id,
                effective_to=date.today() + timedelta(days=30),
                revision=ended.revision,
                reason="Attempt to reopen history",
            ),
        )

    assert caught.value.code == "VERSION_CONFLICT"
    assert ended.status is AssignmentStatus.ENDED
    assert ended.effective_to == date.today()


@pytest.mark.asyncio
async def test_assignment_rejects_draft_and_inapplicable_structure_slots(
    service, uow, actor, organization_id
):  # type: ignore[no-untyped-def]
    employee = await create_employee(service, actor, "STRUCTURE-001")
    start = date.today()
    draft_slot = add_slot(uow, organization_id, structure_status="draft")
    expired_slot = add_slot(
        uow,
        organization_id,
        structure_effective_to=start - timedelta(days=1),
    )
    for slot in (draft_slot, expired_slot):
        with pytest.raises(EmployeeDomainError) as caught:
            await service.create_assignment(
                actor,
                CreateAssignmentCommand(
                    employee_id=employee.employee.id,
                    staffing_slot_id=slot.id,
                    assignment_type=AssignmentType.PERMANENT,
                    full_time_equivalent=Decimal("1"),
                    effective_from=start,
                ),
            )
        assert caught.value.code == "STAFFING_SLOT_NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_scoped_actor_cannot_delegate_another_employees_authority(
    service, actor, organization_id
):  # type: ignore[no-untyped-def]
    delegator = await create_employee(service, actor, "DELEGATOR-001")
    delegate = await create_employee(service, actor, "DELEGATE-001")
    scoped_actor = Actor(
        user_id=uuid4(),
        employee_id=delegate.employee.id,
        organization_id=organization_id,
        permissions=frozenset({"delegations.manage", "employees.read"}),
        accessible_unit_ids=frozenset({uuid4()}),
    )
    now = datetime.now(UTC)
    with pytest.raises(EmployeeDomainError) as caught:
        await service.create_delegation(
            scoped_actor,
            CreateDelegationCommand(
                delegator_employee_id=delegator.employee.id,
                delegate_employee_id=delegate.employee.id,
                scope_type=DelegationScopeType.PERMISSIONS,
                scope_reference=None,
                delegated_permissions=("employees.read",),
                effective_from=now,
                effective_to=now + timedelta(days=1),
                reason="Invalid authority transfer",
            ),
        )
    assert caught.value.code == "AUTH_SCOPE_VIOLATION"
