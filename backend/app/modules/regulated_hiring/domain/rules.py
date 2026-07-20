from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from app.core.errors import ValidationError

from .enums import AuthorityStatus, StageCode

PROFESSIONAL_THRESHOLD = Decimal("60")
WINNER_THRESHOLD = Decimal("70")
COMMISSION_SIZE = 5
COMMISSION_QUORUM = 4
COMMISSION_WEIGHTS: Mapping[str, Decimal] = {
    "relevant_experience": Decimal("10"),
    "professional_assignment": Decimal("25"),
    "professional_interview": Decimal("25"),
    "behavioral_competencies": Decimal("20"),
    "management_case": Decimal("15"),
    "motivation": Decimal("5"),
}

FORBIDDEN_INITIAL_APPLICATION_FIELDS = frozenset(
    {
        "iin",
        "identity_document",
        "bank_details",
        "registration_address",
        "relatives",
        "marital_status",
        "children",
        "religion",
        "political_views",
        "nationality",
        "medical_diagnosis",
        "criminal_record_certificate",
    }
)


def require_confirmed_authority(status: str, *, entity_type: str) -> None:
    if status != AuthorityStatus.CONFIRMED:
        raise ValidationError(
            f"A confirmed {entity_type} is required for a legal hiring decision.",
            details={"entityType": entity_type, "authorityStatus": status},
        )


def validate_initial_application(payload: Mapping[str, Any]) -> None:
    forbidden = sorted(FORBIDDEN_INITIAL_APPLICATION_FIELDS.intersection(payload))
    if forbidden:
        raise ValidationError(
            "The initial application contains data that may only be requested from a finalist.",
            details={"forbiddenFields": forbidden},
        )
    if payload.get("consentGranted") is not True:
        raise ValidationError("Candidate consent is required before an application is stored.")


def validate_professional_assessment(score: Decimal, evidence: str) -> None:
    if score < 0 or score > 100:
        raise ValidationError("Professional assessment score must be between 0 and 100.")
    if score < PROFESSIONAL_THRESHOLD:
        raise ValidationError(
            "Professional assessment threshold was not reached.",
            details={"score": str(score), "threshold": str(PROFESSIONAL_THRESHOLD)},
        )
    if not evidence.strip():
        raise ValidationError("Professional assessment requires factual evidence.")


def calculate_commission_score(scores: Mapping[str, Decimal]) -> Decimal:
    if set(scores) != set(COMMISSION_WEIGHTS):
        raise ValidationError(
            "Commission score must contain the complete approved criteria set.",
            details={"requiredCriteria": sorted(COMMISSION_WEIGHTS)},
        )
    total = Decimal("0")
    for criterion, maximum in COMMISSION_WEIGHTS.items():
        value = scores[criterion]
        if value < 0 or value > maximum:
            raise ValidationError(
                "Commission criterion score is outside its approved range.",
                details={"criterion": criterion, "score": str(value), "maximum": str(maximum)},
            )
        total += value
    return total


def validate_commission_result(
    *,
    present_voters: int,
    total_score: Decimal,
    professional_assignment_score: Decimal,
    professional_interview_score: Decimal,
    stop_factors: Sequence[str],
    conflict_resolved: bool,
) -> None:
    if present_voters < COMMISSION_QUORUM or present_voters > COMMISSION_SIZE:
        raise ValidationError(
            "Competition commission quorum was not reached.",
            details={
                "present": present_voters,
                "required": COMMISSION_QUORUM,
                "size": COMMISSION_SIZE,
            },
        )
    if professional_assignment_score < PROFESSIONAL_THRESHOLD:
        raise ValidationError("Professional assignment component is below 60/100.")
    if professional_interview_score < PROFESSIONAL_THRESHOLD:
        raise ValidationError("Professional interview component is below 60/100.")
    if total_score < WINNER_THRESHOLD:
        raise ValidationError(
            "Winner threshold was not reached.",
            details={"score": str(total_score), "threshold": str(WINNER_THRESHOLD)},
        )
    if stop_factors:
        raise ValidationError("A candidate with stop factors cannot be selected.")
    if not conflict_resolved:
        raise ValidationError("Conflict of interest must be resolved before selection.")


def validate_stage_evidence(stage: StageCode, evidence: Mapping[str, Any]) -> None:
    required_true: dict[StageCode, tuple[str, ...]] = {
        StageCode.UNIT_CHECK: ("slotConfirmed", "slotVacant"),
        StageCode.BUDGET_CHECK: ("budgetConfirmed",),
        StageCode.LEGAL_CHECK: ("legalApproved",),
        StageCode.SELECTION_AUTHORIZATION: ("authorized",),
        StageCode.APPLICATION_INTAKE: ("consentVerified",),
        StageCode.FINALIST_CHECKS: ("identityVerified", "conflictChecked"),
        StageCode.EMPLOYMENT_CONTRACT: ("contractSignedByEmployer", "contractSignedByCandidate"),
        StageCode.HIRING_ORDER: ("contractSigned", "orderSigned"),
        StageCode.ESUTD_AND_PERSONNEL_FILE: ("esutdSubmitted", "personnelFileCreated"),
        StageCode.ACCESS_AND_FIRST_DAY: ("minimumAccessApproved", "workplaceReady"),
        StageCode.PROBATION: ("planSigned", "finalReviewRecorded"),
    }
    missing = [name for name in required_true.get(stage, ()) if evidence.get(name) is not True]
    if missing:
        raise ValidationError(
            "Required stage evidence is missing.",
            details={"stage": stage.value, "missing": missing},
        )
    if stage == StageCode.APPLICATION_INTAKE:
        application = evidence.get("initialApplication")
        if not isinstance(application, Mapping):
            raise ValidationError("Initial application data is required at application intake.")
        validate_initial_application(application)
    elif stage == StageCode.PROFESSIONAL_ASSESSMENT:
        try:
            score = Decimal(str(evidence["score"]))
        except (KeyError, ValueError, TypeError):
            raise ValidationError("Professional assessment score is required.") from None
        validate_professional_assessment(score, str(evidence.get("factualEvidence", "")))
    elif stage == StageCode.COMMISSION_RESULT:
        try:
            validate_commission_result(
                present_voters=int(evidence["presentVoters"]),
                total_score=Decimal(str(evidence["totalScore"])),
                professional_assignment_score=Decimal(str(evidence["professionalAssignmentScore"])),
                professional_interview_score=Decimal(str(evidence["professionalInterviewScore"])),
                stop_factors=list(evidence.get("stopFactors", [])),
                conflict_resolved=evidence.get("conflictResolved") is True,
            )
        except (KeyError, ValueError, TypeError):
            raise ValidationError("Complete commission evidence is required.") from None
