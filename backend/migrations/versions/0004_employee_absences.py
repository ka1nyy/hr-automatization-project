"""Add employee absences: vacations, sick leaves, business trips, days off.

Revision ID: 0004_employee_absences
Revises: 0003_drop_business_processes
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_employee_absences"
down_revision: str | None = "0003_drop_business_processes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee_absences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "employee_id",
            sa.Uuid(),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("absence_type", sa.String(32), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("details", sa.String(300), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("date_to >= date_from", name="ck_absences_valid_dates"),
    )
    op.create_index(
        "ix_absences_employee_dates", "employee_absences", ["employee_id", "date_from", "date_to"]
    )
    op.create_index(
        "ix_absences_status_dates", "employee_absences", ["status", "date_from", "date_to"]
    )


def downgrade() -> None:
    op.drop_index("ix_absences_status_dates", table_name="employee_absences")
    op.drop_index("ix_absences_employee_dates", table_name="employee_absences")
    op.drop_table("employee_absences")
