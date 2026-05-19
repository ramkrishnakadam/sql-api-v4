"""Authentication for Databricks Apps.

Databricks Apps run behind a built-in OAuth proxy that validates tokens
before requests reach this FastAPI application. Supported callers:

- **Interactive users**: browser-based Databricks SSO login
- **Service Principals**: Databricks OIDC token via client_credentials grant

To obtain a token programmatically (SP M2M):
    POST {workspace}/oidc/v1/token
    grant_type=client_credentials&client_id=<sp_client_id>&client_secret=<oauth_secret>&scope=all-apis

The OAuth secret must be created by a Databricks Account Admin via:
    databricks account service-principal-secrets create <sp_databricks_id>

Auth modes via APP_AUTH_MODE env var:
- proxy (default): Trust Databricks proxy headers. The proxy already validated
  the token; the app reads the caller identity from forwarded headers.
- token: Validate the Bearer token against the workspace /oidc/v1/userinfo
  endpoint (double-validation, useful for extra security or non-proxy deploys).
- none: Skip all validation (local development only).
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import HTTPException, Request

from core.database import _DB_HOST

logger = logging.getLogger(__name__)

APP_AUTH_MODE = os.getenv("APP_AUTH_MODE", "proxy")


@dataclass
class CallerIdentity:
    """Resolved caller identity from the Databricks proxy."""

    user_id: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    is_service_principal: bool = False

    @property
    def display_name(self) -> str:
        """Return the best available display name."""
        return self.email or self.username or self.user_id or "unknown"


def _extract_identity_from_proxy(request: Request) -> CallerIdentity:
    """Extract caller identity from Databricks proxy-forwarded headers.

    The Databricks Apps proxy sets these headers after validating the token:
    - X-Forwarded-Email: user email (for interactive users)
    - X-Forwarded-User: username or SP application ID
    - X-Forwarded-Access-Token: the original access token (for passthrough)
    - X-Real-Ip: client IP address

    For service principals, X-Forwarded-Email may be absent; the sub claim
    from the token is the SP's application ID.
    """
    email = request.headers.get("X-Forwarded-Email")
    user = request.headers.get("X-Forwarded-User")

    # Service principals typically lack an email header
    is_sp = not email and user is not None

    return CallerIdentity(
        user_id=user,
        email=email,
        username=user,
        is_service_principal=is_sp,
    )


async def _validate_token_against_oidc(request: Request) -> CallerIdentity:
    """Validate Bearer token against Databricks OIDC userinfo endpoint."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.removeprefix("Bearer ")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"https://{_DB_HOST}/oidc/v1/userinfo",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    info = resp.json()
    email = info.get("email")
    sub = info.get("sub", "unknown")

    return CallerIdentity(
        user_id=sub,
        email=email,
        username=email or sub,
        is_service_principal=email is None,
    )


async def validate_bearer_token(request: Request) -> Optional[CallerIdentity]:
    """Validate the caller's identity according to APP_AUTH_MODE.

    Returns a CallerIdentity with user/SP information, ``None`` for
    unauthenticated dev mode, or raises ``HTTPException(401)`` on failure.
    """
    if APP_AUTH_MODE == "none":
        return None

    if APP_AUTH_MODE == "proxy":
        return _extract_identity_from_proxy(request)

    # token mode — validate against OIDC
    return await _validate_token_against_oidc(request)
