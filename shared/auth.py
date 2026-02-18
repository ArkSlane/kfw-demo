"""
JWT-based authentication and authorization for all services.
Supports two modes controlled by AUTH_MODE:
  - "local"    : self-issued HS256 tokens with a local user store
  - "keycloak" : validates RS256 tokens issued by Keycloak (OIDC / OAuth 2.0)

Usage:
    from shared.auth import setup_auth, require_auth

    setup_auth(app)              # call once at startup
    @app.get("/protected", dependencies=[Depends(require_auth)])
    async def protected_route(): ...

Environment variables (common):
    AUTH_ENABLED       - "true" to enforce auth (default: "false" for dev)
    AUTH_MODE          - "local" | "keycloak" (default: "keycloak")
    AUTH_PUBLIC_PATHS  - Comma-separated paths that skip auth

Local-mode variables:
    AUTH_SECRET_KEY    - HMAC secret for JWT signing (REQUIRED)
    AUTH_ALGORITHM     - JWT algorithm (default: HS256)
    AUTH_TOKEN_EXPIRE  - Token lifetime in minutes (default: 60)

Keycloak-mode variables:
    AUTH_KEYCLOAK_URL       - Base URL of Keycloak (e.g. http://keycloak:8080)
    AUTH_KEYCLOAK_REALM     - Realm name (default: testmaster)
    AUTH_KEYCLOAK_CLIENT_ID - Client ID for audience check (default: testmaster-app)
"""
import os
import json
import hashlib
import logging
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ─── Lazy import jwt (python-jose) ─────────────────────────────────────────
_jwt = None


def _get_jwt():
    global _jwt
    if _jwt is None:
        try:
            from jose import jwt as _jose_jwt
            _jwt = _jose_jwt
        except ImportError:
            raise RuntimeError(
                "python-jose[cryptography] is required when AUTH_ENABLED=true. "
                "Add it to requirements.txt: python-jose[cryptography]"
            )
    return _jwt


# ─── Configuration ──────────────────────────────────────────────────────────
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
AUTH_MODE = os.getenv("AUTH_MODE", "keycloak").lower()  # "local" | "keycloak"

# Local-mode config
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "")
AUTH_ALGORITHM = os.getenv("AUTH_ALGORITHM", "HS256")
AUTH_TOKEN_EXPIRE_MINUTES = int(os.getenv("AUTH_TOKEN_EXPIRE", "60"))

# Keycloak-mode config
AUTH_KEYCLOAK_URL = os.getenv("AUTH_KEYCLOAK_URL", "http://keycloak:8080")
AUTH_KEYCLOAK_REALM = os.getenv("AUTH_KEYCLOAK_REALM", "testmaster")
AUTH_KEYCLOAK_CLIENT_ID = os.getenv("AUTH_KEYCLOAK_CLIENT_ID", "testmaster-app")

AUTH_PUBLIC_PATHS = [
    p.strip()
    for p in os.getenv(
        "AUTH_PUBLIC_PATHS",
        "/health,/docs,/redoc,/openapi.json,/auth/login,/auth/register,/auth/settings"
    ).split(",")
    if p.strip()
]

# User store collection (local mode)
_users_collection = "auth_users"

# Bearer scheme (for OpenAPI docs)
_bearer_scheme = HTTPBearer(auto_error=False)


# ─── JWKS cache for Keycloak mode ──────────────────────────────────────────
_jwks_cache = {"keys": None, "fetched_at": 0}
_JWKS_CACHE_TTL = 300  # seconds


def _get_keycloak_jwks():
    """Fetch and cache JWKS from Keycloak."""
    import time
    now = time.time()
    if _jwks_cache["keys"] and (now - _jwks_cache["fetched_at"]) < _JWKS_CACHE_TTL:
        return _jwks_cache["keys"]

    jwks_url = f"{AUTH_KEYCLOAK_URL}/realms/{AUTH_KEYCLOAK_REALM}/protocol/openid-connect/certs"
    try:
        req = urllib.request.Request(jwks_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            jwks = json.loads(resp.read().decode())
        _jwks_cache["keys"] = {k["kid"]: k for k in jwks.get("keys", [])}
        _jwks_cache["fetched_at"] = now
        logger.info("Fetched JWKS from Keycloak (%d keys)", len(_jwks_cache["keys"]))
        return _jwks_cache["keys"]
    except Exception as e:
        logger.error("Failed to fetch JWKS from %s: %s", jwks_url, e)
        if _jwks_cache["keys"]:
            return _jwks_cache["keys"]
        raise HTTPException(status_code=503, detail="Cannot reach identity provider")


def _decode_keycloak_token(token: str) -> dict:
    """Decode and verify a Keycloak-issued RS256 JWT."""
    jwt = _get_jwt()
    try:
        headers = jwt.get_unverified_headers(token)
        kid = headers.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="Token missing kid header")

        jwks = _get_keycloak_jwks()
        key = jwks.get(kid)
        if not key:
            _jwks_cache["fetched_at"] = 0
            jwks = _get_keycloak_jwks()
            key = jwks.get(kid)
            if not key:
                raise HTTPException(status_code=401, detail="Unknown signing key")

        from jose import jwk as jose_jwk
        rsa_key = jose_jwk.construct(key)

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=AUTH_KEYCLOAK_CLIENT_ID,
            options={"verify_at_hash": False},
        )

        # Normalize: extract roles from realm_access.roles
        roles = []
        realm_access = payload.get("realm_access", {})
        if isinstance(realm_access, dict):
            roles = realm_access.get("roles", [])

        role = "viewer"
        if "admin" in roles:
            role = "admin"
        elif "editor" in roles:
            role = "editor"

        return {
            "sub": payload.get("preferred_username", payload.get("sub", "unknown")),
            "email": payload.get("email", ""),
            "name": payload.get("name", ""),
            "role": role,
            "roles": roles,
            "raw": payload,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Keycloak token validation failed: %s", e)
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ─── Password hashing (simple SHA-256 + salt — local mode) ─────────────────
def _hash_password(password: str) -> str:
    salt = (AUTH_SECRET_KEY or "default-salt")[:16]
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def _verify_password(plain: str, hashed: str) -> bool:
    return _hash_password(plain) == hashed


# ─── Token helpers ──────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    jwt = _get_jwt()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=AUTH_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, AUTH_SECRET_KEY, algorithm=AUTH_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode a token using the configured mode."""
    if AUTH_MODE == "keycloak":
        return _decode_keycloak_token(token)

    # Local mode — HS256
    jwt = _get_jwt()
    try:
        payload = jwt.decode(token, AUTH_SECRET_KEY, algorithms=[AUTH_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ─── FastAPI dependency ─────────────────────────────────────────────────────
async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI dependency that validates the Bearer token.
    Returns the decoded token payload (contains 'sub', 'role', etc.).
    """
    if not AUTH_ENABLED:
        return {"sub": "anonymous", "role": "admin"}

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    return decode_token(credentials.credentials)


# ─── Auth middleware (blanket protection) ───────────────────────────────────
class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that protects all routes except public paths."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")
        if any(path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/") for p in AUTH_PUBLIC_PATHS):
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "message": "Missing or invalid authorization header"},
            )

        token = auth_header[7:]
        try:
            payload = decode_token(token)
            request.state.user = payload
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"error": "Unauthorized", "message": e.detail},
            )

        return await call_next(request)


# ─── Auth routes ────────────────────────────────────────────────────────────
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field("viewer", pattern="^(admin|editor|viewer)$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


def _add_auth_routes(app: FastAPI):
    """Register /auth/* endpoints."""

    from shared.db import get_db

    @app.get("/auth/settings", tags=["auth"])
    async def auth_settings():
        """Public endpoint — tells the frontend which auth mode is active."""
        return {
            "auth_enabled": AUTH_ENABLED,
            "auth_mode": AUTH_MODE,
            "keycloak_url": AUTH_KEYCLOAK_URL if AUTH_MODE == "keycloak" else None,
            "keycloak_realm": AUTH_KEYCLOAK_REALM if AUTH_MODE == "keycloak" else None,
            "keycloak_client_id": AUTH_KEYCLOAK_CLIENT_ID if AUTH_MODE == "keycloak" else None,
        }

    if AUTH_MODE == "local":
        @app.post("/auth/register", tags=["auth"], response_model=TokenResponse)
        async def register(body: RegisterRequest):
            db = get_db()
            existing = await db[_users_collection].find_one({"username": body.username})
            if existing:
                raise HTTPException(status_code=409, detail="Username already exists")

            user_doc = {
                "username": body.username,
                "password_hash": _hash_password(body.password),
                "role": body.role,
                "created_at": datetime.now(timezone.utc),
            }
            result = await db[_users_collection].insert_one(user_doc)

            token = create_access_token({"sub": body.username, "role": body.role})
            return TokenResponse(
                access_token=token,
                expires_in=AUTH_TOKEN_EXPIRE_MINUTES * 60,
                user={"username": body.username, "role": body.role, "id": str(result.inserted_id)},
            )

        @app.post("/auth/login", tags=["auth"], response_model=TokenResponse)
        async def login(body: LoginRequest):
            db = get_db()
            user = await db[_users_collection].find_one({"username": body.username})
            if not user or not _verify_password(body.password, user["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid username or password")

            token = create_access_token({"sub": user["username"], "role": user["role"]})
            return TokenResponse(
                access_token=token,
                expires_in=AUTH_TOKEN_EXPIRE_MINUTES * 60,
                user={"username": user["username"], "role": user["role"], "id": str(user["_id"])},
            )

    @app.get("/auth/me", tags=["auth"])
    async def me(user: dict = Depends(require_auth)):
        return {
            "username": user.get("sub"),
            "role": user.get("role"),
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "roles": user.get("roles", [user.get("role")]),
        }


# ─── Setup function ────────────────────────────────────────────────────────
def setup_auth(app: FastAPI) -> None:
    """
    Wire authentication into a FastAPI app.
    Call this once during app initialization, BEFORE adding routes.
    """
    if AUTH_ENABLED:
        if AUTH_MODE == "local" and not AUTH_SECRET_KEY:
            raise RuntimeError(
                "AUTH_SECRET_KEY environment variable is required when AUTH_ENABLED=true and AUTH_MODE=local"
            )
        app.add_middleware(AuthMiddleware)
        logger.info("Auth enabled — mode=%s", AUTH_MODE)
    else:
        logger.info("Auth disabled — all requests treated as admin")

    # Always add auth routes so /auth/settings is available
    _add_auth_routes(app)
