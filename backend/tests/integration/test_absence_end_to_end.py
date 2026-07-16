from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

import pytest
from app.core.errors import ValidationError
from app.modules.absence.infrastructure.models import LeaveBalanceModel, LeaveTypeModel
from app.modules.absence.infrastructure.operations import SqlAlchemyAbsenceOperations
from app.modules.employees.infrastructure.models import EmployeeAbsenceModel
from app.modules.workflow.infrastructure.models import ProcessInstanceModel, WorkflowTaskModel
from app.seed import ORGANIZATION_ID, _development_user_id, _seed_id
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integration


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _future_weekday(days: int) -> date:
    result = date.today() + timedelta(days=days)
    while result.weekday() >= 5:
        result += timedelta(days=1)
    return result


@pytest.mark.asyncio
async def test_leave_return_resubmit_approval_is_atomic_and_idempotent(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyAbsenceOperations(factory)
    employee = _seed_id("employee", "development-employee")
    employee_user = _development_user_id("employee")
    hr = _development_user_id("hr")
    async with factory() as session:
        leave_type = await session.scalar(
            select(LeaveTypeModel).where(LeaveTypeModel.code == "annual_paid")
        )
    assert leave_type is not None
    start = _future_weekday(60)
    end = start + timedelta(days=2)
    request = await operations.create_leave(
        ORGANIZATION_ID,
        employee_user,
        {
            "employeeId": employee,
            "leaveTypeId": leave_type.id,
            "startDate": start,
            "endDate": end,
            "reason": "Annual rest",
        },
    )
    process_id = UUID(str(request["process_instance_id"]))
    async with factory() as session:
        manager = await session.scalar(
            select(WorkflowTaskModel.assigned_user_id).where(
                WorkflowTaskModel.process_instance_id == process_id,
                WorkflowTaskModel.status == "active",
            )
        )
    assert manager is not None
    first_revision = int(request["revision"])
    returned = await operations.decide_leave(
        UUID(str(request["id"])), manager, first_revision, "manager_review", "return", "Move dates"
    )
    assert returned["status"] == "returned"
    corrected_start = start + timedelta(days=7)
    corrected_end = corrected_start + timedelta(days=2)
    request = await operations.resubmit_leave(
        UUID(str(request["id"])),
        employee_user,
        int(returned["revision"]),
        {"startDate": corrected_start, "endDate": corrected_end, "reason": "Moved"},
    )
    assert request["status"] == "manager_review"
    manager_revision = int(request["revision"])
    request = await operations.decide_leave(
        UUID(str(request["id"])),
        manager,
        manager_revision,
        "manager_review",
        "approve",
        "Approved",
    )
    duplicate = await operations.decide_leave(
        UUID(str(request["id"])),
        manager,
        manager_revision,
        "manager_review",
        "approve",
        "Approved",
    )
    assert duplicate["revision"] == request["revision"]
    approved = await operations.decide_leave(
        UUID(str(request["id"])),
        hr,
        int(request["revision"]),
        "hr_review",
        "approve",
        "Registered",
    )
    assert approved["status"] == "approved"
    async with factory() as session:
        process = await session.get(ProcessInstanceModel, process_id)
        tasks = (
            await session.scalars(
                select(WorkflowTaskModel)
                .where(WorkflowTaskModel.process_instance_id == process_id)
                .order_by(WorkflowTaskModel.created_at)
            )
        ).all()
        balance = await session.scalar(
            select(LeaveBalanceModel).where(
                LeaveBalanceModel.employee_id == employee,
                LeaveBalanceModel.leave_type_id == leave_type.id,
                LeaveBalanceModel.year == corrected_start.year,
            )
        )
        calendar_absence = await session.scalar(
            select(EmployeeAbsenceModel).where(
                EmployeeAbsenceModel.source_type == "leave_request",
                EmployeeAbsenceModel.source_id == request["id"],
            )
        )
    assert process is not None and process.status == "completed"
    assert [task.status for task in tasks] == ["completed", "completed"]
    assert balance is not None
    assert balance.reserved_days == 0
    assert balance.used_days == approved["requested_days"]
    assert calendar_absence is not None
    assert calendar_absence.absence_type == "vacation"


@pytest.mark.asyncio
async def test_insufficient_leave_rolls_back_request_process_audit_and_outbox(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyAbsenceOperations(factory)
    employee = _seed_id("employee", "development-employee")
    async with factory() as session:
        leave_type = await session.scalar(
            select(LeaveTypeModel).where(LeaveTypeModel.code == "annual_paid")
        )
        before_processes = int(
            await session.scalar(
                select(func.count())
                .select_from(ProcessInstanceModel)
                .where(ProcessInstanceModel.business_type == "leaveRequest")
            )
            or 0
        )
    assert leave_type is not None
    start = _future_weekday(120)
    with pytest.raises(ValidationError) as error:
        await operations.create_leave(
            ORGANIZATION_ID,
            _development_user_id("employee"),
            {
                "employeeId": employee,
                "leaveTypeId": leave_type.id,
                "startDate": start,
                "endDate": start + timedelta(days=40),
                "reason": "Too long",
            },
        )
    assert error.value.code.value == "LEAVE_BALANCE_INSUFFICIENT"
    async with factory() as session:
        after_processes = int(
            await session.scalar(
                select(func.count())
                .select_from(ProcessInstanceModel)
                .where(ProcessInstanceModel.business_type == "leaveRequest")
            )
            or 0
        )
    assert after_processes == before_processes


@pytest.mark.asyncio
async def test_business_trip_creates_sequential_tasks_and_cancellation_closes_them(
    seeded_database: AsyncEngine,
) -> None:
    factory = _factory(seeded_database)
    operations = SqlAlchemyAbsenceOperations(factory)
    employee = _seed_id("employee", "development-director")
    start = _future_weekday(180)
    trip = await operations.create_trip(
        ORGANIZATION_ID,
        _development_user_id("director"),
        {
            "employeeId": employee,
            "destination": "Astana",
            "startDate": start,
            "endDate": start + timedelta(days=2),
            "purpose": "Negotiations",
            "estimatedCost": "250000.00",
            "currency": "KZT",
            "fundingDetails": {"costCenter": "ADMIN"},
        },
    )
    process_id = UUID(str(trip["process_instance_id"]))
    async with factory() as session:
        manager = await session.scalar(
            select(WorkflowTaskModel.assigned_user_id).where(
                WorkflowTaskModel.process_instance_id == process_id,
                WorkflowTaskModel.status == "active",
            )
        )
    assert manager is not None
    trip = await operations.decide_trip(
        UUID(str(trip["id"])),
        manager,
        int(trip["revision"]),
        "manager_review",
        "approve",
        "Approved",
    )
    assert trip["status"] == "finance_review"
    trip = await operations.decide_trip(
        UUID(str(trip["id"])),
        _development_user_id("admin"),
        int(trip["revision"]),
        "finance_review",
        "approve",
        "Budget confirmed",
    )
    assert trip["status"] == "hr_registration"
    cancelled = await operations.cancel_trip(
        UUID(str(trip["id"])),
        _development_user_id("director"),
        int(trip["revision"]),
        "Meeting cancelled",
    )
    async with factory() as session:
        process = await session.get(ProcessInstanceModel, process_id)
        active = int(
            await session.scalar(
                select(func.count())
                .select_from(WorkflowTaskModel)
                .where(
                    WorkflowTaskModel.process_instance_id == process_id,
                    WorkflowTaskModel.status.in_(("active", "pending")),
                )
            )
            or 0
        )
    assert cancelled["status"] == "cancelled"
    assert process is not None and process.status == "cancelled"
    assert active == 0

    registered_start = start + timedelta(days=10)
    registered = await operations.create_trip(
        ORGANIZATION_ID,
        _development_user_id("director"),
        {
            "employeeId": employee,
            "destination": "Almaty",
            "startDate": registered_start,
            "endDate": registered_start + timedelta(days=2),
            "purpose": "Board meeting",
            "estimatedCost": "180000.00",
            "currency": "KZT",
            "fundingDetails": {},
        },
    )
    registered_process_id = UUID(str(registered["process_instance_id"]))
    for stage in ("manager_review", "finance_review", "hr_registration"):
        async with factory() as session:
            actor = await session.scalar(
                select(WorkflowTaskModel.assigned_user_id).where(
                    WorkflowTaskModel.process_instance_id == registered_process_id,
                    WorkflowTaskModel.status == "active",
                )
            )
        assert actor is not None
        registered = await operations.decide_trip(
            UUID(str(registered["id"])),
            actor,
            int(registered["revision"]),
            stage,
            "approve",
            "Approved",
        )
    async with factory() as session:
        registered_process = await session.get(ProcessInstanceModel, registered_process_id)
        registered_absence = await session.scalar(
            select(EmployeeAbsenceModel).where(
                EmployeeAbsenceModel.source_type == "business_trip_request",
                EmployeeAbsenceModel.source_id == registered["id"],
            )
        )
    assert registered["status"] == "registered"
    assert registered_process is not None and registered_process.status == "completed"
    assert registered_absence is not None
    assert registered_absence.absence_type == "business_trip"
