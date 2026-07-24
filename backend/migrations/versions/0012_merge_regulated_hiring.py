"""merge regulated hiring branch into the main revision graph

Revision ID: 0012_merge_regulated_hiring
Revises: 0011_employee_hiring_profile, 0007_regulated_hiring

The regulated_hiring module branches off 0006_merge_hiring_absence in parallel
with the Module 4 / hiring-auto line that continues to 0011. This merge collapses
the two heads into one so `alembic upgrade head` stays single-headed.
"""

from collections.abc import Sequence

revision: str = "0012_merge_regulated_hiring"
down_revision: str | Sequence[str] | None = (
    "0011_employee_hiring_profile",
    "0007_regulated_hiring",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join both schema branches without additional DDL."""


def downgrade() -> None:
    """Split the version graph back into its two parent heads."""
