"""Async persistence operations for timesheets."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ResourceNotFoundError

from .models import TimesheetEntryModel, TimesheetPeriodModel

_MUTABLE_PERIOD_STATUSES = ("open", "under_review", "reopened")


class SqlAlchemyTimesheetOperations:
    """Timesheet period and entry reads."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def require_period_organization(self, period_id: UUID, organization_id: UUID) -> None:
        async with self._sessions() as session:
            actual = await session.scalar(
                select(TimesheetPeriodModel.organization_id).where(
                    TimesheetPeriodModel.id == period_id
                )
            )
            if actual != organization_id:
                raise ResourceNotFoundError("timesheet period", period_id)

    async def get_period(self, period_id: UUID) -> TimesheetPeriodModel:
        async with self._sessions() as session:
            period = await session.get(TimesheetPeriodModel, period_id)
            if period is None:
                raise ResourceNotFoundError("timesheet period", period_id)
            return period

    async def find_period(
        self,
        organization_unit_id: UUID,
        period_start: date,
    ) -> TimesheetPeriodModel | None:
        async with self._sessions() as session:
            return await session.scalar(
                select(TimesheetPeriodModel).where(
                    TimesheetPeriodModel.organization_unit_id == organization_unit_id,
                    TimesheetPeriodModel.period_start == period_start,
                )
            )

    async def period_accepts_edits(self, period_id: UUID) -> bool:
        """Whether rows may still be written directly.

        Once a period is closed or sent to accounting, section 8 requires changes to go
        through the correction process instead.
        """

        async with self._sessions() as session:
            status = await session.scalar(
                select(TimesheetPeriodModel.status).where(TimesheetPeriodModel.id == period_id)
            )
            if status is None:
                raise ResourceNotFoundError("timesheet period", period_id)
            return status in _MUTABLE_PERIOD_STATUSES

    async def list_entries(
        self,
        period_id: UUID,
        employee_id: UUID | None = None,
    ) -> Sequence[TimesheetEntryModel]:
        async with self._sessions() as session:
            stmt = select(TimesheetEntryModel).where(
                TimesheetEntryModel.timesheet_period_id == period_id
            )
            if employee_id is not None:
                stmt = stmt.where(TimesheetEntryModel.employee_id == employee_id)
            rows = await session.scalars(
                stmt.order_by(TimesheetEntryModel.employee_id, TimesheetEntryModel.entry_date)
            )
            return list(rows)

    async def hours_by_time_code(self, period_id: UUID, employee_id: UUID) -> dict[UUID, Decimal]:
        """Per-code hour totals: the shape accounting consumes once a period closes."""

        async with self._sessions() as session:
            rows = await session.execute(
                select(
                    TimesheetEntryModel.time_code_id,
                    func.coalesce(func.sum(TimesheetEntryModel.hours), 0),
                )
                .where(
                    TimesheetEntryModel.timesheet_period_id == period_id,
                    TimesheetEntryModel.employee_id == employee_id,
                )
                .group_by(TimesheetEntryModel.time_code_id)
            )
            return {code_id: Decimal(total) for code_id, total in rows.all()}
