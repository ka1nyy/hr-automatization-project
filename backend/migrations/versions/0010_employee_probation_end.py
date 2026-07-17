"""store the probation end date from the approved hiring request

Revision ID: 0010_employee_probation_end
Revises: 0009_employee_number_sequence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_employee_probation_end"
down_revision: str | None = "0009_employee_number_sequence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("probation_end", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE employees AS employee
        SET probation_end = (
            employee.hire_date
            + make_interval(
                months => (request.employment_data ->> 'probationMonths')::INTEGER
            )
        )::DATE
        FROM new_employee_hiring_requests AS request
        WHERE request.hired_employee_id = employee.id
          AND (request.employment_data ->> 'probationMonths') ~ '^[0-9]+$'
          AND (request.employment_data ->> 'probationMonths')::INTEGER > 0
        """
    )


def downgrade() -> None:
    op.drop_column("employees", "probation_end")
