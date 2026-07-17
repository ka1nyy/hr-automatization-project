"""Relational persistence schema for employees and temporal authority."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base


class PersonModel(Base):
    __tablename__ = "people"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(160), nullable=False)
    last_name: Mapped[str] = mapped_column(String(160), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(160))
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    protected_iin: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    personal_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EmployeeModel(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "employee_number", name="uq_employees_organization_number"
        ),
        UniqueConstraint("organization_id", "person_id", name="uq_employees_organization_person"),
        CheckConstraint(
            "termination_date IS NULL OR termination_date >= hire_date",
            name="ck_employees_valid_dates",
        ),
        Index(
            "ix_employees_organization_active_status",
            "organization_id",
            "active",
            "employment_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "user_accounts.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_employees_created_by_user_accounts",
        ),
        nullable=False,
    )
    person_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("people.id", ondelete="RESTRICT"), nullable=False
    )
    employee_number: Mapped[str] = mapped_column(String(64), nullable=False)
    employment_status: Mapped[str] = mapped_column(String(32), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    probation_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    corporate_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EmployeeAbsenceModel(Base):
    __tablename__ = "employee_absences"
    __table_args__ = (
        CheckConstraint("date_to >= date_from", name="ck_absences_valid_dates"),
        Index("ix_absences_employee_dates", "employee_id", "date_from", "date_to"),
        Index("ix_absences_status_dates", "status", "date_from", "date_to"),
        UniqueConstraint("source_type", "source_id", name="uq_employee_absences_source"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    employee_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    absence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    details: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class EmployeeAssignmentModel(Base):
    __tablename__ = "employee_assignments"
    __table_args__ = (
        CheckConstraint("full_time_equivalent > 0", name="ck_assignments_fte_positive"),
        CheckConstraint("full_time_equivalent <= 1", name="ck_assignments_fte_maximum"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_assignments_valid_dates",
        ),
        Index(
            "ix_assignments_employee_effective",
            "employee_id",
            "effective_from",
            "effective_to",
        ),
        Index(
            "ix_assignments_slot_effective",
            "staffing_slot_id",
            "effective_from",
            "effective_to",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    employee_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    staffing_slot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("staffing_slots.id", ondelete="RESTRICT"), nullable=False
    )
    assignment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    full_time_equivalent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acting: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AssignmentReviewRequestModel(Base):
    __tablename__ = "employee_assignment_review_requests"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_employee_assignment_reviews_revision_positive"),
        Index(
            "uq_employee_assignment_reviews_pending",
            "assignment_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_employee_assignment_reviews_organization_status",
            "organization_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    assignment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employee_assignments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submission_reason: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class DelegationModel(Base):
    __tablename__ = "delegations"
    __table_args__ = (
        CheckConstraint(
            "delegator_employee_id <> delegate_employee_id",
            name="ck_delegations_distinct_employees",
        ),
        CheckConstraint("effective_to > effective_from", name="ck_delegations_valid_dates"),
        Index(
            "ix_delegations_delegator_effective",
            "delegator_employee_id",
            "effective_from",
            "effective_to",
        ),
        Index(
            "ix_delegations_delegate_effective",
            "delegate_employee_id",
            "effective_from",
            "effective_to",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    delegator_employee_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    delegate_employee_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delegated_permissions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


_assignment_table = cast(Table, EmployeeAssignmentModel.__table__)
_assignment_table.append_constraint(
    ExcludeConstraint(
        (_assignment_table.c.employee_id, "="),
        (
            func.daterange(
                _assignment_table.c.effective_from,
                _assignment_table.c.effective_to,
                "[]",
            ),
            "&&",
        ),
        where=text(
            '"primary" AND status IN '
            "('pending_review', 'planned', 'active', 'scheduled_end', 'ended')"
        ),
        name="ex_employee_assignments_one_primary_period",
        using="gist",
    )
)
