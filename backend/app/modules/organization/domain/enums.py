"""Organization domain enums.

Enum values are deliberately stable API/database values. Human-readable labels are
reference data and must never be used for authorization or routing.
"""

from enum import StrEnum


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class StructureVersionStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ReviewRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    RETURNED = "returned"
    CANCELLED = "cancelled"


class StaffingSlotStatus(StrEnum):
    PLANNED = "planned"
    APPROVED = "approved"
    VACANT = "vacant"
    OCCUPIED = "occupied"
    TEMPORARILY_BLOCKED = "temporarily_blocked"
    CLOSING = "closing"
    CLOSED = "closed"


class EmploymentType(StrEnum):
    PERMANENT = "permanent"
    PART_TIME = "part_time"
    TEMPORARY = "temporary"
    ACTING = "acting"


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
