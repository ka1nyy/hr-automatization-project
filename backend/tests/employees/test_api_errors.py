"""API errors use the stable envelope and never leak exception internals."""

from datetime import date
from uuid import uuid4

import pytest
from app.modules.employees.api import create_employee_router, employee_exception_handler
from app.modules.employees.application.commands import CreateEmployeeCommand
from app.modules.employees.application.functions import (
    EmployeeFunctionService,
    default_employee_function_registry,
)
from app.modules.employees.application.ports import Actor
from app.modules.employees.application.service import EmployeeService
from app.modules.employees.domain.errors import EmployeeDomainError
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from .fakes import FakeUnitOfWork, TestProtector


def _build_app(service: EmployeeService, actor_holder: dict[str, Actor]) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(EmployeeDomainError, employee_exception_handler)  # type: ignore[arg-type]
    functions = EmployeeFunctionService(default_employee_function_registry(), service)
    app.include_router(
        create_employee_router(lambda: service, lambda: actor_holder["actor"], lambda: functions),
        prefix="/api/v1",
    )
    return app


@pytest.mark.asyncio
async def test_current_employee_endpoint_resolves_the_actor() -> None:
    organization_id = uuid4()
    service = EmployeeService(FakeUnitOfWork(), TestProtector())
    hr_actor = Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset({"employees.read", "employees.create"}),
        organization_wide=True,
    )
    details = await service.create_employee(
        hr_actor,
        CreateEmployeeCommand(
            first_name="Aigul",
            last_name="Sarsenova",
            employee_number="ME-001",
            hire_date=date(2026, 1, 1),
        ),
    )
    actor_holder = {
        "actor": Actor(
            user_id=hr_actor.user_id,
            organization_id=organization_id,
            permissions=frozenset({"employees.read"}),
            organization_wide=True,
            employee_id=details.employee.id,
        )
    }
    app = _build_app(service, actor_holder)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/employees/me")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == str(details.employee.id)

        actor_holder["actor"] = Actor(
            user_id=uuid4(),
            organization_id=organization_id,
            permissions=frozenset({"employees.read"}),
            organization_wide=True,
        )
        orphan = await client.get("/api/v1/employees/me")
        assert orphan.status_code == 404
        assert orphan.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_not_found_error_has_stable_contract() -> None:
    organization_id = uuid4()
    service = EmployeeService(FakeUnitOfWork(), TestProtector())
    actor = Actor(
        user_id=uuid4(),
        organization_id=organization_id,
        permissions=frozenset({"employees.read"}),
        organization_wide=True,
    )
    app = FastAPI()
    app.add_exception_handler(EmployeeDomainError, employee_exception_handler)  # type: ignore[arg-type]
    functions = EmployeeFunctionService(default_employee_function_registry(), service)
    app.include_router(
        create_employee_router(lambda: service, lambda: actor, lambda: functions),
        prefix="/api/v1",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/employees/{uuid4()}")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert set(payload["error"]) == {"code", "message", "details", "requestId"}
