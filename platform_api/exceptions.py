"""
API Exception Handling
======================

Custom exceptions and global error handlers for the API.
"""

from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError


class MultiCordAPIException(Exception):
    """Base exception for MultiCord API."""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(MultiCordAPIException):
    """Authentication failed."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(MultiCordAPIException):
    """Authorization failed."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class ResourceNotFoundError(MultiCordAPIException):
    """Resource not found."""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            f"{resource} not found: {identifier}",
            status.HTTP_404_NOT_FOUND,
            {"resource": resource, "identifier": identifier}
        )


class ConflictError(MultiCordAPIException):
    """Resource conflict."""
    
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_409_CONFLICT)


class RateLimitError(MultiCordAPIException):
    """Rate limit exceeded."""
    
    def __init__(self, retry_after: int):
        super().__init__(
            "Rate limit exceeded",
            status.HTTP_429_TOO_MANY_REQUESTS,
            {"retry_after": retry_after}
        )


class ValidationError(MultiCordAPIException):
    """Input validation failed."""
    
    def __init__(self, message: str, errors: Dict[str, Any]):
        super().__init__(
            message,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"validation_errors": errors}
        )


def create_error_response(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """Create standardized error response."""
    content = {
        "error": {
            "message": message,
            "status_code": status_code,
            "timestamp": datetime.utcnow().isoformat(),
        }
    }
    
    if details:
        content["error"]["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )


async def multicord_exception_handler(
    request: Request,
    exc: MultiCordAPIException
) -> JSONResponse:
    """Handle MultiCord exceptions."""
    return create_error_response(
        exc.status_code,
        exc.message,
        exc.details
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors."""
    errors = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors[field] = error["msg"]
    
    return create_error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Validation failed",
        {"validation_errors": errors}
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handle unexpected errors."""
    # Log the full error for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.exception(f"Unhandled exception: {exc}")
    
    # Return generic error to client
    return create_error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "An internal error occurred"
    )


def setup_exception_handlers(app: FastAPI):
    """Register exception handlers with the app."""
    app.add_exception_handler(MultiCordAPIException, multicord_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)