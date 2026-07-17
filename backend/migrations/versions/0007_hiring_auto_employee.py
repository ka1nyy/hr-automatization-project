"""link completed hiring requests to automatically created employees

Revision ID: 0007_hiring_auto_employee
Revises: 0006_merge_hiring_absence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_hiring_auto_employee"
down_revision: str | None = "0006_merge_hiring_absence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "new_employee_hiring_requests",
        sa.Column("hired_employee_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_new_employee_hiring_requests_hired_employee",
        "new_employee_hiring_requests",
        "employees",
        ["hired_employee_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_new_employee_hiring_requests_hired_employee",
        "new_employee_hiring_requests",
        ["hired_employee_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_new_employee_hiring_requests_hired_employee",
        "new_employee_hiring_requests",
        type_="unique",
    )
    op.drop_constraint(
        "fk_new_employee_hiring_requests_hired_employee",
        "new_employee_hiring_requests",
        type_="foreignkey",
    )
    op.drop_column("new_employee_hiring_requests", "hired_employee_id")
