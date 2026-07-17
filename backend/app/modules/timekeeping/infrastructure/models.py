"""Relational schema for timesheets and working-time schedules.

Leave itself lives in :mod:`app.modules.absence`; this module covers the timesheet
half of Module 4 and reads leave only as a source of timesheet rows.

One invariant from section 8 of the MVP plan shapes the schema: a timesheet is never
typed from scratch.  ``timesheet_entries`` records the source that produced each row,
a manual row must carry a reason, and once a period closes its rows lock and change
only through ``timesheet_corrections``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.database.mixins import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TimeCodeModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    """Configurable timesheet codes, to be confirmed with SPK before go-live (section 12)."""

    __tablename__ = "time_codes"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_time_codes_organization_code"),
        Index("ix_time_codes_organization_active", "organization_id", "active"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(30))
    paid: Mapped[bool] = mapped_column(Boolean, default=True)
    counts_as_worked_time: Mapped[bool] = mapped_column(Boolean, default=True)
    # Code passed to accounting; may differ from the internal code.
    external_code: Mapped[str | None] = mapped_column(String(50))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkScheduleModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    """A working-time pattern; the baseline input to the timesheet (section 9)."""

    __tablename__ = "work_schedules"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_work_schedules_organization_code"),
        CheckConstraint("cycle_length_days > 0", name="cycle_positive"),
        CheckConstraint(
            "weekly_hours IS NULL OR weekly_hours > 0",
            name="weekly_hours_positive",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(30))
    # Days in the repeating pattern: 7 for a weekly schedule, longer for shift rotations.
    cycle_length_days: Mapped[int] = mapped_column(Integer, default=7)
    weekly_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    default_time_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("time_codes.id", ondelete="RESTRICT")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkScheduleDayModel(UUIDPrimaryKeyMixin, RevisionMixin, Base):
    """One day of a schedule's repeating cycle."""

    __tablename__ = "work_schedule_days"
    __table_args__ = (
        UniqueConstraint(
            "work_schedule_id", "cycle_day", name="uq_work_schedule_days_schedule_day"
        ),
        CheckConstraint("cycle_day >= 0", name="cycle_day_nonnegative"),
        CheckConstraint("hours >= 0", name="hours_nonnegative"),
    )

    work_schedule_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_schedules.id", ondelete="CASCADE"), index=True
    )
    # Zero-based offset into the cycle; for a weekly schedule 0 is Monday.
    cycle_day: Mapped[int] = mapped_column(Integer)
    working_day: Mapped[bool] = mapped_column(Boolean, default=True)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    starts_at_minute: Mapped[int | None] = mapped_column(Integer)
    time_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("time_codes.id", ondelete="RESTRICT")
    )


class EmployeeWorkScheduleModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    """Assignment of a schedule to an employee for a period."""

    __tablename__ = "employee_work_schedules"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="valid_dates",
        ),
        Index(
            "ix_employee_work_schedules_employee_effective",
            "employee_id",
            "effective_from",
            "effective_to",
        ),
    )

    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    work_schedule_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_schedules.id", ondelete="RESTRICT")
    )
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    # Anchors the cycle so shift rotations land on the right day after a gap.
    cycle_anchor_date: Mapped[date | None] = mapped_column(Date)
    assigned_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )


class TimesheetPeriodModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    """A month of timesheet for one unit, closed by HR and sent to accounting."""

    __tablename__ = "timesheet_periods"
    __table_args__ = (
        UniqueConstraint(
            "organization_unit_id",
            "period_start",
            name="uq_timesheet_periods_unit_period",
        ),
        CheckConstraint("period_end >= period_start", name="valid_dates"),
        Index("ix_timesheet_periods_scope_status", "organization_id", "status", "period_start"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    organization_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_units.id", ondelete="RESTRICT"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), index=True)
    # Section 9: the manager confirms the team, then HR checks codes and bases.
    manager_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manager_confirmed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    sent_to_accounting_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopen_reason: Mapped[str | None] = mapped_column(Text)


class TimesheetEntryModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    """One employee-day of the timesheet, derived from a schedule or an approved event."""

    __tablename__ = "timesheet_entries"
    __table_args__ = (
        UniqueConstraint(
            "timesheet_period_id",
            "employee_id",
            "entry_date",
            "time_code_id",
            name="uq_timesheet_entries_period_employee_date_code",
        ),
        CheckConstraint("hours >= 0", name="hours_nonnegative"),
        CheckConstraint("hours <= 24", name="hours_maximum"),
        # A manual row must say why it exists; a derived row must point at its source.
        CheckConstraint(
            "(source IN ('manual', 'correction')) = (manual_reason IS NOT NULL)",
            name="manual_reason_present",
        ),
        Index("ix_timesheet_entries_employee_date", "employee_id", "entry_date"),
        Index("ix_timesheet_entries_period_employee", "timesheet_period_id", "employee_id"),
    )

    timesheet_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("timesheet_periods.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    entry_date: Mapped[date] = mapped_column(Date)
    time_code_id: Mapped[UUID] = mapped_column(ForeignKey("time_codes.id", ondelete="RESTRICT"))
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    source: Mapped[str] = mapped_column(String(30))
    # Set for derived rows: the absence or leave request that produced this entry.
    source_absence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employee_absences.id", ondelete="RESTRICT")
    )
    source_leave_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("leave_requests.id", ondelete="RESTRICT")
    )
    manual_reason: Mapped[str | None] = mapped_column(Text)
    # Set when the period closes; a locked row changes only via a correction.
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )


class TimesheetCorrectionModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    """The separate process required to change a closed period (section 8).

    Both the before and after values are kept inline so the correction stays auditable
    even though the entry it targets has since been rewritten.
    """

    __tablename__ = "timesheet_corrections"
    __table_args__ = (
        CheckConstraint(
            "requested_hours IS NULL OR requested_hours >= 0",
            name="requested_hours_nonnegative",
        ),
        Index("ix_timesheet_corrections_scope_status", "organization_id", "status"),
        Index("ix_timesheet_corrections_period", "timesheet_period_id"),
        Index("ix_timesheet_corrections_process_instance", "process_instance_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    timesheet_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("timesheet_periods.id", ondelete="RESTRICT")
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    entry_date: Mapped[date] = mapped_column(Date)
    # Null when the correction adds a row that did not exist before.
    timesheet_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("timesheet_entries.id", ondelete="RESTRICT")
    )
    previous_time_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("time_codes.id", ondelete="RESTRICT")
    )
    previous_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    # Null when the correction removes a row.
    requested_time_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("time_codes.id", ondelete="RESTRICT")
    )
    requested_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), index=True)
    process_instance_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("process_instances.id", ondelete="RESTRICT")
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    decision_reason: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
