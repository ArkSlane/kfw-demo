"""
Rate-limiting middleware for all FastAPI services.

Uses slowapi (built on top of limits).

Usage:
    from shared.rate_limit import setup_rate_limiting, limiter

    setup_rate_limiting(app)           # call once at startup

    @app.get("/heavy")
    @limiter.limit("10/minute")        # per-route override
    async def heavy(request: Request): ...

Environment variables:
    RATE_LIMIT_ENABLED  - "true" to enable (default: "false")
    RATE_LIMIT_DEFAULT  - default limit string (default: "120/minute")
    RATE_LIMIT_STORAGE  - storage backend URI (default: "memory://")
"""
import os
from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse
from datetime import datetime, timezone

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "120/minute")
RATE_LIMIT_STORAGE = os.getenv("RATE_LIMIT_STORAGE", "memory://")

# Create limiter (always instantiated so @limiter.limit() decorators don't crash,
# but not enforced unless setup_rate_limiting() is called with RATE_LIMIT_ENABLED=true).
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[RATE_LIMIT_DEFAULT] if RATE_LIMIT_ENABLED else [],
    storage_uri=RATE_LIMIT_STORAGE,
    enabled=RATE_LIMIT_ENABLED,
)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Return a JSON 429 response when rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "RateLimitExceeded",
            "message": f"Rate limit exceeded: {exc.detail}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def setup_rate_limiting(app: FastAPI) -> None:
    """Wire rate-limiting into a FastAPI app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
