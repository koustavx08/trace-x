from typing import Any

import structlog
from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class APIErrorCode:
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"


class TraceXException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(TraceXException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            code=APIErrorCode.NOT_FOUND,
            message=f"{resource} not found: {identifier}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": identifier},
        )


class ConflictError(TraceXException):
    def __init__(self, resource: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code=APIErrorCode.CONFLICT,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details or {"resource": resource},
        )


class ValidationError(TraceXException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code=APIErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class DatabaseError(TraceXException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code=APIErrorCode.DATABASE_ERROR,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ExternalServiceError(TraceXException):
    def __init__(self, service: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code=APIErrorCode.EXTERNAL_SERVICE_ERROR,
            message=f"{service}: {message}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details or {"service": service},
        )


# --- WS3: provider-availability exception (appended, do not merge into unrelated blocks) ---
class ProviderNotConfiguredError(TraceXException):
    """Raised when a third-party blockchain/intelligence provider (e.g. Chainalysis,
    CipherTrace, Alchemy, Infura) is invoked without its required API key configured.

    Providers must raise this at construction/use time instead of failing silently
    (returning empty data) or crashing app startup.
    """

    def __init__(
        self, provider: str, message: str | None = None, details: dict[str, Any] | None = None
    ):
        super().__init__(
            code=APIErrorCode.PROVIDER_NOT_CONFIGURED,
            message=message or f"{provider} is not configured: missing API key",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details or {"provider": provider},
        )


# --- end WS3 block ---


async def tracex_exception_handler(request: Request, exc: TraceXException) -> JSONResponse:
    logger.error(
        "api_error",
        code=exc.code,
        message=exc.message,
        details=exc.details,
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(
        "http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": APIErrorCode.INTERNAL_ERROR,
                "message": str(exc.detail),
                "details": {},
            }
        },
    )


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        "request_validation_error",
        errors=exc.errors(),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": APIErrorCode.VALIDATION_ERROR,
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": APIErrorCode.INTERNAL_ERROR,
                "message": "An unexpected error occurred",
                "details": {},
            }
        },
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(TraceXException, tracex_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
