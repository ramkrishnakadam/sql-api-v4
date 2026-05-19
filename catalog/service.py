"""Business logic for the catalog scanning feature.

No HTTP concerns here — raises plain Python exceptions that the router
translates into appropriate HTTP responses.
"""

import logging
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Depends

from catalog.repository import CatalogRepository
from catalog.schemas import (
    CatalogHealthResponse,
    CatalogItem,
    CatalogListResponse,
    ColumnItem,
    SchemaItem,
    SchemaListResponse,
    TableDetailResponse,
    TableItem,
    TableListResponse,
)

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 500


@dataclass
class CatalogService:
    """Service layer for Unity Catalog scanning."""

    repo: Annotated[CatalogRepository, Depends(CatalogRepository)]

    # ── health ────────────────────────────────────────────────────────────────

    def health(self) -> CatalogHealthResponse:
        """Verify the system.information_schema is reachable."""
        self.repo.ping()
        return CatalogHealthResponse(status="healthy", feature="catalog")

    # ── catalogs ──────────────────────────────────────────────────────────────

    def list_catalogs(self, limit: int = _DEFAULT_LIMIT) -> CatalogListResponse:
        """List all Unity Catalog catalogs the app SP can access.

        Args:
            limit: Maximum number of catalogs to return (1–1000).

        Returns:
            CatalogListResponse with the catalog list and total count.
        """
        rows = self.repo.list_catalogs(limit=limit)
        items = [CatalogItem.model_validate(r) for r in rows]
        return CatalogListResponse(catalogs=items, total=len(items))

    # ── schemas ───────────────────────────────────────────────────────────────

    def list_schemas(
        self, catalog_name: str, limit: int = _DEFAULT_LIMIT
    ) -> SchemaListResponse:
        """List schemas in a catalog.

        Args:
            catalog_name: Target catalog name.
            limit: Maximum number of schemas to return (1–1000).

        Returns:
            SchemaListResponse with the schema list and total count.

        Raises:
            LookupError: If the catalog does not exist or is not accessible.
        """
        rows = self.repo.list_schemas(catalog_name=catalog_name, limit=limit)
        if not rows:
            # Distinguish "catalog exists but empty" from "catalog not found"
            catalogs = self.repo.list_catalogs(limit=1000)
            names = {r["catalog_name"] for r in catalogs}
            if catalog_name not in names:
                raise LookupError(f"Catalog '{catalog_name}' not found or not accessible")
        items = [SchemaItem.model_validate(r) for r in rows]
        return SchemaListResponse(schemas=items, total=len(items))

    # ── tables ────────────────────────────────────────────────────────────────

    def list_tables(
        self,
        catalog_name: str,
        schema_name: str,
        table_type: Optional[str] = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> TableListResponse:
        """List tables in a catalog.schema, optionally filtered by type.

        Args:
            catalog_name: Target catalog name.
            schema_name: Target schema name.
            table_type: Optional table type filter (MANAGED, EXTERNAL, VIEW, etc.).
            limit: Maximum number of tables to return (1–1000).

        Returns:
            TableListResponse with the table list and total count.

        Raises:
            LookupError: If the schema does not exist or is not accessible.
        """
        rows = self.repo.list_tables(
            catalog_name=catalog_name,
            schema_name=schema_name,
            table_type=table_type,
            limit=limit,
        )
        if not rows and table_type is None:
            schemas = self.repo.list_schemas(catalog_name=catalog_name, limit=1000)
            names = {r["schema_name"] for r in schemas}
            if schema_name not in names:
                raise LookupError(
                    f"Schema '{catalog_name}.{schema_name}' not found or not accessible"
                )
        items = [TableItem.model_validate(r) for r in rows]
        return TableListResponse(tables=items, total=len(items))

    # ── table detail ──────────────────────────────────────────────────────────

    def get_table_detail(
        self, catalog_name: str, schema_name: str, table_name: str
    ) -> TableDetailResponse:
        """Return full table metadata plus all columns.

        Args:
            catalog_name: Target catalog name.
            schema_name: Target schema name.
            table_name: Target table name.

        Returns:
            TableDetailResponse with table metadata and column list.

        Raises:
            LookupError: If the table does not exist or is not accessible.
        """
        meta = self.repo.get_table_meta(
            catalog_name=catalog_name,
            schema_name=schema_name,
            table_name=table_name,
        )
        if meta is None:
            raise LookupError(
                f"Table '{catalog_name}.{schema_name}.{table_name}' not found or not accessible"
            )
        col_rows = self.repo.get_table_columns(
            catalog_name=catalog_name,
            schema_name=schema_name,
            table_name=table_name,
        )
        columns = [ColumnItem.model_validate(r) for r in col_rows]
        return TableDetailResponse(
            **meta,
            columns=columns,
            column_count=len(columns),
        )


CatalogServiceDep = Annotated[CatalogService, Depends(CatalogService)]
