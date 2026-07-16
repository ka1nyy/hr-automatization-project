"""Deterministic, idempotent reference configuration for Module 2."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.absence.infrastructure.models import LeaveBalanceModel, LeaveTypeModel
from app.modules.documents.infrastructure.models import DocumentTypeModel
from app.modules.recruitment.infrastructure.models import PublicationChannelModel
from app.modules.termination.infrastructure.models import TerminationReasonModel
from app.modules.workflow.infrastructure.models import (
    ActorRuleModel,
    FormDefinitionModel,
    FormDefinitionVersionModel,
    FormFieldDefinitionModel,
    ProcessDefinitionModel,
    ProcessDefinitionVersionModel,
    ProcessStepDefinitionModel,
    ProcessTransitionDefinitionModel,
)

DOCUMENT_TYPES: tuple[tuple[str, str], ...] = (
    ("recruitment_request", "Recruitment request"),
    ("staffing_conclusion", "Staffing and budget conclusion"),
    ("vacancy_profile", "Vacancy profile"),
    ("candidate_cv", "Candidate CV"),
    ("candidate_consent", "Candidate consent"),
    ("interview_evaluation", "Interview evaluation"),
    ("commission_protocol", "Commission protocol"),
    ("job_offer", "Job offer"),
    ("candidate_checklist", "Candidate document checklist"),
    ("employment_contract", "Employment contract"),
    ("hiring_order", "Hiring order"),
    ("local_normative_act", "Local normative act"),
    ("lna_acknowledgement", "LNA acknowledgement"),
    ("termination_request", "Termination request"),
    ("termination_notice", "Termination notice"),
    ("legal_conclusion", "Legal conclusion"),
    ("termination_order", "Termination order"),
    ("handover_checklist", "Handover checklist"),
    ("asset_return_confirmation", "Asset return confirmation"),
    ("access_revocation_confirmation", "Access revocation confirmation"),
    ("final_settlement_confirmation", "Final settlement confirmation"),
    ("exit_interview_form", "Exit interview form"),
)

ROUTES: Mapping[str, tuple[tuple[str, str, str, tuple[str, ...]], ...]] = {
    "recruitment": (
        (
            "hr_review",
            "HR completeness review",
            "recruitment.request.review_hr",
            ("approve", "return", "reject"),
        ),
        (
            "staffing_review",
            "Staffing and finance review",
            "recruitment.request.review_staffing",
            ("approve", "return", "reject"),
        ),
        (
            "vacancy_management",
            "Vacancy management",
            "recruitment.vacancy.publish",
            ("complete", "return", "cancel"),
        ),
    ),
    "hiring": (
        (
            "document_collection",
            "Candidate document collection",
            "recruitment.hiring.manage",
            ("complete", "return", "cancel"),
        ),
        (
            "contract_order",
            "Contract and order",
            "documents.sign_request",
            ("complete", "return", "reject"),
        ),
        ("onboarding", "Onboarding execution", "recruitment.hiring.manage", ("complete", "cancel")),
    ),
    "termination": (
        ("hr_review", "HR review", "termination.review_hr", ("approve", "return", "reject")),
        (
            "signature_registration",
            "Signature and registration",
            "termination.sign",
            ("complete", "return", "reject"),
        ),
        ("offboarding", "Offboarding execution", "termination.complete", ("complete", "cancel")),
    ),
    "leave": (
        (
            "manager_review",
            "Manager leave review",
            "leave.review_manager",
            ("approve", "return", "reject"),
        ),
        (
            "hr_review",
            "HR leave review",
            "leave.review_hr",
            ("approve", "return", "reject"),
        ),
    ),
    "business_trip": (
        (
            "manager_review",
            "Manager business-trip review",
            "business_trip.review_manager",
            ("approve", "return", "reject"),
        ),
        (
            "finance_review",
            "Business-trip finance review",
            "business_trip.review_finance",
            ("approve", "return", "reject"),
        ),
        (
            "hr_registration",
            "Business-trip HR registration",
            "business_trip.register",
            ("complete", "return", "reject"),
        ),
    ),
}

STEP_DOCUMENTS: Mapping[tuple[str, str], tuple[str, ...]] = {
    ("recruitment", "hr_review"): ("recruitment_request", "vacancy_profile"),
    ("recruitment", "staffing_review"): ("staffing_conclusion",),
    ("hiring", "document_collection"): (
        "candidate_checklist",
        "candidate_consent",
    ),
    ("hiring", "contract_order"): ("employment_contract", "hiring_order"),
    ("termination", "hr_review"): ("termination_request",),
    ("termination", "signature_registration"): ("termination_order",),
    ("termination", "offboarding"): (
        "handover_checklist",
        "asset_return_confirmation",
        "access_revocation_confirmation",
        "final_settlement_confirmation",
    ),
}

STEP_FORMS: Mapping[tuple[str, str], str] = {
    ("recruitment", "hr_review"): "candidate_application",
    ("hiring", "document_collection"): "hiring_checklist",
    ("termination", "offboarding"): "offboarding_checklist",
}

FORM_FIELDS: Mapping[str, tuple[tuple[str, str, str, bool, str], ...]] = {
    "candidate_application": (
        ("motivation", "Candidate motivation", "multiline", True, "confidential"),
        ("availability_date", "Availability date", "date", False, "confidential"),
    ),
    "hiring_checklist": (
        ("identity_verified", "Identity verified", "boolean", True, "restricted"),
        ("contract_ready", "Employment contract ready", "boolean", True, "confidential"),
    ),
    "offboarding_checklist": (
        ("handover_complete", "Handover complete", "boolean", True, "internal"),
        ("assets_returned", "Assets returned", "boolean", True, "internal"),
        ("access_revoked", "Access revoked", "boolean", True, "restricted"),
        ("settlement_confirmed", "Settlement confirmed", "boolean", True, "restricted"),
    ),
}


async def seed_module2(
    session: AsyncSession,
    *,
    organization_id: UUID,
    actor_id: UUID,
    timestamp: datetime,
    seed_id: Any,
    insert_rows: Any,
) -> None:
    annual_type_id = seed_id("leave-type", "annual_paid")
    unpaid_type_id = seed_id("leave-type", "unpaid")
    await insert_rows(
        session,
        LeaveTypeModel.__table__,
        [
            {
                "id": annual_type_id,
                "organization_id": organization_id,
                "code": "annual_paid",
                "name": "Annual paid leave",
                "paid": True,
                "requires_balance": True,
                "active": True,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
            {
                "id": unpaid_type_id,
                "organization_id": organization_id,
                "code": "unpaid",
                "name": "Unpaid leave",
                "paid": False,
                "requires_balance": False,
                "active": True,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        ],
    )
    await insert_rows(
        session,
        LeaveBalanceModel.__table__,
        [
            {
                "id": seed_id("leave-balance", f"{employee}:{year}"),
                "organization_id": organization_id,
                "employee_id": seed_id("employee", employee),
                "leave_type_id": annual_type_id,
                "year": year,
                "entitled_days": 24,
                "carried_days": 0,
                "reserved_days": 0,
                "used_days": 0,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            for employee in ("development-employee", "development-director")
            for year in range(timestamp.year, timestamp.year + 3)
        ],
    )
    await insert_rows(
        session,
        DocumentTypeModel.__table__,
        [
            {
                "id": seed_id("document-type", code),
                "organization_id": organization_id,
                "code": code,
                "name": name,
                "description": None,
                "default_confidentiality": "confidential"
                if code.startswith("candidate_")
                else "internal",
                "allowed_mime_types": [
                    "application/pdf",
                    "image/png",
                    "image/jpeg",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ],
                "maximum_size_bytes": 10_485_760,
                "active": True,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            for code, name in DOCUMENT_TYPES
        ],
    )
    await insert_rows(
        session,
        PublicationChannelModel.__table__,
        [
            {
                "id": seed_id("publication-channel", code),
                "organization_id": organization_id,
                "code": code,
                "name": name,
                "channel_type": kind,
                "active": True,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            for code, name, kind in (
                ("internal_board", "Internal vacancy board", "internal"),
                ("corporate_site", "Corporate website", "external_manual"),
                ("employment_platform", "Employment platform", "external_manual"),
                ("external_source", "Other recorded source", "external_manual"),
            )
        ],
    )
    await insert_rows(
        session,
        TerminationReasonModel.__table__,
        [
            {
                "id": seed_id("termination-reason", code),
                "organization_id": organization_id,
                "code": code,
                "name": name,
                "legal_review_required": legal,
                "employee_initiated": employee,
                "active": True,
                "revision": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            for code, name, legal, employee in (
                ("employee_request", "Employee request", False, True),
                ("agreement", "Mutual agreement", True, True),
                ("employer_initiative", "Employer initiative", True, False),
                ("contract_expiry", "Contract expiry", False, False),
            )
        ],
    )
    await insert_rows(
        session,
        FormDefinitionModel.__table__,
        [
            {
                "id": seed_id("form-definition", code),
                "organization_id": organization_id,
                "code": code,
                "name": code.replace("_", " ").title(),
                "active": True,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            for code in FORM_FIELDS
        ],
    )
    await insert_rows(
        session,
        FormDefinitionVersionModel.__table__,
        [
            {
                "id": seed_id("form-version", f"{code}:1"),
                "form_definition_id": seed_id("form-definition", code),
                "version_number": 1,
                "status": "published",
                "based_on_version_id": None,
                "revision": 1,
                "created_by": actor_id,
                "published_by": actor_id,
                "created_at": timestamp,
                "published_at": timestamp,
            }
            for code in FORM_FIELDS
        ],
    )
    await insert_rows(
        session,
        FormFieldDefinitionModel.__table__,
        [
            {
                "id": seed_id("form-field", f"{form_code}:{field_code}"),
                "form_version_id": seed_id("form-version", f"{form_code}:1"),
                "code": field_code,
                "label": label,
                "field_type": field_type,
                "required": required,
                "validation_rules": {},
                "reference_data_source": None,
                "visibility_rule": None,
                "editability_rule": None,
                "confidentiality": confidentiality,
                "ordering": ordering,
                "help_text": None,
                "revision": 1,
            }
            for form_code, fields in FORM_FIELDS.items()
            for ordering, (field_code, label, field_type, required, confidentiality) in enumerate(
                fields
            )
        ],
    )
    definitions: list[dict[str, Any]] = []
    versions: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    for process_code, route in ROUTES.items():
        definition_id = seed_id("process-definition", process_code)
        version_id = seed_id("process-version", f"{process_code}:1")
        definitions.append(
            {
                "id": definition_id,
                "organization_id": organization_id,
                "code": process_code,
                "name": f"Initial {process_code} route",
                "description": "Configurable demonstration route.",
                "active": True,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        versions.append(
            {
                "id": version_id,
                "process_definition_id": definition_id,
                "version_number": 1,
                "name": "Initial published route",
                "status": "published",
                "based_on_version_id": None,
                "effective_from": timestamp,
                "effective_to": None,
                "revision": 1,
                "created_by": actor_id,
                "published_by": actor_id,
                "created_at": timestamp,
                "published_at": timestamp,
            }
        )
        for index, (code, name, permission, actions) in enumerate(route):
            rule_id = seed_id("actor-rule", f"{process_code}:{code}")
            step_id = seed_id("process-step", f"{process_code}:{code}")
            rules.append(
                {
                    "id": rule_id,
                    "definition_version_id": version_id,
                    "code": f"{code}_actor",
                    "name": f"Actor for {name}",
                    "rule_type": "permission_holder",
                    "configuration": {"permissionCode": permission, "scopeSource": "process"},
                    "active": True,
                    "revision": 1,
                }
            )
            configuration: dict[str, Any] = {"manualExternalActions": True}
            form_code = STEP_FORMS.get((process_code, code))
            if form_code:
                configuration["formVersionId"] = str(seed_id("form-version", f"{form_code}:1"))
            if process_code == "recruitment" and code == "hr_review":
                configuration["screeningCriteria"] = [
                    {"code": "minimumRequirements", "required": True},
                    {"code": "relevantExperience", "required": True},
                ]
            if process_code == "recruitment" and code == "vacancy_management":
                configuration["commissionRules"] = {
                    "quorumRequired": 2,
                    "conflictDeclarationRequired": True,
                    "immutableEvaluations": True,
                }
            steps.append(
                {
                    "id": step_id,
                    "definition_version_id": version_id,
                    "stable_key": seed_id("process-step-stable", f"{process_code}:{code}"),
                    "code": code,
                    "name": name,
                    "step_type": "parallel_task"
                    if code in {"onboarding", "offboarding"}
                    else "approval",
                    "sequence": index,
                    "actor_rule_id": rule_id,
                    "allowed_actions": list(actions),
                    "due_duration_seconds": 259_200,
                    "required_document_type_ids": [
                        str(seed_id("document-type", document_code))
                        for document_code in STEP_DOCUMENTS.get((process_code, code), ())
                    ],
                    "configuration": configuration,
                    "completion_mode": "all",
                    "required_approvers": 1,
                    "active": True,
                    "revision": 1,
                }
            )
            if index:
                previous = seed_id("process-step", f"{process_code}:{route[index - 1][0]}")
                transition_action = "approve" if "approve" in route[index - 1][3] else "complete"
                transitions.append(
                    {
                        "id": seed_id("process-transition", f"{process_code}:{index}"),
                        "definition_version_id": version_id,
                        "source_step_id": previous,
                        "target_step_id": step_id,
                        "action": transition_action,
                        "condition": None,
                        "priority": 0,
                        "active": True,
                    }
                )
    await insert_rows(session, ProcessDefinitionModel.__table__, definitions)
    await insert_rows(session, ProcessDefinitionVersionModel.__table__, versions)
    await insert_rows(session, ActorRuleModel.__table__, rules)
    await insert_rows(session, ProcessStepDefinitionModel.__table__, steps)
    await insert_rows(session, ProcessTransitionDefinitionModel.__table__, transitions)
