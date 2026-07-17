"""Let administrators manage permissions: system flag, revision, updated_at

A system permission is one the source tree checks by code. Marking them lets the
service refuse a delete that would silently disable an authorization check, while
leaving administrator-defined permissions fully editable.

Existing rows are backfilled as system=true: every permission present before this
revision came from the seeded catalog, so all of them are code contracts.

Revision ID: 0012_permission_admin
Revises: 0011_employee_hiring_profile
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_permission_admin"
down_revision: str | None = "0011_employee_hiring_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "permissions",
        sa.Column("system", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "permissions",
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "permissions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    # Rows created from here on are administrator-defined unless the seed says otherwise,
    # so the column default flips to false once the backfill above has happened.
    op.alter_column("permissions", "system", server_default=sa.text("false"))
    op.create_index("ix_permissions_system", "permissions", ["system"])


def downgrade() -> None:
    op.drop_index("ix_permissions_system", table_name="permissions")
    op.drop_column("permissions", "updated_at")
    op.drop_column("permissions", "revision")
    op.drop_column("permissions", "system")
