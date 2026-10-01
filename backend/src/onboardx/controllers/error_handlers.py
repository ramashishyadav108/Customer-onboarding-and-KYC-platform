"""Maps domain errors and framework errors to the API error envelope (api-contracts 1.1)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from onboardx.domain.errors import DomainError

logger = logging.getLogger("onboardx.errors")

STATUS_BY_CODE = {
    "UNAUTHENTICATED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "INVALID_STATE": 409,
    "CASE_LOCKED": 409,
    "PROFILE_LOCKED": 409,
    "RULESET_IMMUTABLE": 409,
    "DRAFT_EXISTS": 409,
    "VALIDATION_ERROR": 422,
    "RULESET_INVALID": 422,
    "FILE_TOO_LARGE": 413,
    "UNSUPPORTED_MEDIA_TYPE": 415,
    "UNKNOWN_CHECKLIST_ITEM": 422,
    "MISSING_DOCUMENTS": 422,
    "MISSING_PROFILE": 422,
    "MISSING_PROFILE_FIELD": 422,
    "UNKNOWN_REASON_CODE": 422,
    "CONCURRENT_UPDATE": 409,
    "OVERRIDE_AUDIT_REQUIRED": 409,
    "ALREADY_DEACTIVATED": 409,
}


class ApiError(Exception):
    """Raised by controller dependencies (401, 403) and mapped to the envelope."""

    def __init__(
        self, status: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def envelope(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(status_code=status, content=body, headers=headers)


async def _api_error(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ApiError)  # noqa: S101 - registered for ApiError only
    return envelope(error.status, error.code, error.message, error.details)


async def _domain_error(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, DomainError)  # noqa: S101 - registered for DomainError only
    status = STATUS_BY_CODE.get(error.code, 400)
    return envelope(status, error.code, error.message, error.details)


async def _validation_error(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)  # noqa: S101
    fields = [
        {
            "field": ".".join(str(part) for part in item["loc"][1:]) or str(item["loc"][0]),
            "message": str(item["msg"]),
        }
        for item in error.errors()
    ]
    return envelope(422, "VALIDATION_ERROR", "Request validation failed", {"fields": fields})


async def _http_error(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, StarletteHTTPException)  # noqa: S101
    code = "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR"
    return envelope(error.status_code, code, "Request could not be served")


async def _unhandled(_request: Request, error: Exception) -> JSONResponse:
    logger.error("unhandled error type=%s", type(error).__name__)
    return envelope(500, "INTERNAL_ERROR", "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled)
