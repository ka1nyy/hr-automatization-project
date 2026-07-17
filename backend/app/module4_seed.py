"""Deterministic, idempotent reference configuration and storage seed for Module 4.

Covers the timesheet reference data an organization must have before any time can be
recorded: timesheet codes, working-time schedules, an open period per demo unit, and
the document types and order templates the leave and correction processes emit.

Leave types and balances belong to :mod:`app.modules.absence` and are not seeded here.

Everything here is configuration the customer edits in the interface later (sections 2
and 12 of the MVP plan) — the values are a working starting point, not a commitment.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.modules.documents.application.ports import DocumentStoragePort
from app.modules.documents.infrastructure.models import (
    DocumentTemplateModel,
    DocumentTemplateVersionModel,
    DocumentTypeModel,
)
from app.modules.timekeeping.infrastructure.models import (
    EmployeeWorkScheduleModel,
    TimeCodeModel,
    TimesheetPeriodModel,
    WorkScheduleDayModel,
    WorkScheduleModel,
)

# code, external code, name, category, paid, counts as worked time.
#
# ``code`` follows this repository's snake_case convention; ``external_code`` carries the
# single-letter mark accounting expects on a Kazakh timesheet.  Section 12 lists timesheet
# codes as something to confirm with SPK, so both columns are configuration.
TIME_CODES: tuple[tuple[str, str, str, str, bool, bool], ...] = (
    ("work", "Я", "Worked day", "work", True, True),
    ("overtime", "С", "Overtime hours", "overtime", True, True),
    ("night", "Н", "Night hours", "night", True, True),
    ("holiday_work", "РП", "Work on a holiday or rest day", "holiday", True, True),
    ("weekend", "В", "Weekend or non-working holiday", "weekend", False, False),
    ("annual_leave", "ОТ", "Annual paid leave", "leave", True, False),
    ("unpaid_leave", "ДО", "Leave without pay", "unpaid_absence", False, False),
    ("study_leave", "У", "Study leave", "leave", True, False),
    ("parental_leave", "Р", "Parental leave", "leave", False, False),
    ("sick_leave", "Б", "Certified sick leave", "sick", True, False),
    ("business_trip", "К", "Business trip", "business_trip", True, True),
    ("day_off", "ОВ", "Approved day off", "absence", False, False),
    ("absence_unexcused", "ПР", "Unexcused absence", "unpaid_absence", False, False),
)

# code, name, kind, cycle length, weekly hours, working-day count.
WORK_SCHEDULES: tuple[tuple[str, str, str, int, Decimal, int], ...] = (
    ("five_day_40", "Five-day week, 40 hours", "five_day", 7, Decimal("40"), 5),
    ("six_day_40", "Six-day week, 40 hours", "six_day", 7, Decimal("40"), 6),
)

DOCUMENT_TYPES: tuple[tuple[str, str, str], ...] = (
    ("leave_request", "Leave request", "internal"),
    ("leave_order", "Leave order", "internal"),
    ("sick_leave_certificate", "Sick leave certificate", "restricted"),
    ("timesheet_register", "Timesheet register", "internal"),
    ("timesheet_correction_request", "Timesheet correction request", "internal"),
)

LEAVE_ORDER_TEMPLATE = """АО «СПК «Ертіс»

ПРИКАЗ № {{orderNumber}}
от {{orderDate}}

О предоставлении отпуска

ПРИКАЗЫВАЮ:

1. Предоставить {{employeeName}}, {{positionName}}, {{unitName}},
   {{leaveTypeName}} продолжительностью {{leaveDays}} календарных дней
   с {{dateFrom}} по {{dateTo}}.

2. Основание: {{basis}}.

3. На период отсутствия обязанности возложить на: {{substituteName}}.

4. Бухгалтерии произвести расчёт в соответствии с законодательством
   Республики Казахстан.

Подписант: {{signatoryName}}, {{signatoryPosition}}

С приказом ознакомлен: ______________ / {{employeeName}} /
"""

TIMESHEET_CORRECTION_TEMPLATE = """АО «СПК «Ертіс»

ЗАПРОС НА ИСПРАВЛЕНИЕ ТАБЕЛЯ № {{requestNumber}}
от {{requestDate}}

Подразделение: {{unitName}}
Табельный период: {{periodStart}} — {{periodEnd}}
Сотрудник: {{employeeName}}
Дата: {{entryDate}}

Было:  код {{previousTimeCode}}, часов {{previousHours}}
Стало: код {{requestedTimeCode}}, часов {{requestedHours}}

Причина исправления: {{reason}}

Инициатор: {{requestedByName}}
Согласовал руководитель: {{managerName}}
Проверил HR: {{hrName}}
"""

# template code, document type code, name, body, variable names.
TEMPLATES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (
        "leave_order_ru",
        "leave_order",
        "Leave order (RU)",
        LEAVE_ORDER_TEMPLATE,
        (
            "orderNumber",
            "orderDate",
            "employeeName",
            "positionName",
            "unitName",
            "leaveTypeName",
            "leaveDays",
            "dateFrom",
            "dateTo",
            "basis",
            "substituteName",
            "signatoryName",
            "signatoryPosition",
        ),
    ),
    (
        "timesheet_correction_ru",
        "timesheet_correction_request",
        "Timesheet correction request (RU)",
        TIMESHEET_CORRECTION_TEMPLATE,
        (
            "requestNumber",
            "requestDate",
            "unitName",
            "periodStart",
            "periodEnd",
            "employeeName",
            "entryDate",
            "previousTimeCode",
            "previousHours",
            "requestedTimeCode",
            "requestedHours",
            "reason",
            "requestedByName",
            "managerName",
            "hrName",
        ),
    ),
)

TEMPLATE_MIME_TYPE = "text/plain; charset=utf-8"


def _template_storage_key(organization_id: UUID, template_code: str) -> str:
    return f"templates/{organization_id}/module4/{template_code}.v1.txt"


async def _storage_key_exists(storage: DocumentStoragePort, storage_key: str) -> bool:
    """Whether an object is already present.

    The local adapter creates files exclusively and fails on a second write, so the seed
    checks before storing to stay re-runnable.
    """

    try:
        async for _ in storage.read(storage_key):
            break
    except ApplicationError:
        return False
    return True


async def _store_template(
    storage: DocumentStoragePort,
    *,
    storage_key: str,
    body: bytes,
) -> None:
    if await _storage_key_exists(storage, storage_key):
        return

    async def content() -> AsyncIterator[bytes]:
        yield body

    await storage.store(
        storage_key=storage_key,
        content=content(),
        content_type=TEMPLATE_MIME_TYPE,
        metadata={"seed": "module4"},
    )


def _month_bounds(moment: date) -> tuple[date, date]:
    start = moment.replace(day=1)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return start, date.fromordinal(end.toordinal() - 1)


async def seed_module4(
    session: AsyncSession,
    *,
    organization_id: UUID,
    actor_id: UUID,
    timestamp: datetime,
    seed_id: Any,
    insert_rows: Any,
    storage: DocumentStoragePort,
    employee_ids: Sequence[UUID],
    unit_ids: Sequence[UUID],
    effective_from: date,
    today: date | None = None,
) -> None:
    today = today or datetime.now(tz=UTC).date()

    await insert_rows(
        session,
        TimeCodeModel.__table__,
        [
            {
                "id": seed_id("time-code", code),
                "organization_id": organization_id,
                "code": code,
                "name": name,
                "category": category,
                "paid": paid,
                "counts_as_worked_time": worked,
                "external_code": external_code,
                "active": True,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            for code, external_code, name, category, paid, worked in TIME_CODES
        ],
    )
    await insert_rows(
        session,
        WorkScheduleModel.__table__,
        [
            {
                "id": seed_id("work-schedule", code),
                "organization_id": organization_id,
                "code": code,
                "name": name,
                "kind": kind,
                "cycle_length_days": cycle_length,
                "weekly_hours": weekly_hours,
                "default_time_code_id": seed_id("time-code", "work"),
                "active": True,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            for code, name, kind, cycle_length, weekly_hours, _working_days in WORK_SCHEDULES
        ],
    )

    schedule_days: list[dict[str, Any]] = []
    for code, _name, _kind, cycle_length, weekly_hours, working_days in WORK_SCHEDULES:
        daily_hours = (weekly_hours / working_days).quantize(Decimal("0.01"))
        for cycle_day in range(cycle_length):
            working = cycle_day < working_days
            schedule_days.append(
                {
                    "id": seed_id("work-schedule-day", f"{code}:{cycle_day}"),
                    "work_schedule_id": seed_id("work-schedule", code),
                    "cycle_day": cycle_day,
                    "working_day": working,
                    "hours": daily_hours if working else Decimal("0"),
                    "starts_at_minute": 9 * 60 if working else None,
                    "time_code_id": seed_id("time-code", "work" if working else "weekend"),
                    "revision": 1,
                }
            )
    await insert_rows(session, WorkScheduleDayModel.__table__, schedule_days)

    await insert_rows(
        session,
        EmployeeWorkScheduleModel.__table__,
        [
            {
                "id": seed_id("employee-work-schedule", str(employee_id)),
                "employee_id": employee_id,
                "work_schedule_id": seed_id("work-schedule", "five_day_40"),
                "effective_from": effective_from,
                "effective_to": None,
                "cycle_anchor_date": effective_from,
                "assigned_by_user_id": actor_id,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            for employee_id in employee_ids
        ],
    )

    await insert_rows(
        session,
        DocumentTypeModel.__table__,
        [
            {
                "id": seed_id("document-type", code),
                "organization_id": organization_id,
                "code": code,
                "name": name,
                "description": None,
                "default_confidentiality": confidentiality,
                "allowed_mime_types": [
                    "application/pdf",
                    "image/png",
                    "image/jpeg",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ],
                "maximum_size_bytes": 10_485_760,
                "active": True,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            for code, name, confidentiality in DOCUMENT_TYPES
        ],
    )

    template_rows: list[dict[str, Any]] = []
    template_version_rows: list[dict[str, Any]] = []
    for template_code, document_type_code, name, body, variables in TEMPLATES:
        encoded = body.encode("utf-8")
        storage_key = _template_storage_key(organization_id, template_code)
        await _store_template(storage, storage_key=storage_key, body=encoded)
        template_rows.append(
            {
                "id": seed_id("document-template", template_code),
                "organization_id": organization_id,
                "document_type_id": seed_id("document-type", document_type_code),
                "code": template_code,
                "name": name,
                "active": True,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        template_version_rows.append(
            {
                "id": seed_id("document-template-version", f"{template_code}:1"),
                "template_id": seed_id("document-template", template_code),
                "version_number": 1,
                "status": "published",
                "based_on_version_id": None,
                "storage_key": storage_key,
                "content_sha256": hashlib.sha256(encoded).hexdigest(),
                "variable_schema": {
                    variable: {"type": "string", "required": True} for variable in variables
                },
                "created_by": actor_id,
                "published_by": actor_id,
                "revision": 1,
                "created_at": timestamp,
                "published_at": timestamp,
            }
        )
    await insert_rows(session, DocumentTemplateModel.__table__, template_rows)
    await insert_rows(session, DocumentTemplateVersionModel.__table__, template_version_rows)

    # An open period for the current month gives each demo unit somewhere to record time.
    month_start, month_end = _month_bounds(today)
    await insert_rows(
        session,
        TimesheetPeriodModel.__table__,
        [
            {
                "id": seed_id("timesheet-period", f"{unit_id}:{month_start.isoformat()}"),
                "organization_id": organization_id,
                "organization_unit_id": unit_id,
                "period_start": month_start,
                "period_end": month_end,
                "status": "open",
                "manager_confirmed_at": None,
                "manager_confirmed_by_user_id": None,
                "closed_at": None,
                "closed_by_user_id": None,
                "sent_to_accounting_at": None,
                "reopened_at": None,
                "reopen_reason": None,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            for unit_id in unit_ids
        ],
    )


__all__ = ["seed_module4"]
