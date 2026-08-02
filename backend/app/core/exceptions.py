"""
Application exception hierarchy and FastAPI exception handlers.

All API errors are returned using the consistent envelope:
    {"detail": {"code": str, "message": str, "fields": dict}}
"""
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base class for all application errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str = "Unexpected server error",
        fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.fields = fields or {}
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """Raised when a resource already exists / violates uniqueness."""
    status_code = 409
    code = "conflict"


class ValidationError(AppError):
    """Raised when business-level validation fails (400)."""
    status_code = 400
    code = "validation_error"


class UnauthorizedError(AppError):
    """Raised when authentication is missing or invalid."""
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    """Raised when a user is not allowed to perform the action."""
    status_code = 403
    code = "forbidden"


class DatabaseError(AppError):
    """Raised when an underlying database operation fails."""
    status_code = 500
    code = "database_error"


def _error_body(code: str, message: str, fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"detail": {"code": code, "message": message, "fields": fields or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.fields),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields: Dict[str, Any] = {}
        for err in exc.errors():
            loc = err.get("loc", ())
            # loc is a tuple like ("body", "email") or ("query", "page")
            field = ".".join(str(part) for part in loc if part != "body")
            fields[field or "request"] = err.get("msg", "Invalid value")
        return JSONResponse(
            status_code=400,
            content=_error_body("validation_error", "Request validation failed", fields),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            code = detail.get("code", "http_error")
            message = detail.get("message", "HTTP error")
            fields = detail.get("fields", {})
        else:
            code = "http_error"
            message = str(detail) if detail else "HTTP error"
            fields = {}
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, message, fields),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", f"Unexpected server error: {str(exc)}"),
        )

