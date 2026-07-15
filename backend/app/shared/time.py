"""Timezone-safe date and time helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize an aware timestamp to UTC and reject ambiguous naive values."""

    if value.tzinfo is None or value.utcoffset() is None:
        msg = "a timezone-aware datetime is required"
        raise ValueError(msg)
    return value.astimezone(UTC)


def date_ranges_overlap(
    first_start: date,
    first_end: date | None,
    second_start: date,
    second_end: date | None,
) -> bool:
    """Return whether two inclusive, optionally open-ended date ranges overlap."""

    return (first_end is None or second_start <= first_end) and (
        second_end is None or first_start <= second_end
    )
