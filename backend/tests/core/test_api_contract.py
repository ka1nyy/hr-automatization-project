"""Composition-root and OpenAPI security contract checks."""

from typing import Any

import app.main as main_module
from app.core.config import Environment, Settings
from app.main import create_app
from app.open_api import validate
from fastapi import APIRouter
from fastapi.testclient import TestClient

HTTP_METHODS = frozenset({"delete", "get", "head", "options", "patch", "post", "put", "trace"})


def _test_settings(*, sensitive_data_key: str | None = None) -> Settings:
    return Settings(
        environment=Environment.TEST,
        dev_auth_enabled=False,
        sensitive_data_key=sensitive_data_key,
        oidc_issuer=None,
        oidc_audience=None,
        oidc_jwks_url=None,
    )


def test_openapi_documents_bearer_auth_and_stable_error_envelope() -> None:
    application = create_app(_test_settings())

    schema = application.openapi()

    assert validate(schema) == []
    assert schema["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "OIDC access token. Development-only identity headers are not "
            "production authentication."
        ),
    }
    assert schema["components"]["schemas"]["ErrorEnvelope"]["required"] == ["error"]
    assert set(schema["components"]["schemas"]["ErrorBody"]["required"]) == {
        "code",
        "message",
        "details",
        "requestId",
    }

    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if path.startswith("/health/"):
                assert "security" not in operation
                continue
            assert operation["security"] == [{"BearerAuth": []}]
            for response_code in ("401", "403", "404", "409", "422"):
                response_schema = operation["responses"][response_code]["content"][
                    "application/json"
                ]["schema"]
                assert response_schema == {"$ref": "#/components/schemas/ErrorEnvelope"}


def test_employee_service_is_lazy_and_bound_to_create_app_settings(monkeypatch: Any) -> None:
    constructed_with: list[str] = []
    service_providers: list[Any] = []

    class ProbeSensitiveDataProtector:
        def __init__(self, key: str) -> None:
            constructed_with.append(key)

        def protect(self, value: str) -> str:
            return value

        def reveal(self, value: str) -> str:
            return value

    monkeypatch.setattr(
        main_module,
        "FernetSensitiveDataProtector",
        ProbeSensitiveDataProtector,
    )

    def capture_employee_router(
        service_provider: Any, _actor_provider: Any, _function_service_provider: Any
    ) -> APIRouter:
        service_providers.append(service_provider)
        return APIRouter()

    monkeypatch.setattr(main_module, "create_employee_router", capture_employee_router)
    create_app(_test_settings(sensitive_data_key="passed-runtime-key"))

    assert constructed_with == []
    assert len(service_providers) == 1
    service_provider = service_providers[0]
    first_service = service_provider()
    second_service = service_provider()

    assert constructed_with == ["passed-runtime-key"]
    assert first_service is second_service


def test_paginated_collections_publish_allowlisted_sort_contracts() -> None:
    schema = create_app(_test_settings()).openapi()
    expected = {
        "/api/v1/employees": {"employeeNumber", "-employeeNumber", "hireDate", "-hireDate"},
        "/api/v1/delegations": {"effectiveFrom", "-effectiveFrom", "status", "-status"},
        "/api/v1/organization/structure/versions": {"versionNumber", "-versionNumber"},
        "/api/v1/positions": {"code", "-code", "name", "-name"},
        "/api/v1/staffing-slots": {
            "organizationUnitId",
            "-organizationUnitId",
            "fullTimeEquivalent",
            "-fullTimeEquivalent",
        },
        "/api/v1/access/roles": {"code", "-code", "name", "-name"},
        "/api/v1/access/permissions": {"code", "-code", "name", "-name"},
        "/api/v1/audit/events": {"occurredAt", "-occurredAt", "action", "-action"},
    }

    for path, required_values in expected.items():
        parameters = schema["paths"][path]["get"]["parameters"]
        sort_parameter = next(item for item in parameters if item["name"] == "sort")
        assert required_values <= set(sort_parameter["schema"]["enum"])


def test_compiled_frontend_is_served_with_spa_fallback(tmp_path: Any) -> None:
    frontend_dir = tmp_path / "frontend-dist"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("<main>HR application</main>", encoding="utf-8")
    (frontend_dir / "asset.txt").write_text("compiled asset", encoding="utf-8")
    settings = _test_settings().model_copy(update={"frontend_dist_path": str(frontend_dir)})

    with TestClient(create_app(settings)) as client:
        assert client.get("/").text == "<main>HR application</main>"
        assert client.get("/hr/employees").text == "<main>HR application</main>"
        assert client.get("/asset.txt").text == "compiled asset"
        assert client.get("/api/v1/not-a-route").status_code == 404
