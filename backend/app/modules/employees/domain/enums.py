"""Employee-domain enumerations persisted as stable string values."""

from enum import StrEnum


class PersonStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class EmploymentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ENDED = "ended"


class AssignmentType(StrEnum):
    PERMANENT = "permanent"
    TEMPORARY = "temporary"
    ACTING = "acting"
    PART_TIME = "part_time"
    CONCURRENT = "concurrent"


class AssignmentStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    PLANNED = "planned"
    ACTIVE = "active"
    SCHEDULED_END = "scheduled_end"
    ENDED = "ended"
    CANCELLED = "cancelled"


class AssignmentReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AbsenceType(StrEnum):
    VACATION = "vacation"
    SICK_LEAVE = "sick_leave"
    BUSINESS_TRIP = "business_trip"
    DAY_OFF = "day_off"


class AbsenceStatus(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DelegationScopeType(StrEnum):
    PERMISSIONS = "permissions"
    ORGANIZATION = "organization"
    UNIT = "unit"
    PROCESS = "process"
    REQUEST = "request"


class DelegationStatus(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
