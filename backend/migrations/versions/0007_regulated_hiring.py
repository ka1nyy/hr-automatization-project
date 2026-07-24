"""regulated hiring authority, stages, forms, and legal checkpoints

Revision ID: 0007_regulated_hiring
Revises: 0006_merge_hiring_absence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_regulated_hiring"
down_revision: str | None = "0006_merge_hiring_absence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.UUID(), nullable=False)


def _versioned() -> list[sa.Column]:
    return [
        _id(),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "normative_sources",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("authority_status", sa.String(30), nullable=False),
        sa.Column("file_reference", sa.String(1000), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_versioned(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code"),
    )
    op.create_index("ix_normative_sources_organization_id", "normative_sources", ["organization_id"])
    op.create_index("ix_normative_sources_authority_status", "normative_sources", ["authority_status"])

    op.create_table(
        "authority_bindings",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("authority_status", sa.String(30), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("assertion", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("granted_permissions", jsonb, nullable=False),
        *_versioned(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["normative_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "entity_type", "entity_id", "effective_from"),
    )
    op.create_index("ix_authority_bindings_organization_id", "authority_bindings", ["organization_id"])
    op.create_index("ix_authority_bindings_entity_id", "authority_bindings", ["entity_id"])
    op.create_index("ix_authority_bindings_authority_status", "authority_bindings", ["authority_status"])
    op.create_index("ix_authority_bindings_entity", "authority_bindings", ["entity_type", "entity_id", "authority_status"])

    op.create_table(
        "regulated_hiring_stage_definitions",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("owner_role_code", sa.String(100), nullable=False),
        sa.Column("sla_min_days", sa.Integer(), nullable=True),
        sa.Column("sla_max_days", sa.Integer(), nullable=True),
        sa.Column("working_days", sa.Boolean(), nullable=False),
        sa.Column("entry_criteria", jsonb, nullable=False),
        sa.Column("exit_criteria", jsonb, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_versioned(),
        sa.CheckConstraint("sequence >= 0 AND sequence <= 22", name="regulated_hiring_stage_sequence"),
        sa.CheckConstraint("version_number > 0", name="regulated_hiring_stage_version_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["normative_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", "version_number"),
        sa.UniqueConstraint("organization_id", "sequence", "version_number"),
    )
    op.create_index("ix_regulated_hiring_stage_definitions_organization_id", "regulated_hiring_stage_definitions", ["organization_id"])

    op.create_table(
        "regulated_hiring_form_definitions",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("owner_role_code", sa.String(100), nullable=False),
        sa.Column("signer_role_codes", jsonb, nullable=False),
        sa.Column("data_schema", jsonb, nullable=False),
        sa.Column("immutable_after_signing", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_versioned(),
        sa.CheckConstraint("sequence >= 1 AND sequence <= 21", name="regulated_hiring_form_sequence"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["normative_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", "version_number"),
    )
    op.create_index("ix_regulated_hiring_form_definitions_organization_id", "regulated_hiring_form_definitions", ["organization_id"])

    op.create_table(
        "regulated_hiring_cases",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("recruitment_request_id", sa.UUID(), nullable=False),
        sa.Column("staffing_slot_id", sa.UUID(), nullable=False),
        sa.Column("candidate_application_id", sa.UUID(), nullable=True),
        sa.Column("business_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("current_stage_code", sa.String(100), nullable=False),
        sa.Column("current_stage_sequence", sa.Integer(), nullable=False),
        sa.Column("process_engine", sa.String(30), nullable=False),
        sa.Column("camunda_process_instance_key", sa.String(100), nullable=True),
        sa.Column("initiated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_reason", sa.Text(), nullable=True),
        *_versioned(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recruitment_request_id"], ["recruitment_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["staffing_slot_id"], ["staffing_slots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_application_id"], ["candidate_applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "business_key"),
        sa.UniqueConstraint("recruitment_request_id"),
        sa.UniqueConstraint("camunda_process_instance_key"),
    )
    op.create_index("ix_regulated_hiring_cases_organization_id", "regulated_hiring_cases", ["organization_id"])
    op.create_index("ix_regulated_hiring_cases_status", "regulated_hiring_cases", ["status"])
    op.create_index("ix_regulated_hiring_cases_current_stage_code", "regulated_hiring_cases", ["current_stage_code"])
    op.create_index("ix_regulated_hiring_cases_scope_status", "regulated_hiring_cases", ["organization_id", "status"])

    op.create_table(
        "regulated_hiring_stage_executions",
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("stage_definition_id", sa.UUID(), nullable=False),
        sa.Column("stage_code", sa.String(100), nullable=False),
        sa.Column("stage_sequence", sa.Integer(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("assigned_user_id", sa.UUID(), nullable=True),
        sa.Column("assigned_employee_id", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", sa.String(30), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("evidence", jsonb, nullable=False),
        *_versioned(),
        sa.CheckConstraint("cycle > 0", name="regulated_hiring_stage_cycle_positive"),
        sa.ForeignKeyConstraint(["case_id"], ["regulated_hiring_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_definition_id"], ["regulated_hiring_stage_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "stage_code", "cycle"),
    )
    op.create_index("ix_regulated_hiring_stage_executions_case_id", "regulated_hiring_stage_executions", ["case_id"])
    op.create_index("ix_regulated_hiring_stage_executions_status", "regulated_hiring_stage_executions", ["status"])
    op.create_index("ix_regulated_hiring_stage_execution_active", "regulated_hiring_stage_executions", ["case_id", "status", "due_at"])

    op.create_table(
        "regulated_hiring_stage_actions",
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("stage_execution_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("safe_metadata", jsonb, nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        _id(),
        sa.ForeignKeyConstraint(["case_id"], ["regulated_hiring_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_execution_id"], ["regulated_hiring_stage_executions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_regulated_hiring_stage_actions_case_id", "regulated_hiring_stage_actions", ["case_id"])
    op.create_index("ix_regulated_hiring_stage_actions_case_time", "regulated_hiring_stage_actions", ["case_id", "occurred_at"])

    op.create_table(
        "regulated_hiring_form_records",
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("form_definition_id", sa.UUID(), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("data", jsonb, nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("signed_by", jsonb, nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("supersedes_record_id", sa.UUID(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        *_versioned(),
        sa.CheckConstraint("record_version > 0", name="regulated_hiring_form_record_version_positive"),
        sa.ForeignKeyConstraint(["case_id"], ["regulated_hiring_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["form_definition_id"], ["regulated_hiring_form_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["document_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_record_id"], ["regulated_hiring_form_records.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "form_definition_id", "record_version"),
    )
    op.create_index("ix_regulated_hiring_form_records_case_id", "regulated_hiring_form_records", ["case_id"])
    op.create_index("ix_regulated_hiring_form_records_status", "regulated_hiring_form_records", ["status"])

    op.create_table(
        "regulated_candidate_consents",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("vacancy_id", sa.UUID(), nullable=False),
        sa.Column("consent_version", sa.Integer(), nullable=False),
        sa.Column("purposes", jsonb, nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("reserve_granted", sa.Boolean(), nullable=False),
        sa.Column("reference_checks_granted", sa.Boolean(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_until", sa.Date(), nullable=True),
        sa.Column("evidence_document_id", sa.UUID(), nullable=True),
        *_versioned(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_document_id"], ["document_records.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "vacancy_id", "consent_version"),
    )
    op.create_index("ix_regulated_candidate_consents_organization_id", "regulated_candidate_consents", ["organization_id"])
    op.create_index("ix_regulated_candidate_consents_candidate_id", "regulated_candidate_consents", ["candidate_id"])
    op.create_index("ix_regulated_candidate_consents_vacancy_id", "regulated_candidate_consents", ["vacancy_id"])

    op.create_table(
        "regulated_employment_registrations",
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("contract_document_id", sa.UUID(), nullable=True),
        sa.Column("contract_signed_by_employer_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contract_signed_by_candidate_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_document_id", sa.UUID(), nullable=True),
        sa.Column("order_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_start_date", sa.Date(), nullable=False),
        sa.Column("esutd_due_date", sa.Date(), nullable=True),
        sa.Column("esutd_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("esutd_confirmation", sa.String(500), nullable=True),
        sa.Column("personnel_file_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admitted_to_work_at", sa.DateTime(timezone=True), nullable=True),
        *_versioned(),
        sa.ForeignKeyConstraint(["case_id"], ["regulated_hiring_cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contract_document_id"], ["document_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_document_id"], ["document_records.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id"),
    )
    op.create_index("ix_regulated_employment_registrations_case_id", "regulated_employment_registrations", ["case_id"])

    op.create_table(
        "regulated_probation_plans",
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=True),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("goals_30", jsonb, nullable=False),
        sa.Column("goals_60", jsonb, nullable=False),
        sa.Column("goals_90", jsonb, nullable=False),
        sa.Column("signed_by_manager_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_by_employee_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_30", jsonb, nullable=True),
        sa.Column("review_60", jsonb, nullable=True),
        sa.Column("final_review", jsonb, nullable=True),
        sa.Column("legal_review_required", sa.Boolean(), nullable=False),
        sa.Column("legal_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.String(30), nullable=True),
        *_versioned(),
        sa.CheckConstraint("duration_months > 0 AND duration_months <= 6", name="regulated_probation_duration"),
        sa.ForeignKeyConstraint(["case_id"], ["regulated_hiring_cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id"),
    )
    op.create_index("ix_regulated_probation_plans_case_id", "regulated_probation_plans", ["case_id"])

    op.create_table(
        "regulated_commission_evaluations",
        sa.Column("commission_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("member_employee_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("criterion_scores", jsonb, nullable=False),
        sa.Column("total_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("recommendation", sa.String(30), nullable=False),
        sa.Column("factual_basis", jsonb, nullable=False),
        sa.Column("conflict_declared", sa.Boolean(), nullable=False),
        sa.Column("amended_from_id", sa.UUID(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        _id(),
        sa.CheckConstraint("total_score >= 0 AND total_score <= 100", name="regulated_commission_score"),
        sa.ForeignKeyConstraint(["commission_id"], ["competition_commissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["application_id"], ["candidate_applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["member_employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["amended_from_id"], ["regulated_commission_evaluations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("commission_id", "application_id", "member_employee_id", "version_number"),
    )
    op.create_index("ix_regulated_commission_evaluations_commission_id", "regulated_commission_evaluations", ["commission_id"])
    op.create_index("ix_regulated_commission_evaluations_application_id", "regulated_commission_evaluations", ["application_id"])


def downgrade() -> None:
    for table in (
        "regulated_commission_evaluations",
        "regulated_probation_plans",
        "regulated_employment_registrations",
        "regulated_candidate_consents",
        "regulated_hiring_form_records",
        "regulated_hiring_stage_actions",
        "regulated_hiring_stage_executions",
        "regulated_hiring_cases",
        "regulated_hiring_form_definitions",
        "regulated_hiring_stage_definitions",
        "authority_bindings",
        "normative_sources",
    ):
        op.drop_table(table)
