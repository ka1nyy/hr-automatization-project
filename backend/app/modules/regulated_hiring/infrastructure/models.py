from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.database.mixins import RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin


class NormativeSourceModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "normative_sources"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(50))
    authority_status: Mapped[str] = mapped_column(String(30), index=True)
    file_reference: Mapped[str | None] = mapped_column(String(1000))
    effective_from: Mapped[date | None] = mapped_column(Date)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class AuthorityBindingModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "authority_bindings"
    __table_args__ = (
        UniqueConstraint("organization_id", "entity_type", "entity_id", "effective_from"),
        Index("ix_authority_bindings_entity", "entity_type", "entity_id", "authority_status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID] = mapped_column(index=True)
    authority_status: Mapped[str] = mapped_column(String(30), index=True)
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("normative_sources.id", ondelete="RESTRICT")
    )
    assertion: Mapped[str] = mapped_column(Text)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    granted_permissions: Mapped[list[str]] = mapped_column(JSONB, default=list)


class HiringStageDefinitionModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "regulated_hiring_stage_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", "version_number"),
        UniqueConstraint("organization_id", "sequence", "version_number"),
        CheckConstraint("sequence >= 0 AND sequence <= 22", name="regulated_hiring_stage_sequence"),
        CheckConstraint("version_number > 0", name="regulated_hiring_stage_version_positive"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("normative_sources.id", ondelete="RESTRICT")
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    sequence: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(300))
    owner_role_code: Mapped[str] = mapped_column(String(100))
    sla_min_days: Mapped[int | None] = mapped_column(Integer)
    sla_max_days: Mapped[int | None] = mapped_column(Integer)
    working_days: Mapped[bool] = mapped_column(Boolean, default=True)
    entry_criteria: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    exit_criteria: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class HiringFormDefinitionModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "regulated_hiring_form_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", "version_number"),
        CheckConstraint("sequence >= 1 AND sequence <= 21", name="regulated_hiring_form_sequence"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("normative_sources.id", ondelete="RESTRICT")
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    sequence: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(500))
    owner_role_code: Mapped[str] = mapped_column(String(100))
    signer_role_codes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    data_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    immutable_after_signing: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class HiringProcessCaseModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "regulated_hiring_cases"
    __table_args__ = (
        UniqueConstraint("organization_id", "business_key"),
        UniqueConstraint("recruitment_request_id"),
        Index("ix_regulated_hiring_cases_scope_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    recruitment_request_id: Mapped[UUID] = mapped_column(
        ForeignKey("recruitment_requests.id", ondelete="RESTRICT")
    )
    staffing_slot_id: Mapped[UUID] = mapped_column(
        ForeignKey("staffing_slots.id", ondelete="RESTRICT")
    )
    candidate_application_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidate_applications.id", ondelete="RESTRICT")
    )
    business_key: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), index=True)
    current_stage_code: Mapped[str] = mapped_column(String(100), index=True)
    current_stage_sequence: Mapped[int] = mapped_column(Integer, default=0)
    process_engine: Mapped[str] = mapped_column(String(30), default="local")
    camunda_process_instance_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    initiated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_reason: Mapped[str | None] = mapped_column(Text)


class HiringStageExecutionModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "regulated_hiring_stage_executions"
    __table_args__ = (
        UniqueConstraint("case_id", "stage_code", "cycle"),
        CheckConstraint("cycle > 0", name="regulated_hiring_stage_cycle_positive"),
        Index("ix_regulated_hiring_stage_execution_active", "case_id", "status", "due_at"),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("regulated_hiring_cases.id", ondelete="CASCADE"), index=True
    )
    stage_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("regulated_hiring_stage_definitions.id", ondelete="RESTRICT")
    )
    stage_code: Mapped[str] = mapped_column(String(100))
    stage_sequence: Mapped[int] = mapped_column(Integer)
    cycle: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), index=True)
    assigned_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    assigned_employee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision: Mapped[str | None] = mapped_column(String(30))
    decision_comment: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class HiringStageActionModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "regulated_hiring_stage_actions"
    __table_args__ = (
        Index("ix_regulated_hiring_stage_actions_case_time", "case_id", "occurred_at"),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("regulated_hiring_cases.id", ondelete="CASCADE"), index=True
    )
    stage_execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("regulated_hiring_stage_executions.id", ondelete="RESTRICT")
    )
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HiringFormRecordModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "regulated_hiring_form_records"
    __table_args__ = (
        UniqueConstraint("case_id", "form_definition_id", "record_version"),
        CheckConstraint("record_version > 0", name="regulated_hiring_form_record_version_positive"),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("regulated_hiring_cases.id", ondelete="CASCADE"), index=True
    )
    form_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("regulated_hiring_form_definitions.id", ondelete="RESTRICT")
    )
    record_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    signed_by: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_records.id", ondelete="RESTRICT")
    )
    supersedes_record_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("regulated_hiring_form_records.id", ondelete="RESTRICT")
    )
    correction_reason: Mapped[str | None] = mapped_column(Text)


class CandidateConsentModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "regulated_candidate_consents"
    __table_args__ = (UniqueConstraint("candidate_id", "vacancy_id", "consent_version"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="RESTRICT"), index=True
    )
    vacancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("vacancies.id", ondelete="RESTRICT"), index=True
    )
    consent_version: Mapped[int] = mapped_column(Integer)
    purposes: Mapped[list[str]] = mapped_column(JSONB)
    granted: Mapped[bool] = mapped_column(Boolean)
    reserve_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    reference_checks_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[date | None] = mapped_column(Date)
    evidence_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_records.id", ondelete="RESTRICT")
    )


class EmploymentRegistrationModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "regulated_employment_registrations"
    __table_args__ = (UniqueConstraint("case_id"),)

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("regulated_hiring_cases.id", ondelete="RESTRICT"), index=True
    )
    contract_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_records.id", ondelete="RESTRICT")
    )
    contract_signed_by_employer_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contract_signed_by_candidate_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    order_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_records.id", ondelete="RESTRICT")
    )
    order_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_start_date: Mapped[date] = mapped_column(Date)
    esutd_due_date: Mapped[date | None] = mapped_column(Date)
    esutd_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    esutd_confirmation: Mapped[str | None] = mapped_column(String(500))
    personnel_file_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admitted_to_work_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProbationPlanModel(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "regulated_probation_plans"
    __table_args__ = (
        UniqueConstraint("case_id"),
        CheckConstraint(
            "duration_months > 0 AND duration_months <= 6", name="regulated_probation_duration"
        ),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("regulated_hiring_cases.id", ondelete="RESTRICT"), index=True
    )
    employee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT")
    )
    duration_months: Mapped[int] = mapped_column(Integer)
    goals_30: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    goals_60: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    goals_90: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    signed_by_manager_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signed_by_employee_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_30: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    review_60: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    final_review: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    legal_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    legal_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(String(30))


class CommissionEvaluationModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "regulated_commission_evaluations"
    __table_args__ = (
        UniqueConstraint("commission_id", "application_id", "member_employee_id", "version_number"),
        CheckConstraint(
            "total_score >= 0 AND total_score <= 100", name="regulated_commission_score"
        ),
    )

    commission_id: Mapped[UUID] = mapped_column(
        ForeignKey("competition_commissions.id", ondelete="RESTRICT"), index=True
    )
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_applications.id", ondelete="RESTRICT"), index=True
    )
    member_employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT")
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    criterion_scores: Mapped[dict[str, Any]] = mapped_column(JSONB)
    total_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    recommendation: Mapped[str] = mapped_column(String(30))
    factual_basis: Mapped[dict[str, Any]] = mapped_column(JSONB)
    conflict_declared: Mapped[bool] = mapped_column(Boolean, default=False)
    amended_from_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("regulated_commission_evaluations.id", ondelete="RESTRICT")
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
