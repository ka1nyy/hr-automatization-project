from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.database.mixins import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin


class HiringRequestModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "new_employee_hiring_requests"
    __table_args__ = (
        UniqueConstraint("organization_id", "request_number"),
        Index("ix_new_hiring_requests_status_stage", "organization_id", "status", "current_stage"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    request_number: Mapped[str] = mapped_column(String(80))
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT"), index=True
    )
    protected_personal_data: Mapped[str] = mapped_column(Text)
    employment_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    education_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    current_stage: Mapped[int] = mapped_column(Integer, default=0)
    approval_cycle: Mapped[int] = mapped_column(Integer, default=1)
    pdf_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_records.id", ondelete="RESTRICT")
    )
    pdf_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT")
    )
    final_pdf_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HiringAttachmentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "new_employee_hiring_attachments"
    __table_args__ = (UniqueConstraint("request_id", "category"),)

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("new_employee_hiring_requests.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(40))
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_records.id", ondelete="RESTRICT")
    )
    current_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT")
    )
    original_filename: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(200))


class HiringApprovalDecisionModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "new_employee_hiring_approval_decisions"
    __table_args__ = (UniqueConstraint("request_id", "approval_cycle", "stage_number"),)

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("new_employee_hiring_requests.id", ondelete="CASCADE"), index=True
    )
    approval_cycle: Mapped[int] = mapped_column(Integer)
    stage_number: Mapped[int] = mapped_column(Integer)
    stage_code: Mapped[str] = mapped_column(String(80))
    stage_name: Mapped[str] = mapped_column(String(300))
    approver_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    approver_name: Mapped[str] = mapped_column(String(255))
    approver_role: Mapped[str] = mapped_column(String(255))
    decision: Mapped[str] = mapped_column(String(30))
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HiringDispatchModel(UUIDPrimaryKeyMixin, RevisionMixin, Base):
    __tablename__ = "new_employee_hiring_dispatches"
    __table_args__ = (UniqueConstraint("request_id", "recipient_type"),)

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("new_employee_hiring_requests.id", ondelete="CASCADE"), index=True
    )
    recipient_type: Mapped[str] = mapped_column(String(30))
    assigned_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT"), index=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="assigned")
