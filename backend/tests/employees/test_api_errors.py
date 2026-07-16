"""API errors use the stable envelope and never leak exception internals."""

from uuid import uuid4

import pytest
from app.modules.employees.api import create_employee_router, employee_exception_handler
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
