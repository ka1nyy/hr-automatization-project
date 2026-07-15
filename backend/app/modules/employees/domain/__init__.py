"""Pure employee domain model."""

from .entities import Delegation, Employee, EmployeeAssignment, Person
from .enums import (
    AssignmentStatus,
    AssignmentType,
    DelegationScopeType,
    DelegationStatus,
    EmploymentStatus,
    PersonStatus,
)
from .errors import EmployeeDomainError

__all__ = [
    "AssignmentStatus",
    "AssignmentType",
    "Delegation",
    "DelegationScopeType",
    "DelegationStatus",
    "Employee",
    "EmployeeAssignment",
    "EmployeeDomainError",
    "EmploymentStatus",
    "Person",
    "PersonStatus",
]
