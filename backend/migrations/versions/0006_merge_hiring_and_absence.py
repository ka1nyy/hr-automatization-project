"""merge hiring request and absence migration branches

Revision ID: 0006_merge_hiring_absence
Revises: 0005_hiring_requests, 0005_absence
"""

from collections.abc import Sequence

revision: str = "0006_merge_hiring_absence"
down_revision: str | Sequence[str] | None = (
    "0005_hiring_requests",
    "0005_absence",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join both schema branches without additional DDL."""


def downgrade() -> None:
    """Split the version graph back into its two parent heads."""
