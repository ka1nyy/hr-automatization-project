"""FastAPI exception handlers implementing the stable error envelope."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException

from app.core.errors.codes import ErrorCode
from app.core.errors.exceptions import ApplicationError, ConcurrencyConflictError
from app.core.logging.context import get_request_id

_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.AUTH_UNAUTHENTICATED: 401,
    ErrorCode.AUTH_FORBIDDEN: 403,
    ErrorCode.AUTH_SCOPE_VIOLATION: 403,
    ErrorCode.RESOURCE_NOT_FOUND: 404,
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.SENSITIVE_DATA_FORBIDDEN: 403,
}


def _status_for(error: ApplicationError) -> int:
    return _STATUS_BY_CODE.get(error.code, 409)


def _response(
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code.value,
                "message": message,
                "details": details or {},
                "requestId": get_request_id(),
            }
        },
        headers=headers,
    )


async def application_error_handler(_request: Request, exc: ApplicationError) -> JSONResponse:
    return _response(
        status_code=_status_for(exc),
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers={"WWW-Authenticate": "Bearer"}
        if exc.code is ErrorCode.AUTH_UNAUTHENTICATED
        else None,
    )


async def request_validation_error_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    problems = [
        {
            "location": [str(part) for part in error.get("loc", ())],
            "message": str(error.get("msg", "Invalid value")),
            "type": str(error.get("type", "validation_error")),
        }
        for error in exc.errors()
    ]
    return _response(
        status_code=422,
        code=ErrorCode.VALIDATION_FAILED,
        message="The request failed validation.",
        details={"problems": problems},
    )


async def stale_data_error_handler(_request: Request, _exc: StaleDataError) -> JSONResponse:
    error = ConcurrencyConflictError()
    return _response(
        status_code=409,
        code=error.code,
        message=error.message,
        details=error.details,
    )


async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    code = {
        401: ErrorCode.AUTH_UNAUTHENTICATED,
        403: ErrorCode.AUTH_FORBIDDEN,
        404: ErrorCode.RESOURCE_NOT_FOUND,
        422: ErrorCode.VALIDATION_FAILED,
    }.get(exc.status_code, ErrorCode.VALIDATION_FAILED)
    message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return _response(
        status_code=exc.status_code,
        code=code,
        message=message,
        headers=exc.headers,
    )


def install_exception_handlers(app: FastAPI) -> None:
    """Register only understood failures; unexpected exceptions remain visible to observability."""

    app.add_exception_handler(ApplicationError, application_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StaleDataError, stale_data_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_error_handler)  # type: ignore[arg-type]
