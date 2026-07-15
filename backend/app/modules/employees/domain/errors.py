"""Stable employee-domain failures shared by all adapters."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EmployeeDomainError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    status_code: int = 409

    def __str__(self) -> str:
        return self.message


def validation_error(message: str, **details: Any) -> EmployeeDomainError:
    return EmployeeDomainError("VALIDATION_FAILED", message, details, 422)
