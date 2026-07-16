"""absence leave and business trips

Revision ID: 0005_absence
Revises: 0004_module2
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_absence"
down_revision: str | None = "0004_module2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_types",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(250), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
        sa.Column("requires_balance", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code"),
    )
    op.create_index("ix_leave_types_organization_id", "leave_types", ["organization_id"])
    op.create_table(
        "leave_balances",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("leave_type_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("entitled_days", sa.Numeric(7, 2), nullable=False),
        sa.Column("carried_days", sa.Numeric(7, 2), nullable=False),
        sa.Column("reserved_days", sa.Numeric(7, 2), nullable=False),
        sa.Column("used_days", sa.Numeric(7, 2), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "leave_type_id", "year"),
    )
    op.create_index("ix_leave_balances_organization_id", "leave_balances", ["organization_id"])
    op.create_index("ix_leave_balances_employee_id", "leave_balances", ["employee_id"])
    op.create_table(
        "leave_requests",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("leave_type_id", sa.UUID(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("requested_days", sa.Numeric(7, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("returned_from_stage", sa.String(40), nullable=True),
        sa.Column("process_instance_id", sa.UUID(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("end_date >= start_date", name="ck_leave_requests_dates"),
        sa.CheckConstraint("requested_days > 0", name="ck_leave_requests_days"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["organization_units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["process_instance_id"], ["process_instances.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_leave_requests_scope_status", "leave_requests", ["organization_id", "unit_id", "status"]
    )
    op.create_index(
        "ix_leave_requests_employee_dates",
        "leave_requests",
        ["employee_id", "start_date", "end_date"],
    )
    op.create_index("ix_leave_requests_employee_id", "leave_requests", ["employee_id"])
    op.create_index("ix_leave_requests_organization_id", "leave_requests", ["organization_id"])
    op.create_index("ix_leave_requests_unit_id", "leave_requests", ["unit_id"])
    op.create_index("ix_leave_requests_status", "leave_requests", ["status"])
    op.create_table(
        "business_trip_requests",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("destination", sa.String(500), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("funding_details", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("returned_from_stage", sa.String(40), nullable=True),
        sa.Column("process_instance_id", sa.UUID(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("end_date >= start_date", name="ck_business_trip_requests_dates"),
        sa.CheckConstraint("estimated_cost >= 0", name="ck_business_trip_requests_cost"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["organization_units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["process_instance_id"], ["process_instances.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_business_trips_scope_status",
        "business_trip_requests",
        ["organization_id", "unit_id", "status"],
    )
    op.create_index(
        "ix_business_trips_employee_dates",
        "business_trip_requests",
        ["employee_id", "start_date", "end_date"],
    )
    op.create_index(
        "ix_business_trip_requests_employee_id", "business_trip_requests", ["employee_id"]
    )
    op.create_index(
        "ix_business_trip_requests_organization_id", "business_trip_requests", ["organization_id"]
    )
    op.create_index("ix_business_trip_requests_unit_id", "business_trip_requests", ["unit_id"])
    op.create_index("ix_business_trip_requests_status", "business_trip_requests", ["status"])


def downgrade() -> None:
    op.drop_table("business_trip_requests")
    op.drop_table("leave_requests")
    op.drop_table("leave_balances")
    op.drop_table("leave_types")
