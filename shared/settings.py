"""
Centralized settings with validation for all services.

Reads from environment variables and validates at import time.
If a critical variable is missing or invalid, the service fails fast with a clear message.
"""
import os
import logging

logger = logging.getLogger(__name__)

# ─── Database ───────────────────────────────────────────────────────────────
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "aitp")

# ─── CORS ───────────────────────────────────────────────────────────────────
# Comma-separated list of allowed origins. Defaults to localhost dev origins.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000"
    ).split(",")
    if o.strip()
]

# ─── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT_JSON = os.getenv("LOG_FORMAT_JSON", "true").lower() == "true"

# ─── Request limits ─────────────────────────────────────────────────────────
MAX_REQUEST_BODY_MB = int(os.getenv("MAX_REQUEST_BODY_MB", "10"))


def validate_settings() -> None:
    """Validate critical settings at startup. Call once before serving requests."""
    errors = []

    if not MONGO_URL:
        errors.append("MONGO_URL is empty")
    if not DB_NAME:
        errors.append("DB_NAME is empty")

    if errors:
        msg = "Configuration errors:\n  - " + "\n  - ".join(errors)
        logger.critical(msg)
        raise SystemExit(msg)

    logger.info(
        "Settings loaded: MONGO_URL=%s, DB_NAME=%s, CORS_ORIGINS=%s, LOG_LEVEL=%s",
        MONGO_URL[:30] + "..." if len(MONGO_URL) > 30 else MONGO_URL,
        DB_NAME,
        CORS_ORIGINS,
        LOG_LEVEL,
    )
