from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.errors import ValidationError
from app.modules.regulated_hiring.application.service import RegulatedHiringService
from app.modules.regulated_hiring.domain.catalog import FORM_POLICIES, STAGE_POLICIES
from app.modules.regulated_hiring.domain.enums import StageCode
from app.modules.regulated_hiring.domain.rules import (
    calculate_commission_score,
    require_confirmed_authority,
    validate_initial_application,
    validate_professional_assessment,
    validate_stage_evidence,
)


def test_normative_catalog_has_all_numbered_stages_and_forms() -> None:
    assert [item.sequence for item in STAGE_POLICIES] == list(range(23))
    assert len({item.code for item in STAGE_POLICIES}) == 23
    assert [item.sequence for item in FORM_POLICIES] == list(range(1, 22))
    assert [item.code for item in FORM_POLICIES] == [
        f"NAIM-{number:02d}" for number in range(1, 22)
    ]


def test_unconfirmed_staffing_authority_cannot_start_legal_hiring() -> None:
    with pytest.raises(ValidationError):
        require_confirmed_authority("model", entity_type="staffing_slot")
    with pytest.raises(ValidationError):
        require_confirmed_authority("document_required", entity_type="staffing_slot")
    require_confirmed_authority("confirmed", entity_type="staffing_slot")


def test_initial_application_requires_consent_and_rejects_finalist_data() -> None:
    with pytest.raises(ValidationError):
        validate_initial_application({"consentGranted": True, "iin": "forbidden"})
    with pytest.raises(ValidationError):
        validate_initial_application({"name": "Candidate"})
    validate_initial_application({"consentGranted": True, "name": "Candidate"})


def test_professional_assessment_threshold_and_evidence_are_mandatory() -> None:
    with pytest.raises(ValidationError):
        validate_professional_assessment(Decimal("59.99"), "documented")
    with pytest.raises(ValidationError):
        validate_professional_assessment(Decimal("60"), "")
    validate_professional_assessment(Decimal("60"), "Signed assessment sheet")


def test_commission_score_uses_the_approved_one_hundred_point_model() -> None:
    score = calculate_commission_score(
        {
            "relevant_experience": Decimal("10"),
            "professional_assignment": Decimal("25"),
            "professional_interview": Decimal("25"),
            "behavioral_competencies": Decimal("20"),
            "management_case": Decimal("15"),
            "motivation": Decimal("5"),
        }
    )
    assert score == Decimal("100")


def test_commission_stage_enforces_quorum_and_component_thresholds() -> None:
    evidence = {
        "presentVoters": 4,
        "totalScore": 70,
        "professionalAssignmentScore": 60,
        "professionalInterviewScore": 60,
        "stopFactors": [],
        "conflictResolved": True,
    }
    validate_stage_evidence(StageCode.COMMISSION_RESULT, evidence)
    with pytest.raises(ValidationError):
        validate_stage_evidence(StageCode.COMMISSION_RESULT, {**evidence, "presentVoters": 3})


def test_contract_and_order_cannot_be_approved_out_of_sequence() -> None:
    with pytest.raises(ValidationError):
        validate_stage_evidence(
            StageCode.EMPLOYMENT_CONTRACT,
            {"contractSignedByEmployer": True, "contractSignedByCandidate": False},
        )
    with pytest.raises(ValidationError):
        validate_stage_evidence(StageCode.HIRING_ORDER, {"orderSigned": True})


def test_stage_due_date_skips_weekends() -> None:
    friday = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)
    assert RegulatedHiringService._add_working_days(friday, 1) == datetime(
        2026, 7, 20, 9, 0, tzinfo=UTC
    )
