"""Provider-neutral user account domain objects."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


def _utc_now() -> datetime:
    return datetime.now(UTC)


class UserAccountStatus(StrEnum):
    """Lifecycle state of a login identity."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


@dataclass(frozen=True, slots=True, kw_only=True)
class UserAccount:
    """A provider-independent account mapped to an external identity subject."""

    external_subject: str
    username: str
    display_name: str
    id: UUID = field(default_factory=uuid4)
    email: str | None = None
    employee_id: UUID | None = None
    status: UserAccountStatus = UserAccountStatus.ACTIVE
    last_login_at: datetime | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    revision: int = 1

    def __post_init__(self) -> None:
        if not self.external_subject.strip():
            raise ValueError("external_subject must not be blank")
        if not self.username.strip():
            raise ValueError("username must not be blank")
        if not self.display_name.strip():
            raise ValueError("display_name must not be blank")
        if self.revision < 1:
            raise ValueError("revision must be positive")

    @property
    def is_active(self) -> bool:
        return self.status is UserAccountStatus.ACTIVE

    def record_login(self, *, at: datetime | None = None) -> UserAccount:
        if not self.is_active:
            raise ValueError("inactive accounts cannot log in")
        timestamp = at or _utc_now()
        return replace(
            self,
            last_login_at=timestamp,
            updated_at=timestamp,
            revision=self.revision + 1,
        )
