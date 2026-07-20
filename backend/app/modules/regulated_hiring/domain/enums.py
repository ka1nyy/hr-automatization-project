from enum import StrEnum


class AuthorityStatus(StrEnum):
    CONFIRMED = "confirmed"
    MODEL = "model"
    DOCUMENT_REQUIRED = "document_required"


class CaseStatus(StrEnum):
    ACTIVE = "active"
    RETURNED = "returned"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class StageStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    RETURNED = "returned"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class FormStatus(StrEnum):
    DRAFT = "draft"
    SIGNED = "signed"
    SUPERSEDED = "superseded"
    VOIDED = "voided"


class StageCode(StrEnum):
    NEED_SIGNAL = "need_signal"
    UNIT_CHECK = "unit_check"
    REQUEST_FORMATION = "request_formation"
    NEED_APPROVAL = "need_approval"
    BUDGET_CHECK = "budget_check"
    LEGAL_CHECK = "legal_check"
    SELECTION_AUTHORIZATION = "selection_authorization"
    VACANCY_PUBLICATION = "vacancy_publication"
    APPLICATION_INTAKE = "application_intake"
    FORMAL_SCREENING = "formal_screening"
    PHONE_SCREENING = "phone_screening"
    PROFESSIONAL_ASSESSMENT = "professional_assessment"
    STRUCTURED_INTERVIEW = "structured_interview"
    FINALIST_CHECKS = "finalist_checks"
    COMMISSION_RESULT = "commission_result"
    FINAL_DECISION = "final_decision"
    OFFER = "offer"
    DOCUMENT_COLLECTION = "document_collection"
    EMPLOYMENT_CONTRACT = "employment_contract"
    HIRING_ORDER = "hiring_order"
    ESUTD_AND_PERSONNEL_FILE = "esutd_and_personnel_file"
    ACCESS_AND_FIRST_DAY = "access_and_first_day"
    PROBATION = "probation"
