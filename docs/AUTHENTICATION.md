# Authentication — Sql Api V4

## Overview

This app runs on **Databricks Apps**, which places an OAuth proxy in front of
every deployed application. The proxy validates incoming tokens before the
request reaches FastAPI, meaning the app itself does not need to verify
cryptographic signatures.

## How it works

```
Caller (user / SP)
  │
  ▼  Bearer token in Authorization header
┌─────────────────────────────┐
│  Databricks OAuth Proxy     │  ← validates token, sets identity headers
└─────────────────────────────┘
  │
  ▼  X-Forwarded-Email, X-Forwarded-User, X-Forwarded-Access-Token
┌─────────────────────────────┐
│  FastAPI (core/auth.py)     │  ← reads identity from headers
└─────────────────────────────┘
```

## Auth modes

Set via the `APP_AUTH_MODE` environment variable (default: `proxy`).

### `proxy` (recommended for Databricks Apps)

Trusts headers set by the OAuth proxy after token validation:

| Header | Description |
|--------|-------------|
| `X-Forwarded-Email` | User email (interactive users only) |
| `X-Forwarded-User` | Username or SP application ID |
| `X-Forwarded-Access-Token` | Original access token (for passthrough to SQL) |

For **service principals**, `X-Forwarded-Email` is absent; the app detects
this and marks the caller as `is_service_principal=True`.

### `token`

Validates the Bearer token directly against the workspace OIDC userinfo
endpoint (`https://<workspace>/oidc/v1/userinfo`). Useful for deployments
outside the Databricks proxy or as an extra validation layer.

### `none`

Skips all authentication. **Local development only** — never use in production.

## Service Principal (M2M) access

### Prerequisites

1. **Register the SP** in the Databricks workspace (or at account level)
2. **Create an OAuth secret** (requires Account Admin):
   ```bash
   databricks account service-principal-secrets create <sp_databricks_id>
   ```
3. **Grant app permissions** — the SP needs `CAN_MANAGE` or `CAN_USE` on the app:
   ```bash
   databricks apps set-permission \
     --app-name sql-api-v4 \
     --principal <sp_databricks_id> \
     --level CAN_MANAGE
   ```

### Token acquisition

```bash
curl -X POST "https://<workspace>.azuredatabricks.net/oidc/v1/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=<sp_client_id>&client_secret=<oauth_secret>&scope=all-apis"
```

Response:
```json
{
  "access_token": "<oidc_token>",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Calling the app

```bash
curl -H "Authorization: Bearer <oidc_token>" \
  "https://sql-api-v4-<workspace_id>.<region>.azure.databricksapps.com/api/v1/sql_api_v4/health"
```

## CallerIdentity

The `validate_bearer_token` dependency returns a `CallerIdentity` dataclass:

```python
@dataclass
class CallerIdentity:
    user_id: Optional[str]       # X-Forwarded-User or OIDC sub
    email: Optional[str]         # X-Forwarded-Email (None for SPs)
    username: Optional[str]      # Best available name
    is_service_principal: bool   # True when email is absent
```

To use in a route handler:

```python
from core.auth import CallerIdentity, validate_bearer_token

@router.get("/whoami")
async def whoami(caller: CallerIdentity = Depends(validate_bearer_token)):
    return {"identity": caller.display_name, "is_sp": caller.is_service_principal}
```

## SQL connection identity

The database layer (`core/database.py`) determines SQL authentication
separately from the caller identity. Auth priority:

1. **PAT token** (`DATABRICKS_TOKEN`) — dev/admin override
2. **BYOSP M2M** (`DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET`) — team SP
3. **User passthrough** (`IDENTITY_MODE=user`) — caller's token for per-user UC grants
4. **Runtime SP** — Databricks-managed app identity (fallback)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 {}` (empty body) | OAuth proxy rejected token | Ensure token is from workspace OIDC, not AAD directly |
| `403` on app URL | SP lacks app permission | Grant `CAN_MANAGE` / `CAN_USE` on the app |
| `CallerIdentity.is_service_principal` always True | Proxy not forwarding email | Expected for SPs; check `X-Forwarded-User` is populated |
| Token expires quickly | Default 1h TTL | Re-acquire token before expiry; implement token caching |
