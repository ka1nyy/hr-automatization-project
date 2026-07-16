"""Absence functions: registration, balance, overlaps, cancellation."""

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
from app.modules.employees.domain.enums import AbsenceStatus, EmploymentStatus
from app.modules.employees.domain.errors import EmployeeDomainError

from .fakes import FakeUnitOfWork, TestProtector

ABSENCE_PERMISSIONS = frozenset(
    {
        "employees.read",
        "employees.hire",
        "employees.terminate",
        "employees.absence.vacation",
        "employees.absence.sick_leave",
        "employees.absence.business_trip",
        "employees.absence.day_off",
        "employees.absence.cancel",
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
        permissions=ABSENCE_PERMISSIONS,
        organization_wide=True,
    )


@pytest.fixture
def uow():  # type: ignore[no-untyped-def]
    return FakeUnitOfWork()


@pytest.fixture
def service(uow):  # type: ignore[no-untyped-def]
    return EmployeeService(uow, TestProtector())


@pytest.fixture
def functions(service):  # type: ignore[no-untyped-def]
    return EmployeeFunctionService(default_employee_function_registry(), service)


async def hire(functions, actor, uow, organization_id):  # type: ignore[no-untyped-def]
    slot = StaffingSlotSnapshot(
        id=uuid4(),
        organization_id=organization_id,
        organization_unit_id=uuid4(),
        structure_version_id=uuid4(),
        full_time_equivalent=Decimal("1.0"),
        status="vacant",
        effective_from=date(2025, 1, 1),
        effective_to=None,
    )
    uow.staffing_slots.items[slot.id] = slot
    return await functions.invoke_collection_function(
        actor,
        "employee.hire",
        {
            "firstName": "Айгерим",
            "lastName": "Бекова",
            "employeeNumber": "ABS-001",
            "hireDate": "2026-01-01",
            "staffingSlotId": str(slot.id),
        },
    )


def vacation_payload(date_from: date, date_to: date) -> dict:  # type: ignore[type-arg]
    return {
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
        "reason": "Ежегодный отпуск",
    }


@pytest.mark.asyncio
async def test_vacation_is_registered_and_reduces_balance(
    functions, service, actor, uow, organization_id
):  # type: ignore[no-untyped-def]
    details = await hire(functions, actor, uow, organization_id)
    year = date.today().year
    absence = await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.vacation",
        vacation_payload(date(year, 8, 1), date(year, 8, 10)),
    )
    assert absence.days == 10
    assert uow.audit.items[-1].action == "employee.absence.registered"
    assert uow.outbox.items[-1].event_type == "employeeAbsenceRegistered"
    view = await service.list_absences(actor, details.employee.id)
    assert view.vacation_balance.used == 10
    assert view.vacation_balance.remaining == 14


@pytest.mark.asyncio
async def test_vacation_over_balance_is_rejected(functions, actor, uow, organization_id):  # type: ignore[no-untyped-def]
    details = await hire(functions, actor, uow, organization_id)
    year = date.today().year
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_employee_function(
            actor,
            details.employee.id,
            "employee.vacation",
            vacation_payload(date(year, 8, 1), date(year, 8, 30)),
        )
    assert caught.value.code == "ABSENCE_BALANCE_EXCEEDED"


@pytest.mark.asyncio
async def test_overlapping_absences_are_rejected_across_types(
    functions, actor, uow, organization_id
):  # type: ignore[no-untyped-def]
    details = await hire(functions, actor, uow, organization_id)
    year = date.today().year
    await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.vacation",
        vacation_payload(date(year, 8, 1), date(year, 8, 10)),
    )
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_employee_function(
            actor,
            details.employee.id,
            "employee.business_trip",
            {
                "dateFrom": date(year, 8, 5).isoformat(),
                "dateTo": date(year, 8, 15).isoformat(),
                "reason": "Командировка в Астану",
                "details": "г. Астана",
            },
        )
    assert caught.value.code == "ABSENCE_DATE_CONFLICT"


@pytest.mark.asyncio
async def test_cancelled_absence_frees_dates_and_balance(
    functions, service, actor, uow, organization_id
):  # type: ignore[no-untyped-def]
    details = await hire(functions, actor, uow, organization_id)
    start = date.today() + timedelta(days=30)
    absence = await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.vacation",
        vacation_payload(start, start + timedelta(days=9)),
    )
    cancelled = await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.absence_cancel",
        {"absenceId": str(absence.id), "reason": "Перенос отпуска", "revision": absence.revision},
    )
    assert cancelled.status is AbsenceStatus.CANCELLED
    assert uow.audit.items[-1].action == "employee.absence.cancelled"
    view = await service.list_absences(actor, details.employee.id)
    assert view.vacation_balance.remaining == 24
    replacement = await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.vacation",
        vacation_payload(start, start + timedelta(days=9)),
    )
    assert replacement.days == 10


@pytest.mark.asyncio
async def test_completed_absence_cannot_be_cancelled(functions, actor, uow, organization_id):  # type: ignore[no-untyped-def]
    details = await hire(functions, actor, uow, organization_id)
    past_start = date.today() - timedelta(days=20)
    absence = await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.sick_leave",
        {
            "dateFrom": past_start.isoformat(),
            "dateTo": (past_start + timedelta(days=5)).isoformat(),
            "reason": "Больничный лист",
        },
    )
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_employee_function(
            actor,
            details.employee.id,
            "employee.absence_cancel",
            {"absenceId": str(absence.id), "reason": "Ошибка", "revision": absence.revision},
        )
    assert caught.value.code == "VERSION_CONFLICT"


@pytest.mark.asyncio
async def test_termination_cancels_future_absences(functions, service, actor, uow, organization_id):  # type: ignore[no-untyped-def]
    details = await hire(functions, actor, uow, organization_id)
    future = date.today() + timedelta(days=40)
    absence = await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.vacation",
        vacation_payload(future, future + timedelta(days=5)),
    )
    result = await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.terminate",
        {
            "terminationDate": date.today().isoformat(),
            "reason": "Сокращение",
            "revision": details.employee.revision,
        },
    )
    assert result.employee.employment_status is EmploymentStatus.ENDED
    assert uow.absences.items[absence.id].status is AbsenceStatus.CANCELLED


@pytest.mark.asyncio
async def test_absence_functions_hidden_for_terminated_employee(
    functions, actor, uow, organization_id
):  # type: ignore[no-untyped-def]
    details = await hire(functions, actor, uow, organization_id)
    await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.terminate",
        {
            "terminationDate": date.today().isoformat(),
            "reason": "Сокращение",
            "revision": details.employee.revision,
        },
    )
    keys = {
        item.key for item in await functions.list_employee_functions(actor, details.employee.id)
    }
    assert keys == set()


@pytest.mark.asyncio
async def test_absence_requires_type_specific_permission(functions, actor, uow, organization_id):  # type: ignore[no-untyped-def]
    details = await hire(functions, actor, uow, organization_id)
    limited = Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset({"employees.read", "employees.absence.day_off"}),
        organization_wide=True,
    )
    keys = {
        item.key for item in await functions.list_employee_functions(limited, details.employee.id)
    }
    assert keys == {"employee.day_off"}
    with pytest.raises(EmployeeDomainError) as caught:
        await functions.invoke_employee_function(
            limited,
            details.employee.id,
            "employee.vacation",
            vacation_payload(date.today(), date.today()),
        )
    assert caught.value.code == "AUTH_FORBIDDEN"


@pytest.mark.asyncio
async def test_active_absences_listing_covers_today(
    functions, service, actor, uow, organization_id
):  # type: ignore[no-untyped-def]
    details = await hire(functions, actor, uow, organization_id)
    await functions.invoke_employee_function(
        actor,
        details.employee.id,
        "employee.business_trip",
        {
            "dateFrom": date.today().isoformat(),
            "dateTo": (date.today() + timedelta(days=3)).isoformat(),
            "reason": "Командировка",
            "details": "г. Астана",
        },
    )
    active = await service.list_active_absences(actor)
    assert len(active) == 1
    assert active[0].employee_id == details.employee.id
