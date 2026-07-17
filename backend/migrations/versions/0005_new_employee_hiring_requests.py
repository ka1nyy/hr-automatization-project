"""new employee hiring requests

Revision ID: 0005_hiring_requests
Revises: 0004_module2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_hiring_requests"
down_revision: str | None = "0004_module2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "new_employee_hiring_requests",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("request_number", sa.String(80), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("protected_personal_data", sa.Text(), nullable=False),
        sa.Column("employment_data", postgresql.JSONB(), nullable=False),
        sa.Column("education_data", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("current_stage", sa.Integer(), nullable=False),
        sa.Column("approval_cycle", sa.Integer(), nullable=False),
        sa.Column("pdf_document_id", sa.UUID(), nullable=True),
        sa.Column("pdf_version_id", sa.UUID(), nullable=True),
        sa.Column("final_pdf_version_id", sa.UUID(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pdf_document_id"], ["document_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pdf_version_id"], ["document_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["final_pdf_version_id"], ["document_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "request_number"),
    )
    op.create_index(
        "ix_new_hiring_requests_organization_id",
        "new_employee_hiring_requests",
        ["organization_id"],
    )
    op.create_index(
        "ix_new_hiring_requests_created_by", "new_employee_hiring_requests", ["created_by"]
    )
    op.create_index("ix_new_hiring_requests_status", "new_employee_hiring_requests", ["status"])
    op.create_index(
        "ix_new_hiring_requests_status_stage",
        "new_employee_hiring_requests",
        ["organization_id", "status", "current_stage"],
    )
    op.create_table(
        "new_employee_hiring_attachments",
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("current_version_id", sa.UUID(), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(200), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["request_id"], ["new_employee_hiring_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["document_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["current_version_id"], ["document_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "category"),
    )
    op.create_index(
        "ix_new_employee_hiring_attachments_request_id",
        "new_employee_hiring_attachments",
        ["request_id"],
    )
    op.create_table(
        "new_employee_hiring_approval_decisions",
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("approval_cycle", sa.Integer(), nullable=False),
        sa.Column("stage_number", sa.Integer(), nullable=False),
        sa.Column("stage_code", sa.String(80), nullable=False),
        sa.Column("stage_name", sa.String(300), nullable=False),
        sa.Column("approver_user_id", sa.UUID(), nullable=False),
        sa.Column("approver_name", sa.String(255), nullable=False),
        sa.Column("approver_role", sa.String(255), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["request_id"], ["new_employee_hiring_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["approver_user_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "approval_cycle", "stage_number"),
    )
    op.create_index(
        "ix_new_employee_hiring_approval_decisions_request_id",
        "new_employee_hiring_approval_decisions",
        ["request_id"],
    )
    op.create_table(
        "new_employee_hiring_dispatches",
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("recipient_type", sa.String(30), nullable=False),
        sa.Column("assigned_user_id", sa.UUID(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["request_id"], ["new_employee_hiring_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "recipient_type"),
    )
    op.create_index(
        "ix_new_employee_hiring_dispatches_request_id",
        "new_employee_hiring_dispatches",
        ["request_id"],
    )
    op.create_index(
        "ix_new_employee_hiring_dispatches_assigned_user_id",
        "new_employee_hiring_dispatches",
        ["assigned_user_id"],
    )


def downgrade() -> None:
    op.drop_table("new_employee_hiring_dispatches")
    op.drop_table("new_employee_hiring_approval_decisions")
    op.drop_table("new_employee_hiring_attachments")
    op.drop_table("new_employee_hiring_requests")
