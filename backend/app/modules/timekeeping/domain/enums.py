"""Timekeeping enumerations persisted as stable string values."""

from enum import StrEnum


class TimeCodeCategory(StrEnum):
    """Determines how a timesheet entry is interpreted downstream."""

    WORK = "work"
    OVERTIME = "overtime"
    NIGHT = "night"
    HOLIDAY = "holiday"
    WEEKEND = "weekend"
    LEAVE = "leave"
    SICK = "sick"
    BUSINESS_TRIP = "business_trip"
    ABSENCE = "absence"
    UNPAID_ABSENCE = "unpaid_absence"


class TimesheetPeriodStatus(StrEnum):
    """Section 8: HR closes the period, then hands it to accounting."""

    OPEN = "open"
    UNDER_REVIEW = "under_review"
    CLOSED = "closed"
    SENT_TO_ACCOUNTING = "sent_to_accounting"
    REOPENED = "reopened"


class TimesheetEntrySource(StrEnum):
    """Provenance of a timesheet row.

    Section 8 forbids typing a timesheet from scratch: rows are derived from the
    schedule and from approved events, and anything manual carries a reason.
    """

    SCHEDULE = "schedule"
    ABSENCE = "absence"
    LEAVE_REQUEST = "leave_request"
    BUSINESS_TRIP = "business_trip"
    MANUAL = "manual"
    CORRECTION = "correction"


class TimesheetCorrectionStatus(StrEnum):
    """The separate correction process required once a period is closed."""

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    UNDER_APPROVAL = "under_approval"
    APPLIED = "applied"
    RETURNED = "returned"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class WorkScheduleKind(StrEnum):
    FIVE_DAY = "five_day"
    SIX_DAY = "six_day"
    SHIFT = "shift"
    FLEXIBLE = "flexible"
    SUMMARIZED = "summarized"
