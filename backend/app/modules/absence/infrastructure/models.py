from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.database.mixins import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin


class LeaveTypeModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "leave_types"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(250))
    paid: Mapped[bool]
    requires_balance: Mapped[bool]
    active: Mapped[bool]


class LeaveBalanceModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "leave_balances"
    __table_args__ = (UniqueConstraint("employee_id", "leave_type_id", "year"),)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    leave_type_id: Mapped[UUID] = mapped_column(ForeignKey("leave_types.id", ondelete="RESTRICT"))
    year: Mapped[int]
    entitled_days: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    carried_days: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=0)
    reserved_days: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=0)
    used_days: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=0)


class LeaveRequestModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        Index("ix_leave_requests_scope_status", "organization_id", "unit_id", "status"),
        Index("ix_leave_requests_employee_dates", "employee_id", "start_date", "end_date"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_units.id", ondelete="RESTRICT"), index=True
    )
    leave_type_id: Mapped[UUID] = mapped_column(ForeignKey("leave_types.id", ondelete="RESTRICT"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    requested_days: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), index=True)
    returned_from_stage: Mapped[str | None] = mapped_column(String(40))
    process_instance_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("process_instances.id", ondelete="RESTRICT")
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)


class BusinessTripRequestModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "business_trip_requests"
    __table_args__ = (
        Index("ix_business_trips_scope_status", "organization_id", "unit_id", "status"),
        Index("ix_business_trips_employee_dates", "employee_id", "start_date", "end_date"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_units.id", ondelete="RESTRICT"), index=True
    )
    destination: Mapped[str] = mapped_column(String(500))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    purpose: Mapped[str] = mapped_column(Text)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    funding_details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(40), index=True)
    returned_from_stage: Mapped[str | None] = mapped_column(String(40))
    process_instance_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("process_instances.id", ondelete="RESTRICT")
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
