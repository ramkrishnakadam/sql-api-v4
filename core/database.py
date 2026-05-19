"""Databricks SQL connection factory + FastAPI dependency.

Authentication priority (in order):
1. DATABRICKS_TOKEN env var — PAT or manually provided token (dev/testing)
2. BYOSP M2M — DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET in secret scope.
   Uses client_credentials OAuth grant. The SP is registered in Azure AD/Entra ID
   by the team, added to Azure AD groups, and those groups are granted in Unity Catalog.
3. Databricks runtime identity — WorkspaceClient() with no explicit credentials.
   Uses the Databricks-managed app SP (injected by the Apps runtime). This SP is NOT
   an Azure AD registration you control — you cannot add it to Azure AD groups.
   Use only for development or when BYOSP is not yet configured.

Identity passthrough (IDENTITY_MODE=user):
   When enabled, the caller's forwarded OAuth token is used for the SQL connection
   so Unity Catalog enforces grants against the individual caller's identity.
"""

import logging
import os
from typing import Annotated, Any, Optional

from databricks import sql as databricks_sql
from fastapi import Depends, Request

logger = logging.getLogger(__name__)

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH", "")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
DATABRICKS_CLIENT_ID = os.getenv("DATABRICKS_CLIENT_ID", "")
DATABRICKS_CLIENT_SECRET = os.getenv("DATABRICKS_CLIENT_SECRET", "")
DATABRICKS_TENANT_ID = os.getenv("DATABRICKS_TENANT_ID", "")
IDENTITY_MODE = os.getenv("IDENTITY_MODE", "app")

# Normalised hostname — strips scheme and trailing slash so it is safe to
# embed in URL templates (e.g. f"https://{_DB_HOST}/oidc/v1/token").
_DB_HOST = DATABRICKS_HOST.replace("https://", "").replace("http://", "").rstrip("/")


def _get_m2m_token(host: str, client_id: str, client_secret: str, tenant_id: str = "") -> str:
    """Exchange SP credentials for a short-lived Databricks access token.

    Supports two grant flows depending on whether an Azure tenant ID is supplied:

    - **Azure AD / Entra ID SP** (``tenant_id`` provided): posts
      ``client_credentials`` to the Azure AD token endpoint and requests the
      Databricks resource scope.  Use this when ``DATABRICKS_CLIENT_ID`` and
      ``DATABRICKS_CLIENT_SECRET`` are Azure AD application credentials.
    - **Databricks-native OAuth M2M** (no ``tenant_id``): posts to the
      workspace OIDC endpoint.  Requires a Databricks OAuth secret (created by
      an Account Admin), *not* an Azure AD client secret.

    Args:
        host: Databricks workspace hostname, **without** scheme or trailing slash.
        client_id: Azure AD application (client) ID of the SP.
        client_secret: Azure AD client secret (AAD route) or Databricks OAuth
            secret (Databricks-native route).
        tenant_id: Azure AD tenant ID.  When non-empty the Azure AD token
            endpoint is used; otherwise the Databricks OIDC endpoint is used.

    Returns:
        Short-lived access token string.

    Raises:
        RuntimeError: If the token exchange fails or the response lacks
            ``access_token``.
    """
    import urllib.request
    import urllib.parse
    import json

    if tenant_id:
        # Azure AD / Entra ID route — correct endpoint for Azure AD service principals
        url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            # Databricks resource ID — grants access to all Databricks REST APIs
            "scope": "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default",
        }).encode()
    else:
        # Databricks-native OAuth M2M — requires a Databricks OAuth secret
        url = f"https://{host}/oidc/v1/token"
        payload = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "all-apis",
        }).encode()

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            body = json.loads(resp.read())
    except Exception as exc:
        raise RuntimeError(
            f"M2M token exchange failed for client_id={client_id!r}: {exc}. "
            "Ensure the SP is registered in Databricks and has CAN_USE on the SQL warehouse."
        ) from exc

    token = body.get("access_token")
    if not token:
        raise RuntimeError(
            f"M2M token response missing 'access_token' for client_id={client_id!r}. "
            f"Response keys: {list(body.keys())}"
        )
    return token


def _get_app_runtime_token() -> tuple[str, str]:
    """Return (host, token) using the Databricks-managed runtime SP.

    This uses whichever credentials the Databricks Apps runtime injected.
    The resulting SP is NOT an Azure AD registration you own — you cannot
    add it to Azure AD groups for Unity Catalog group-based grants.
    Use BYOSP (DATABRICKS_CLIENT_ID + SECRET) for group-based access control.
    """
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    host = (w.config.host or "").rstrip("/").replace("https://", "").replace("http://", "")
    auth = w.config.authenticate
    headers = auth() if callable(auth) else auth
    if callable(headers):
        headers = headers("GET", f"https://{host or DATABRICKS_HOST}")
    token = headers.get("Authorization", "").removeprefix("Bearer ")
    return host, token


def _extract_user_token(request: Optional[Request]) -> Optional[str]:
    """Extract user OAuth token from proxy headers, in priority order."""
    if not request:
        return None
    for header in ("X-Forwarded-Access-Token", "X-Auth-Request-Access-Token"):
        token = request.headers.get(header)
        if token:
            return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ")
    return None


def get_connection(request: Request):
    """FastAPI dependency yielding a Databricks SQL connection.

    Auth priority: PAT token → BYOSP M2M → user passthrough → runtime SP.
    """
    # Priority 1: explicit PAT / dev token
    if DATABRICKS_TOKEN:
        conn = databricks_sql.connect(
            server_hostname=_DB_HOST,
            http_path=DATABRICKS_HTTP_PATH,
            access_token=DATABRICKS_TOKEN,
        )
        try:
            yield conn
        finally:
            conn.close()
        return

    # Priority 2: BYOSP M2M — team-registered Azure AD SP, group-managed UC access
    if DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET:
        try:
            token = _get_m2m_token(
                _DB_HOST,
                DATABRICKS_CLIENT_ID,
                DATABRICKS_CLIENT_SECRET,
                tenant_id=DATABRICKS_TENANT_ID,
            )
            conn = databricks_sql.connect(
                server_hostname=_DB_HOST,
                http_path=DATABRICKS_HTTP_PATH,
                access_token=token,
            )
            try:
                yield conn
            finally:
                conn.close()
            return
        except Exception as exc:
            logger.error("BYOSP M2M auth failed: %s", exc)
            raise

    # Priority 3: caller identity passthrough (Unity Catalog enforces per-user grants)
    if IDENTITY_MODE == "user":
        user_token = _extract_user_token(request)
        if user_token:
            try:
                conn = databricks_sql.connect(
                    server_hostname=_DB_HOST,
                    http_path=DATABRICKS_HTTP_PATH,
                    access_token=user_token,
                )
                try:
                    yield conn
                finally:
                    conn.close()
                return
            except Exception as exc:
                logger.warning("User passthrough failed (%s); falling back to runtime SP", exc)

    # Priority 4: Databricks-managed runtime SP (cannot be added to Azure AD groups)
    logger.warning(
        "Falling back to Databricks runtime SP for SQL connection. "
        "Set DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET for BYOSP M2M auth."
    )
    host, token = _get_app_runtime_token()
    conn = databricks_sql.connect(
        server_hostname=host or _DB_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=token,
    )
    try:
        yield conn
    finally:
        conn.close()


ConnectionDep = Annotated[Any, Depends(get_connection)]
