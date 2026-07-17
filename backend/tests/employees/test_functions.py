"""Business-function registry, availability rules, and invocation behavior."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from app.modules.employees.application.functions import (
    EmployeeFunctionService,
    default_employee_function_registry,
)
from app.modules.employees.application.ports import Actor, StaffingSlotSnapshot
from app.modules.employees.application.service import EmployeeService
from app.modules.employees.domain.enums import AssignmentStatus, EmploymentStatus
from app.modules.employees.domain.errors import EmployeeDomainError

from .fakes import FakeUnitOfWork, TestProtector

ALL_FUNCTION_PERMISSIONS = frozenset(
    {
        "employees.read",
        "employees.hire",
        "employees.terminate",
        "employees.transfer",
    }
)


@pytest.fixture
def organization_id():  # type: ignore[no-untyped-def]
    return uuid4()


@pytest.fixture
def actor(organization_id):  # type: ignore[no-untyped-def]
    return Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=ALL_FUNCTION_PERMISSIONS,
        organization_wide=True,
    )


@pytest.fixture
def uow():  # type: ignore[no-untyped-def]
    return FakeUnitOfWork()


@pytest.fixture
def functions(uow):  # type: ignore[no-untyped-def]
    return EmployeeFunctionService(
        default_employee_function_registry(),
        EmployeeService(uow, TestProtector()),
    )


def add_slot(uow: FakeUnitOfWork, organization_id, *, fte: str = "1.0"):  # type: ignore[no-untyped-def]
    slot = StaffingSlotSnapshot(
        id=uuid4(),
        organization_id=organization_id,
        organization_unit_id=uuid4(),
        structure_version_id=uuid4(),
        full_time_equivalent=Decimal(fte),
        status="vacant",
        effective_from=date(2025, 1, 1),
        effective_to=None,
    )
    uow.staffing_slots.items[slot.id] = slot
    return slot


def hire_payload(slot_id, number: str = "F-001") -> dict:  # type: ignore[no-untyped-def]
    return {
        "firstName": "Aigerim",
        "lastName": "Bekova",
        "employeeNumber": number,
        "hireDate": "2026-01-01",
        "staffingSlotId": str(slot_id),
    }


async def hire(functions, actor, uow, organization_id, number: str = "F-001"):  # type: ignore[no-untyped-def]
    slot = add_slot(uow, organization_id)
    details = await functions.invoke_collection_function(
        actor, "employee.hire", hire_payload(slot.id, number)
    )
    return details, slot


@pytest.mark.asyncio
async def test_hire_creates_active_employee_with_primary_assignment(
    functions, actor, uow, organization_id
):  # type: ignore[no-untyped-def]
    details, slot = await hire(functions, actor, uow, organization_id)
    assert details.employee.employment_status is EmploymentStatus.ACTIVE
    assert details.assignments[0].primary is True
    assert details.assignments[0].staffing_slot_id == slot.id
    assert details.assignments[0].status is AssignmentStatus.ACTIVE
    assert uow.audit.items[-1].action == "employee.hired"
    assert uow.outbox.items[-1].event_type == "employeeHired"


@pytest.mark.asyncio
async def test_hire_requires_permission(functions, uow, organization_id):  # type: ignore[no-untyped-def]
    reader = Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset({"employees.read"}),
        organization_wide=True,
    )
    slot = add_slot(uow, organization_id)
    assert functions.list_collection_functions(reader) == ()
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_collection_function(reader, "employee.hire", hire_payload(slot.id))
    assert caught.value.code == "AUTH_FORBIDDEN"


@pytest.mark.asyncio
async def test_available_functions_follow_permissions_and_state(
    functions, actor, uow, organization_id
):  # type: ignore[no-untyped-def]
    details, _slot = await hire(functions, actor, uow, organization_id)
    keys = {
        item.key for item in await functions.list_employee_functions(actor, details.employee.id)
    }
    assert keys == {"employee.transfer"}

    reader = Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset({"employees.read"}),
        organization_wide=True,
    )
    assert await functions.list_employee_functions(reader, details.employee.id) == ()


@pytest.mark.asyncio
async def test_terminate_ends_employment_and_assignments(functions, actor, uow, organization_id):  # type: ignore[no-untyped-def]
    details, _slot = await hire(functions, actor, uow, organization_id)
    employee_id = details.employee.id
    employee_number = details.employee.employee_number
    result = await functions.invoke_employee_function(
        actor,
        employee_id,
        "employee.terminate",
        {
            "terminationDate": date.today().isoformat(),
            "reason": "Сокращение штата",
            "revision": details.employee.revision,
        },
    )
    assert result.employee.employment_status is EmploymentStatus.ENDED
    assert result.employee.active is False
    assert result.employee.employee_number == employee_number
    assignment = next(iter(uow.assignments.items.values()))
    assert assignment.effective_to == date.today()
    assert uow.audit.items[-1].action == "employee.terminated"
    # The employee's state now hides both employee-scope functions.
    assert await functions.list_employee_functions(actor, employee_id) == ()
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_employee_function(
            actor,
            employee_id,
            "employee.terminate",
            {
                "terminationDate": date.today().isoformat(),
                "reason": "Повторно",
                "revision": result.employee.revision,
            },
        )
    assert caught.value.code == "VERSION_CONFLICT"


@pytest.mark.asyncio
async def test_scheduled_termination_keeps_employee_active_until_date(
    functions, actor, uow, organization_id
):  # type: ignore[no-untyped-def]
    details, _slot = await hire(functions, actor, uow, organization_id)
    future = date.today() + timedelta(days=30)
    result = await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.terminate",
        {
            "terminationDate": future.isoformat(),
            "reason": "Окончание контракта",
            "revision": details.employee.revision,
        },
    )
    assert result.employee.active is True
    assert result.employee.employment_status is EmploymentStatus.ACTIVE
    assert result.employee.termination_date == future
    assignment = next(iter(uow.assignments.items.values()))
    assert assignment.status is AssignmentStatus.SCHEDULED_END
    assert uow.audit.items[-1].action == "employee.termination.scheduled"


@pytest.mark.asyncio
async def test_transfer_moves_primary_assignment_atomically(functions, actor, uow, organization_id):  # type: ignore[no-untyped-def]
    details, source_slot = await hire(functions, actor, uow, organization_id)
    target_slot = add_slot(uow, organization_id)
    effective_from = date.today() + timedelta(days=1)
    result = await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.transfer",
        {
            "staffingSlotId": str(target_slot.id),
            "effectiveFrom": effective_from.isoformat(),
            "reason": "Перевод в другой отдел",
        },
    )
    by_slot = {item.staffing_slot_id: item for item in result.assignments}
    assert by_slot[source_slot.id].effective_to == effective_from - timedelta(days=1)
    assert by_slot[target_slot.id].primary is True
    assert by_slot[target_slot.id].effective_from == effective_from
    assert uow.audit.items[-1].action == "employee.transferred"
    assert uow.outbox.items[-1].event_type == "employeeTransferred"


@pytest.mark.asyncio
async def test_transfer_to_current_slot_is_rejected(functions, actor, uow, organization_id):  # type: ignore[no-untyped-def]
    details, source_slot = await hire(functions, actor, uow, organization_id)
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_employee_function(
            actor,
            details.employee.id,
            "employee.transfer",
            {
                "staffingSlotId": str(source_slot.id),
                "effectiveFrom": (date.today() + timedelta(days=1)).isoformat(),
                "reason": "Перевод",
            },
        )
    assert caught.value.code == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_unknown_function_key_is_not_found(functions, actor):  # type: ignore[no-untyped-def]
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_collection_function(actor, "employee.promote", {})
    assert caught.value.code == "RESOURCE_NOT_FOUND"
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_scope_mismatch_is_rejected(functions, actor, uow, organization_id):  # type: ignore[no-untyped-def]
    details, _slot = await hire(functions, actor, uow, organization_id)
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_collection_function(actor, "employee.terminate", {})
    assert caught.value.code == "VALIDATION_FAILED"
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_employee_function(actor, details.employee.id, "employee.hire", {})
    assert caught.value.code == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_invalid_payload_reports_field_problems(functions, actor, uow, organization_id):  # type: ignore[no-untyped-def]
    details, _slot = await hire(functions, actor, uow, organization_id)
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_employee_function(
            actor,
            details.employee.id,
            "employee.terminate",
            {"reason": "Без даты", "revision": 1, "unexpected": True},
        )
    assert caught.value.code == "VALIDATION_FAILED"
    fields = {problem["field"] for problem in caught.value.details["problems"]}
    assert "terminationDate" in fields
    assert "unexpected" in fields
