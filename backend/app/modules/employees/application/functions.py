"""Role-configurable business functions surfaced to clients as available actions.

Each function couples a stable key with the permission that unlocks it, an
availability rule against the employee's state, and a payload contract. Roles
gain or lose functions through the RBAC catalog (role -> permission), never
through code changes here or in the client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from ..domain.enums import AssignmentStatus, AssignmentType, EmploymentStatus
from ..domain.errors import EmployeeDomainError
from .commands import HireEmployeeCommand, TerminateEmployeeCommand, TransferEmployeeCommand
from .ports import Actor
from .service import EmployeeService
from .views import EmployeeDetails


class FunctionScope(StrEnum):
    COLLECTION = "collection"
    EMPLOYEE = "employee"


@dataclass(frozen=True, slots=True)
class FunctionDescriptor:
    key: str
    title: str
    description: str
    scope: FunctionScope
    permission: str


class _PayloadModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


def _parse_payload[PayloadT: _PayloadModel](
    model: type[PayloadT], payload: Mapping[str, Any]
) -> PayloadT:
    try:
        return model.model_validate(dict(payload))
    except ValidationError as exc:
        raise EmployeeDomainError(
            "VALIDATION_FAILED",
            "The function payload is invalid.",
            {
                "problems": [
                    {
                        "field": ".".join(str(part) for part in error["loc"]),
                        "message": error["msg"],
                    }
                    for error in exc.errors()
                ]
            },
            422,
        ) from exc


class EmployeeFunction(ABC):
    """A single business operation invokable through the generic function API."""

    descriptor: ClassVar[FunctionDescriptor]

    def is_available(self, details: EmployeeDetails) -> bool:
        """Report whether the employee's current state admits this function."""

        del details
        return True

    @abstractmethod
    async def invoke(
        self,
        actor: Actor,
        service: EmployeeService,
        payload: Mapping[str, Any],
        employee_id: UUID | None,
    ) -> EmployeeDetails: ...


class _HirePayload(_PayloadModel):
    first_name: str = Field(min_length=1, max_length=160)
    last_name: str = Field(min_length=1, max_length=160)
    employee_number: str = Field(min_length=1, max_length=64)
    hire_date: date
    middle_name: str | None = Field(default=None, max_length=160)
    display_name: str | None = Field(default=None, max_length=500)
    iin: str | None = Field(default=None, min_length=12, max_length=12, repr=False)
    birth_date: date | None = Field(default=None, repr=False)
    personal_email: str | None = Field(default=None, max_length=320, repr=False)
    phone: str | None = Field(default=None, max_length=80, repr=False)
    corporate_email: str | None = Field(default=None, max_length=320)
    staffing_slot_id: UUID | None = None
    assignment_type: AssignmentType = AssignmentType.PERMANENT
    full_time_equivalent: Decimal = Field(
        default=Decimal("1.00"), gt=0, le=1, max_digits=5, decimal_places=2
    )


class HireEmployeeFunction(EmployeeFunction):
    descriptor = FunctionDescriptor(
        key="employee.hire",
        title="Нанять сотрудника",
        description="Создать сотрудника и назначить его на штатную единицу.",
        scope=FunctionScope.COLLECTION,
        permission="employees.hire",
    )

    async def invoke(
        self,
        actor: Actor,
        service: EmployeeService,
        payload: Mapping[str, Any],
        employee_id: UUID | None,
    ) -> EmployeeDetails:
        del employee_id
        parsed = _parse_payload(_HirePayload, payload)
        command = _to_command(HireEmployeeCommand, parsed)
        return await service.hire_employee(actor, command)


class _TerminatePayload(_PayloadModel):
    termination_date: date
    reason: str = Field(min_length=1, max_length=1000)
    revision: int = Field(ge=1)


class TerminateEmployeeFunction(EmployeeFunction):
    descriptor = FunctionDescriptor(
        key="employee.terminate",
        title="Уволить сотрудника",
        description="Завершить трудовые отношения и закрыть активные назначения.",
        scope=FunctionScope.EMPLOYEE,
        permission="employees.terminate",
    )

    def is_available(self, details: EmployeeDetails) -> bool:
        employee = details.employee
        return (
            employee.active
            and employee.employment_status is not EmploymentStatus.ENDED
            and employee.termination_date is None
        )

    async def invoke(
        self,
        actor: Actor,
        service: EmployeeService,
        payload: Mapping[str, Any],
        employee_id: UUID | None,
    ) -> EmployeeDetails:
        if employee_id is None:
            raise _employee_required(self.descriptor.key)
        parsed = _parse_payload(_TerminatePayload, payload)
        command = _to_command(TerminateEmployeeCommand, parsed, employee_id=employee_id)
        return await service.terminate_employee(actor, command)


class _TransferPayload(_PayloadModel):
    staffing_slot_id: UUID
    effective_from: date
    reason: str = Field(min_length=1, max_length=1000)
    assignment_type: AssignmentType = AssignmentType.PERMANENT
    full_time_equivalent: Decimal = Field(
        default=Decimal("1.00"), gt=0, le=1, max_digits=5, decimal_places=2
    )


class TransferEmployeeFunction(EmployeeFunction):
    descriptor = FunctionDescriptor(
        key="employee.transfer",
        title="Перевести сотрудника",
        description="Перевести сотрудника на другую штатную единицу.",
        scope=FunctionScope.EMPLOYEE,
        permission="employees.transfer",
    )

    def is_available(self, details: EmployeeDetails) -> bool:
        employee = details.employee
        return (
            employee.active
            and employee.employment_status is not EmploymentStatus.ENDED
            and any(
                item.primary and item.effective_status() is AssignmentStatus.ACTIVE
                for item in details.assignments
            )
        )

    async def invoke(
        self,
        actor: Actor,
        service: EmployeeService,
        payload: Mapping[str, Any],
        employee_id: UUID | None,
    ) -> EmployeeDetails:
        if employee_id is None:
            raise _employee_required(self.descriptor.key)
        parsed = _parse_payload(_TransferPayload, payload)
        command = _to_command(TransferEmployeeCommand, parsed, employee_id=employee_id)
        return await service.transfer_employee(actor, command)


def _employee_required(function_key: str) -> EmployeeDomainError:
    return EmployeeDomainError(
        "VALIDATION_FAILED",
        "The function requires an employee.",
        {"functionKey": function_key},
        422,
    )


def _to_command[CommandT](
    command_type: type[CommandT], parsed: _PayloadModel, **extra: Any
) -> CommandT:
    try:
        return command_type(**parsed.model_dump(), **extra)
    except (TypeError, ValueError) as exc:
        raise EmployeeDomainError(
            "VALIDATION_FAILED",
            "The function payload is invalid.",
            {"message": str(exc)},
            422,
        ) from exc


class FunctionRegistry:
    """Key-addressable catalog of business functions; extended by registration only."""

    def __init__(self, functions: Iterable[EmployeeFunction]) -> None:
        self._functions: dict[str, EmployeeFunction] = {}
        for function in functions:
            self.register(function)

    def register(self, function: EmployeeFunction) -> None:
        key = function.descriptor.key
        if key in self._functions:
            msg = f"A business function with key {key!r} is already registered."
            raise ValueError(msg)
        self._functions[key] = function

    def get(self, key: str) -> EmployeeFunction:
        function = self._functions.get(key)
        if function is None:
            raise EmployeeDomainError(
                "RESOURCE_NOT_FOUND",
                "The business function is not registered.",
                {"functionKey": key},
                404,
            )
        return function

    def by_scope(self, scope: FunctionScope) -> tuple[EmployeeFunction, ...]:
        return tuple(
            function for function in self._functions.values() if function.descriptor.scope is scope
        )


def default_employee_function_registry() -> FunctionRegistry:
    return FunctionRegistry(
        (
            HireEmployeeFunction(),
            TerminateEmployeeFunction(),
            TransferEmployeeFunction(),
        )
    )


class EmployeeFunctionService:
    """Computes the actor's available functions and dispatches invocations."""

    def __init__(self, registry: FunctionRegistry, employees: EmployeeService) -> None:
        self._registry = registry
        self._employees = employees

    def list_collection_functions(self, actor: Actor) -> tuple[FunctionDescriptor, ...]:
        return tuple(
            function.descriptor
            for function in self._registry.by_scope(FunctionScope.COLLECTION)
            if "*" in actor.permissions or function.descriptor.permission in actor.permissions
        )

    async def list_employee_functions(
        self, actor: Actor, employee_id: UUID
    ) -> tuple[FunctionDescriptor, ...]:
        details = await self._employees.get_employee(actor, employee_id)
        descriptors: list[FunctionDescriptor] = []
        for function in self._registry.by_scope(FunctionScope.EMPLOYEE):
            if not function.is_available(details):
                continue
            if not await self._employees.has_employee_permission(
                actor, employee_id, function.descriptor.permission
            ):
                continue
            descriptors.append(function.descriptor)
        return tuple(descriptors)

    async def invoke_collection_function(
        self, actor: Actor, key: str, payload: Mapping[str, Any]
    ) -> EmployeeDetails:
        function = self._registry.get(key)
        if function.descriptor.scope is not FunctionScope.COLLECTION:
            raise EmployeeDomainError(
                "VALIDATION_FAILED",
                "The function must be invoked for a specific employee.",
                {"functionKey": key},
                422,
            )
        return await function.invoke(actor, self._employees, payload, None)

    async def invoke_employee_function(
        self, actor: Actor, employee_id: UUID, key: str, payload: Mapping[str, Any]
    ) -> EmployeeDetails:
        function = self._registry.get(key)
        if function.descriptor.scope is not FunctionScope.EMPLOYEE:
            raise EmployeeDomainError(
                "VALIDATION_FAILED",
                "The function is not invoked for a specific employee.",
                {"functionKey": key},
                422,
            )
        details = await self._employees.get_employee(actor, employee_id)
        if not function.is_available(details):
            raise EmployeeDomainError(
                "VERSION_CONFLICT",
                "The function is not available for the employee's current state.",
                {"functionKey": key},
            )
        return await function.invoke(actor, self._employees, payload, employee_id)
