"""
Request correlation ID middleware for distributed tracing.

Every inbound request gets a unique X-Request-ID.  The ID is:
  - Read from the incoming X-Request-ID header if the caller provides one,
    so upstream proxies (nginx, API gateway) can set a single trace ID.
  - Otherwise generated as a new UUID4.

The ID is:
  - Stored on request.state.request_id so route handlers can access it.
  - Echoed back in the X-Request-ID response header.
  - Added automatically to every structured log line via the ContextVar
    mechanism (see get_request_id / set_request_id).

Usage — wire into a FastAPI app:
    from shared.correlation import setup_correlation
    setup_correlation(app)

Usage — propagate to downstream services (pass existing trace ID):
    from shared.correlation import get_request_id
    headers = {"X-Request-ID": get_request_id()}
    await httpx_client.get(url, headers=headers)
"""
import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import FastAPI

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")

HEADER_NAME = "X-Request-ID"


def get_request_id() -> str:
    """Return the current request's correlation ID (empty string outside request context)."""
    return _request_id_var.get()


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Re-use the caller's ID or mint a new one
        req_id = request.headers.get(HEADER_NAME) or str(uuid.uuid4())

        # Make the ID available inside the request and to the ContextVar
        request.state.request_id = req_id
        token = _request_id_var.set(req_id)

        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)

        response.headers[HEADER_NAME] = req_id
        return response


def setup_correlation(app: FastAPI) -> None:
    """Add CorrelationMiddleware to a FastAPI app. Call once at startup."""
    app.add_middleware(CorrelationMiddleware)
