"""Remove the demo business-process tables superseded by employee functions.

Revision ID: 0003_drop_business_processes
Revises: 0002_integrated_workflows
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_drop_business_processes"
down_revision: str | None = "0002_integrated_workflows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_hiring_status_created", table_name="hiring_requests")
    op.drop_table("hiring_requests")
    op.drop_index("ix_leave_status", table_name="leave_requests")
    op.drop_index("ix_leave_employee_dates", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_index("ix_work_tasks_state_due", table_name="work_tasks")
    op.drop_table("work_tasks")
    op.drop_index("ix_correspondence_sender_number", table_name="correspondence_items")
    op.drop_index("ix_correspondence_status_due", table_name="correspondence_items")
    op.drop_table("correspondence_items")
    op.drop_table("business_process_definitions")


def downgrade() -> None:
    op.create_table(
        "business_process_definitions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("active_instances", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("owner", sa.String(240), nullable=False),
        sa.Column(
            "steps", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("version > 0", name="ck_business_process_definitions_version_positive"),
    )
    op.create_table(
        "correspondence_items",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("number", sa.String(64), nullable=False, unique=True),
        sa.Column("sender", sa.String(300), nullable=False),
        sa.Column("sender_number", sa.String(120), nullable=False),
        sa.Column("sender_date", sa.Date(), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("document_type", sa.String(160), nullable=False),
        sa.Column("channel", sa.String(80), nullable=False),
        sa.Column("department", sa.String(240), nullable=False),
        sa.Column("executive", sa.String(240), nullable=False),
        sa.Column("executor", sa.String(240), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("priority", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("workflow_step", sa.String(160), nullable=False),
        sa.Column("confidentiality", sa.String(32), nullable=False),
        sa.Column("response_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "attachments", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "audit_log", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_correspondence_status_due", "correspondence_items", ["status", "due_date"])
    op.create_index(
        "ix_correspondence_sender_number", "correspondence_items", ["sender", "sender_number"]
    )
    op.create_table(
        "work_tasks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("document_number", sa.String(100), nullable=False),
        sa.Column("process", sa.String(200), nullable=False),
        sa.Column("role", sa.String(160), nullable=False),
        sa.Column("department", sa.String(240), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("priority", sa.String(24), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("assignee", sa.String(240)),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_work_tasks_state_due", "work_tasks", ["state", "due_date"])
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "employee_id",
            sa.UUID(),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("employee_name", sa.String(500), nullable=False),
        sa.Column("leave_type", sa.String(160), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("substitute", sa.String(300), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("document_number", sa.String(80), nullable=False, unique=True),
        sa.Column("workflow_step", sa.String(160), nullable=False),
        sa.Column("route_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "audit_log", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("end_date >= start_date", name="ck_leave_requests_valid_date_range"),
        sa.CheckConstraint("days > 0", name="ck_leave_requests_days_positive"),
    )
    op.create_index(
        "ix_leave_employee_dates", "leave_requests", ["employee_id", "start_date", "end_date"]
    )
    op.create_index("ix_leave_status", "leave_requests", ["status"])
    op.create_table(
        "hiring_requests",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("number", sa.String(80), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "attachments", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_step", sa.String(160), nullable=False),
        sa.Column("route_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "audit_log", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "created_by",
            sa.UUID(),
            sa.ForeignKey("user_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_hiring_status_created", "hiring_requests", ["status", "created_at"])
