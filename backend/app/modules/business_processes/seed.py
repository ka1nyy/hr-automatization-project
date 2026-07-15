"""Deterministic seed data for the integrated frontend's vertical workflows."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.employees.infrastructure.models import EmployeeModel, PersonModel

from .application.service import HIRING_ROUTE, LEAVE_ROUTE
from .infrastructure.models import (
    CorrespondenceModel,
    LeaveRequestModel,
    ProcessDefinitionModel,
    WorkTaskModel,
)

NAMESPACE = UUID("2db70c57-e03c-46a3-8ec9-1f3f74aa89be")


def _id(value: str) -> UUID:
    return uuid5(NAMESPACE, value)


async def _insert(
    session: AsyncSession, model: type[object], rows: list[dict[str, object]]
) -> None:
    if rows:
        await session.execute(insert(model).values(rows).on_conflict_do_nothing())


async def seed_business_processes(session: AsyncSession) -> None:
    now = datetime(2026, 7, 15, 8, 0, tzinfo=UTC)
    today = date(2026, 7, 15)
    employee_rows = (
        await session.execute(
            select(EmployeeModel.id, PersonModel.display_name)
            .join(PersonModel, PersonModel.id == EmployeeModel.person_id)
            .order_by(EmployeeModel.employee_number)
            .limit(3)
        )
    ).all()
    await _insert(
        session,
        ProcessDefinitionModel,
        [
            {
                "id": "p-incoming",
                "name": "Incoming correspondence",
                "version": 7,
                "state": "published",
                "active_instances": 2,
                "owner": "Secretariat",
                "steps": [
                    "Registration",
                    "Resolution",
                    "Execution",
                    "Approval",
                    "Signature",
                    "Dispatch",
                ],
                "updated_at": now,
                "revision": 1,
            },
            {
                "id": "p-hr-leave",
                "name": "Leave request",
                "version": 1,
                "state": "published",
                "active_instances": 2,
                "owner": "Департамент документационного обеспечения и управления персоналом",
                "steps": ["Employee", "Manager", "HR", "Signer", "Accounting"],
                "updated_at": now,
                "revision": 1,
            },
            {
                "id": "p-hiring",
                "name": "Recruitment and hiring",
                "version": 1,
                "state": "published",
                "active_instances": 0,
                "owner": "Департамент документационного обеспечения и управления персоналом",
                "steps": HIRING_ROUTE["steps"],
                "updated_at": now,
                "revision": 1,
            },
        ],
    )
    correspondence = [
        {
            "id": _id("correspondence-1"),
            "number": "IN-2026-000001",
            "sender": "Akimat of Pavlodar Region",
            "sender_number": "12-4/1842",
            "sender_date": today - timedelta(days=2),
            "received_at": now,
            "subject": "Information on the regional development plan",
            "summary": "Please provide the current implementation status and supporting materials.",
            "document_type": "Official letter",
            "channel": "Electronic document exchange",
            "department": "Strategy",
            "executive": "Chairman of the Board",
            "executor": "Not assigned",
            "due_date": today + timedelta(days=5),
            "priority": "high",
            "status": "registered",
            "workflow_step": "Registration completed",
            "confidentiality": "internal",
            "response_required": True,
            "attachments": [],
            "tags": ["planning"],
            "audit_log": [
                {
                    "id": str(_id("audit-correspondence-1")),
                    "at": now.isoformat(),
                    "actor": "secretary",
                    "action": "Registered",
                    "detail": "Registry assigned IN-2026-000001",
                }
            ],
            "created_at": now,
            "updated_at": now,
            "revision": 1,
        },
        {
            "id": _id("correspondence-2"),
            "number": "IN-2026-000002",
            "sender": "Ministry of National Economy",
            "sender_number": "08-15/721",
            "sender_date": today - timedelta(days=1),
            "received_at": now + timedelta(minutes=20),
            "subject": "Request for investment project data",
            "summary": "A consolidated response is required within the stated deadline.",
            "document_type": "Request",
            "channel": "Email",
            "department": "Investments",
            "executive": "Deputy Chairman",
            "executor": "Investment analyst",
            "due_date": today + timedelta(days=2),
            "priority": "urgent",
            "status": "resolution",
            "workflow_step": "Executive resolution",
            "confidentiality": "restricted",
            "response_required": True,
            "attachments": [],
            "tags": ["investment"],
            "audit_log": [
                {
                    "id": str(_id("audit-correspondence-2")),
                    "at": now.isoformat(),
                    "actor": "secretary",
                    "action": "Sent for resolution",
                    "detail": "Executive task created",
                }
            ],
            "created_at": now,
            "updated_at": now,
            "revision": 1,
        },
    ]
    await _insert(session, CorrespondenceModel, correspondence)
    tasks = [
        {
            "id": _id("task-1"),
            "title": "Prepare resolution for investment data request",
            "document_number": "IN-2026-000002",
            "process": "Incoming correspondence",
            "role": "Executive",
            "department": "Investments",
            "due_date": today + timedelta(days=1),
            "priority": "urgent",
            "state": "available",
            "assignee": None,
            "source_type": "correspondence",
            "source_id": _id("correspondence-2"),
            "created_at": now,
            "updated_at": now,
            "revision": 1,
        },
        {
            "id": _id("task-2"),
            "title": "Check personnel-file completeness",
            "document_number": "HR-CHECK-2026-001",
            "process": "HR administration",
            "role": "HR specialist",
            "department": "HR",
            "due_date": today - timedelta(days=1),
            "priority": "high",
            "state": "overdue",
            "assignee": "hr",
            "source_type": "employee",
            "source_id": employee_rows[0][0] if employee_rows else _id("missing-employee"),
            "created_at": now,
            "updated_at": now,
            "revision": 1,
        },
    ]
    await _insert(session, WorkTaskModel, tasks)
    if len(employee_rows) >= 2:
        await _insert(
            session,
            LeaveRequestModel,
            [
                {
                    "id": _id("leave-1"),
                    "employee_id": employee_rows[0][0],
                    "employee_name": employee_rows[0][1],
                    "leave_type": "Annual paid leave",
                    "start_date": today + timedelta(days=12),
                    "end_date": today + timedelta(days=19),
                    "days": 8,
                    "comment": "According to the approved schedule",
                    "substitute": employee_rows[1][1],
                    "status": "hr_review",
                    "document_number": "HR-LV-2026-0001",
                    "workflow_step": "HR review",
                    "route_snapshot": LEAVE_ROUTE,
                    "audit_log": [
                        {
                            "id": str(_id("audit-leave-1")),
                            "at": now.isoformat(),
                            "actor": employee_rows[0][1],
                            "action": "Request created",
                            "detail": "Manager approved; waiting for HR",
                        }
                    ],
                    "created_at": now,
                    "updated_at": now,
                    "revision": 1,
                },
                {
                    "id": _id("leave-2"),
                    "employee_id": employee_rows[1][0],
                    "employee_name": employee_rows[1][1],
                    "leave_type": "Annual paid leave",
                    "start_date": today + timedelta(days=40),
                    "end_date": today + timedelta(days=45),
                    "days": 6,
                    "comment": "Planned leave",
                    "substitute": employee_rows[0][1],
                    "status": "pending_manager",
                    "document_number": "HR-LV-2026-0002",
                    "workflow_step": "Manager approval",
                    "route_snapshot": LEAVE_ROUTE,
                    "audit_log": [
                        {
                            "id": str(_id("audit-leave-2")),
                            "at": now.isoformat(),
                            "actor": employee_rows[1][1],
                            "action": "Request created",
                            "detail": "Manager task created",
                        }
                    ],
                    "created_at": now,
                    "updated_at": now,
                    "revision": 1,
                },
            ],
        )
