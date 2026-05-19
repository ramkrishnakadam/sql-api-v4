"""Pydantic request/response schemas for the SqlApiV4 feature."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SqlApiV4HealthResponse(BaseModel):
    """Health payload for the SqlApiV4 feature."""

    status: str
    feature: str


class SqlApiV4Item(BaseModel):
    """A single SqlApiV4 item."""

    id: str = Field(..., description="Stable item identifier", max_length=64)
    name: str = Field(..., description="Human-readable name", max_length=256)
    status: Optional[str] = Field(default=None, description="Lifecycle status", max_length=32)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"id": "i-123", "name": "Example item", "status": "active"},
        },
    )
