"""
Shared error handling for all FastAPI services.
Provides consistent error response format across all services.
"""
from datetime import datetime, timezone
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from pydantic import BaseModel
from typing import Optional


class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str
    message: str
    timestamp: str
    details: Optional[dict] = None


def create_error_response(
    error_type: str,
    message: str,
    details: Optional[dict] = None,
    status_code: int = 500
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        error_type: Type/category of error (e.g., "ValidationError", "NotFoundError")
        message: Human-readable error message
        details: Optional additional details about the error
        status_code: HTTP status code
        
    Returns:
        JSONResponse with standardized error format
    """
    error_data = {
        "error": error_type,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if details:
        error_data["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=error_data
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors with standardized format.
    """
    errors = exc.errors()
    error_details = {
        "validation_errors": [
            {
                "field": ".".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type": err["type"]
            }
            for err in errors
        ]
    }
    
    return create_error_response(
        error_type="ValidationError",
        message="Request validation failed",
        details=error_details,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """
    Handle all uncaught exceptions with standardized format.
    """
    # Log the full exception for debugging
    import traceback
    print(f"Unhandled exception: {exc}")
    print(traceback.format_exc())
    
    return create_error_response(
        error_type=exc.__class__.__name__,
        message=str(exc),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle FastAPI HTTPException with standardized format.
    Converts the default 'detail' field to our standard format.
    """
    # Map status codes to error types
    error_type_map = {
        400: "BadRequest",
        401: "Unauthorized",
        403: "Forbidden",
        404: "NotFound",
        409: "Conflict",
        422: "ValidationError",
        500: "InternalServerError"
    }
    
    error_type = error_type_map.get(exc.status_code, "HTTPError")
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    
    return create_error_response(
        error_type=error_type,
        message=message,
        status_code=exc.status_code
    )


def setup_error_handlers(app):
    """
    Setup standardized error handlers for a FastAPI app.
    
    Usage:
        from shared.errors import setup_error_handlers
        app = FastAPI()
        setup_error_handlers(app)
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)


# Custom exception classes for common scenarios
class AppException(Exception):
    """Base exception for application-specific errors"""
    def __init__(self, message: str, error_type: str = "ApplicationError", status_code: int = 500):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found"""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, "NotFoundError", status.HTTP_404_NOT_FOUND)


class ValidationError(AppException):
    """Validation error"""
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, "ValidationError", status.HTTP_400_BAD_REQUEST)


class ConflictError(AppException):
    """Resource conflict"""
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, "ConflictError", status.HTTP_409_CONFLICT)


class UnauthorizedError(AppException):
    """Unauthorized access"""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, "UnauthorizedError", status.HTTP_401_UNAUTHORIZED)


async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions"""
    return create_error_response(
        error_type=exc.error_type,
        message=exc.message,
        status_code=exc.status_code
    )


def setup_all_error_handlers(app):
    """
    Setup all error handlers including custom application exceptions.
    
    Usage:
        from shared.errors import setup_all_error_handlers
        app = FastAPI()
        setup_all_error_handlers(app)
    """
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
