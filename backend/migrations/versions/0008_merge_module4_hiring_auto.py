"""merge Module 4 and automatic hiring migration branches

Revision ID: 0008_merge_module4_hiring_auto
Revises: 0007_module4_timesheet, 0007_hiring_auto_employee
"""

from collections.abc import Sequence

revision: str = "0008_merge_module4_hiring_auto"
down_revision: str | Sequence[str] | None = (
    "0007_module4_timesheet",
    "0007_hiring_auto_employee",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join both schema branches without additional DDL."""


def downgrade() -> None:
    """Split the version graph back into its two parent heads."""
