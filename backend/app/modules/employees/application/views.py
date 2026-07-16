"""Framework-neutral employee result DTOs."""

from dataclasses import dataclass

from ..domain.entities import Delegation, Employee, EmployeeAbsence, EmployeeAssignment, Person


@dataclass(frozen=True, slots=True)
class EmployeeDetails:
    employee: Employee
    person: Person
    assignments: tuple[EmployeeAssignment, ...]
    revealed_iin: str | None = None


@dataclass(frozen=True, slots=True)
class EmployeePage:
    items: tuple[EmployeeDetails, ...]
    total: int


@dataclass(frozen=True, slots=True)
class DelegationPage:
    items: tuple[Delegation, ...]
    total: int


@dataclass(frozen=True, slots=True)
class VacationBalance:
    year: int
    entitlement: int
    used: int
    remaining: int


@dataclass(frozen=True, slots=True)
class EmployeeAbsenceList:
    items: tuple[EmployeeAbsence, ...]
    vacation_balance: VacationBalance
