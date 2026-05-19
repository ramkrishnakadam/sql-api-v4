"""Public status endpoints — no authentication required."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/status", tags=["status"])


class StatusResponse(BaseModel):
    """Lightweight status payload."""

    status: str
    service: str = "sql-api-v4"


@router.get("/health", response_model=StatusResponse, summary="Liveness check")
async def health() -> StatusResponse:
    """Return ``ok`` if the app process is up."""
    return StatusResponse(status="ok")


@router.get("/ready", response_model=StatusResponse, summary="Readiness check")
async def ready() -> StatusResponse:
    """Return ``ready`` if the app is ready to accept traffic."""
    return StatusResponse(status="ready")
