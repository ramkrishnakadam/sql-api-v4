"""HTTP routes for the SqlApiV4 feature.

Router only — no business logic. Delegates to SqlApiV4Service via DI.
"""

import logging

from fastapi import APIRouter, HTTPException

from sql_api_v4.schemas import (
    SqlApiV4Item,
    SqlApiV4HealthResponse,
)
from sql_api_v4.service import SqlApiV4ServiceDep

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=SqlApiV4HealthResponse,
    summary="SqlApiV4 health check",
    description="Verifies the SqlApiV4 feature can reach its data source.",
)
async def health(service: SqlApiV4ServiceDep) -> SqlApiV4HealthResponse:
    try:
        return service.health()
    except Exception as e:
        logger.exception("SqlApiV4 health check failed")
        raise HTTPException(status_code=503, detail=f"SqlApiV4 unavailable: {e}")


@router.get(
    "/items/{item_id}",
    response_model=SqlApiV4Item,
    summary="Get a SqlApiV4 item by ID",
    description="Example endpoint — replace with your real resources.",
    responses={
        200: {"description": "Item found"},
        404: {"description": "Item not found"},
    },
)
async def get_item(item_id: str, service: SqlApiV4ServiceDep) -> SqlApiV4Item:
    item = service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    return item
