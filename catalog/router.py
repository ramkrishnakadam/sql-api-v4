"""HTTP routes for the catalog scanning feature.

Router only — no business logic. All logic lives in CatalogService.
All endpoints require a valid Bearer token (inherited from app auth middleware).
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from catalog.schemas import (
    CatalogHealthResponse,
    CatalogListResponse,
    SchemaListResponse,
    TableDetailResponse,
    TableListResponse,
)
from catalog.service import CatalogServiceDep

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_LIMIT = 1000


# ── health ────────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=CatalogHealthResponse,
    summary="Catalog feature health check",
    description="Verifies the app SP can reach system.information_schema.",
)
async def health(service: CatalogServiceDep) -> CatalogHealthResponse:
    """Return healthy if the Unity Catalog system schema is reachable."""
    try:
        return service.health()
    except Exception as exc:
        logger.exception("Catalog health check failed")
        raise HTTPException(status_code=503, detail=f"Catalog unavailable: {exc}")


# ── catalogs ──────────────────────────────────────────────────────────────────

@router.get(
    "/catalogs",
    response_model=CatalogListResponse,
    summary="List Unity Catalog catalogs",
    description=(
        "Returns all catalogs visible to the app SP from "
        "`system.information_schema.catalogs`."
    ),
)
async def list_catalogs(
    service: CatalogServiceDep,
    limit: int = Query(default=500, ge=1, le=_MAX_LIMIT, description="Max rows to return"),
) -> CatalogListResponse:
    """List all accessible Unity Catalog catalogs."""
    try:
        return service.list_catalogs(limit=limit)
    except Exception as exc:
        logger.exception("Failed to list catalogs")
        raise HTTPException(status_code=500, detail=str(exc))


# ── schemas ───────────────────────────────────────────────────────────────────

@router.get(
    "/catalogs/{catalog_name}/schemas",
    response_model=SchemaListResponse,
    summary="List schemas in a catalog",
    description="Returns all schemas in the specified catalog.",
    responses={404: {"description": "Catalog not found or not accessible"}},
)
async def list_schemas(
    catalog_name: str,
    service: CatalogServiceDep,
    limit: int = Query(default=500, ge=1, le=_MAX_LIMIT, description="Max rows to return"),
) -> SchemaListResponse:
    """List all schemas in a Unity Catalog catalog."""
    try:
        return service.list_schemas(catalog_name=catalog_name, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to list schemas for catalog %s", catalog_name)
        raise HTTPException(status_code=500, detail=str(exc))


# ── tables ────────────────────────────────────────────────────────────────────

@router.get(
    "/catalogs/{catalog_name}/schemas/{schema_name}/tables",
    response_model=TableListResponse,
    summary="List tables in a schema",
    description=(
        "Returns all tables in the specified catalog.schema. "
        "Optionally filter by table_type (MANAGED, EXTERNAL, VIEW)."
    ),
    responses={404: {"description": "Schema not found or not accessible"}},
)
async def list_tables(
    catalog_name: str,
    schema_name: str,
    service: CatalogServiceDep,
    table_type: Optional[str] = Query(
        default=None,
        description="Filter by table type: MANAGED, EXTERNAL, VIEW",
        pattern="^(MANAGED|EXTERNAL|VIEW|BASE TABLE|TEMPORARY)$",
    ),
    limit: int = Query(default=500, ge=1, le=_MAX_LIMIT, description="Max rows to return"),
) -> TableListResponse:
    """List all tables in a Unity Catalog schema."""
    try:
        return service.list_tables(
            catalog_name=catalog_name,
            schema_name=schema_name,
            table_type=table_type,
            limit=limit,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception(
            "Failed to list tables for %s.%s", catalog_name, schema_name
        )
        raise HTTPException(status_code=500, detail=str(exc))


# ── table detail (columns) ───────────────────────────────────────────────────

@router.get(
    "/catalogs/{catalog_name}/schemas/{schema_name}/tables/{table_name}",
    response_model=TableDetailResponse,
    summary="Get table detail with columns",
    description=(
        "Returns full table metadata and the complete column list "
        "from `system.information_schema.columns`."
    ),
    responses={404: {"description": "Table not found or not accessible"}},
)
async def get_table_detail(
    catalog_name: str,
    schema_name: str,
    table_name: str,
    service: CatalogServiceDep,
) -> TableDetailResponse:
    """Get full metadata and column list for a specific table."""
    try:
        return service.get_table_detail(
            catalog_name=catalog_name,
            schema_name=schema_name,
            table_name=table_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception(
            "Failed to get detail for %s.%s.%s", catalog_name, schema_name, table_name
        )
        raise HTTPException(status_code=500, detail=str(exc))
