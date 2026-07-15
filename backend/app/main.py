"""FastAPI composition root for the Module 1 modular monolith."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.core.audit.router import router as audit_router
from app.core.config import Settings, get_settings
from app.core.database.session import async_session_factory, close_database, ping_database
from app.core.errors.handlers import install_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.factory import build_token_authenticator
from app.core.security.middleware import AuthenticationMiddleware
from app.core.security.ports import AuthorizationPort
from app.modules.access_control.api import router as access_router
from app.modules.access_control.api.dependencies import (
    get_database_authorization_port,
    get_organization_scope_resolver,
)
from app.modules.access_control.application.ports import OrganizationScopeResolver
from app.modules.business_processes.api.routes import router as business_process_router
from app.modules.employees.api import (
    create_employee_router,
    employee_exception_handler,
    get_employee_actor,
)
from app.modules.employees.application.service import EmployeeService
from app.modules.employees.domain.errors import EmployeeDomainError
from app.modules.employees.infrastructure.authorization_adapter import (
    DelegationAwareAuthorizationAdapter,
)
from app.modules.employees.infrastructure.core_adapters import CoreAuditSink, CoreOutboxSink
from app.modules.employees.infrastructure.crypto import FernetSensitiveDataProtector
from app.modules.employees.infrastructure.organization_adapter import (
    SqlAlchemyEmployeePolicyReader,
    SqlAlchemyStaffingSlotReader,
)
from app.modules.employees.infrastructure.repositories import (
    SqlAlchemyEmployeeUnitOfWorkFactory,
)
from app.modules.identity.api import get_database_principal
from app.modules.organization.api.routes import (
    organization_exception_handler,
)
from app.modules.organization.api.routes import (
    router as organization_router,
)
from app.modules.organization.domain.errors import OrganizationError
from app.modules.organization.infrastructure.scope_factory import (
    SessionFactoryOrganizationScopeResolver,
)
from app.shared.api import DataResponse, ResponseMeta


class HealthStatus(BaseModel):
    status: str


def get_independent_organization_scope_resolver() -> OrganizationScopeResolver:
    return SessionFactoryOrganizationScopeResolver(async_session_factory)


def get_delegation_aware_authorization(
    base: Annotated[AuthorizationPort, Depends(get_database_authorization_port)],
) -> AuthorizationPort:
    return DelegationAwareAuthorizationAdapter(base, async_session_factory)


_HTTP_METHODS = frozenset({"delete", "get", "head", "options", "patch", "post", "put", "trace"})


def _install_openapi_contract(application: FastAPI) -> None:
    """Document middleware authentication and the runtime's stable error envelope."""

    def build_openapi() -> dict[str, Any]:
        if application.openapi_schema is not None:
            return application.openapi_schema
        schema = get_openapi(
            title=application.title,
            version=application.version,
            openapi_version=application.openapi_version,
            summary=application.summary,
            description=application.description,
            routes=application.routes,
        )
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "OIDC access token. Development-only identity headers are not "
                "production authentication."
            ),
        }
        schemas = components.setdefault("schemas", {})
        schemas["ErrorBody"] = {
            "type": "object",
            "required": ["code", "message", "details", "requestId"],
            "properties": {
                "code": {"type": "string", "description": "Stable machine-readable error code."},
                "message": {"type": "string"},
                "details": {"type": "object", "additionalProperties": True},
                "requestId": {"type": "string", "format": "uuid"},
            },
            "additionalProperties": False,
        }
        schemas["ErrorEnvelope"] = {
            "type": "object",
            "required": ["error"],
            "properties": {"error": {"$ref": "#/components/schemas/ErrorBody"}},
            "additionalProperties": False,
        }
        response_descriptions = {
            "401": "Authentication is required or the bearer token is invalid.",
            "403": "The authenticated principal lacks permission or scope.",
            "404": "The requested resource was not found.",
            "409": "The request conflicts with current state or revision.",
            "422": "The request failed validation.",
        }
        error_schema = {"$ref": "#/components/schemas/ErrorEnvelope"}
        for path, path_item in schema.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method not in _HTTP_METHODS or not isinstance(operation, dict):
                    continue
                if path.startswith("/health/"):
                    operation.pop("security", None)
                    continue
                operation["security"] = [{"BearerAuth": []}]
                responses = operation.setdefault("responses", {})
                for response_code, description in response_descriptions.items():
                    responses[response_code] = {
                        "description": description,
                        "content": {"application/json": {"schema": error_schema}},
                    }
        application.openapi_schema = schema
        return schema

    application.openapi = build_openapi  # type: ignore[method-assign]


def _employee_service_provider(runtime: Settings) -> Callable[[], EmployeeService]:
    """Bind the lazy employee service to this app instance's validated settings."""

    @lru_cache(maxsize=1)
    def provide() -> EmployeeService:
        uow_factory = SqlAlchemyEmployeeUnitOfWorkFactory(
            async_session_factory,
            SqlAlchemyStaffingSlotReader,
            SqlAlchemyEmployeePolicyReader,
            CoreAuditSink,
            CoreOutboxSink,
        )
        return EmployeeService(
            uow_factory,
            FernetSensitiveDataProtector(runtime.require_sensitive_data_key()),
        )

    return provide


def _install_frontend(application: FastAPI, runtime: Settings) -> None:
    """Serve the repository's compiled SPA from the backend process when configured."""

    if not runtime.frontend_dist_path:
        return

    frontend_root = Path(runtime.frontend_dist_path).resolve()
    index_file = frontend_root / "index.html"
    if not index_file.is_file():
        msg = f"Compiled frontend index is missing: {index_file}"
        raise RuntimeError(msg)

    api_prefix = runtime.api_prefix.rstrip("/")

    @application.get("/{requested_path:path}", include_in_schema=False)
    async def serve_frontend(requested_path: str) -> FileResponse:
        request_path = f"/{requested_path}"
        if request_path == api_prefix or request_path.startswith(f"{api_prefix}/"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        candidate = (frontend_root / requested_path).resolve()
        try:
            candidate.relative_to(frontend_root)
        except ValueError:
            candidate = index_file

        return FileResponse(candidate if candidate.is_file() else index_file)


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or get_settings()
    employee_service_provider = _employee_service_provider(runtime)
    configure_logging(runtime.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await close_database()

    application = FastAPI(
        title=runtime.app_name,
        version="1.0.0",
        description=(
            "Module 1 API for identity, scoped access, versioned organization structures, "
            "staffing, employees, assignments, delegation, audit, and integration events."
        ),
        lifespan=lifespan,
    )
    allowed_headers = ["Authorization", "Content-Type", "X-Request-Id"]
    if runtime.is_development and runtime.dev_auth_enabled:
        allowed_headers.extend(
            [
                "X-Dev-User",
                "X-Dev-Organization-Id",
                "X-Dev-Employee-Id",
                "X-Dev-Unit-Ids",
                "X-Dev-Permissions",
                "X-Dev-Roles",
            ]
        )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=allowed_headers,
        expose_headers=["X-Request-Id"],
    )
    application.add_middleware(
        AuthenticationMiddleware,
        settings=runtime,
        token_authenticator=build_token_authenticator(runtime),
    )
    application.add_middleware(RequestContextMiddleware)

    install_exception_handlers(application)
    application.add_exception_handler(OrganizationError, organization_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(EmployeeDomainError, employee_exception_handler)  # type: ignore[arg-type]

    application.dependency_overrides[get_current_principal] = get_database_principal
    application.dependency_overrides[get_organization_scope_resolver] = (
        get_independent_organization_scope_resolver
    )
    application.dependency_overrides[get_authorization_port] = get_delegation_aware_authorization

    @application.get(
        "/health/live",
        response_model=DataResponse[HealthStatus],
        tags=["health"],
    )
    async def live() -> DataResponse[HealthStatus]:
        return DataResponse(
            data=HealthStatus(status="ok"),
            meta=ResponseMeta(),
        )

    @application.get(
        "/health/ready",
        response_model=DataResponse[HealthStatus],
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": DataResponse[HealthStatus]}},
        tags=["health"],
    )
    async def ready() -> DataResponse[HealthStatus] | JSONResponse:
        if await ping_database():
            return DataResponse(data=HealthStatus(status="ready"), meta=ResponseMeta())
        payload: DataResponse[HealthStatus] = DataResponse(
            data=HealthStatus(status="not_ready"),
            meta=ResponseMeta(),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(mode="json", by_alias=True),
        )

    application.include_router(organization_router, prefix=runtime.api_prefix)
    application.include_router(access_router, prefix=runtime.api_prefix)
    application.include_router(audit_router, prefix=runtime.api_prefix)
    application.include_router(business_process_router, prefix=runtime.api_prefix)
    application.include_router(
        create_employee_router(employee_service_provider, get_employee_actor),
        prefix=runtime.api_prefix,
    )
    _install_openapi_contract(application)
    _install_frontend(application, runtime)
    return application


app = create_app()
