"""Data access for the catalog scanning feature.

All queries target Unity Catalog system tables in
``system.information_schema``. The BYOSP identity used by the SQL
connection must have at minimum:

    GRANT USE CATALOG ON CATALOG system TO `<byosp-client-id>`;
    GRANT SELECT ON ALL TABLES IN SCHEMA system.information_schema TO `<byosp-client-id>`;

or add the BYOSP to an Azure AD group that already holds those grants.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from core.database import ConnectionDep

logger = logging.getLogger(__name__)

# Maximum rows returned per scan to protect warehouse from runaway queries.
_DEFAULT_LIMIT = 1000


@dataclass
class CatalogRepository:
    """Repository for Unity Catalog system.information_schema queries."""

    db: ConnectionDep

    # ── connectivity ──────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Lightweight connectivity check against system schema."""
        cursor = self.db.cursor()
        try:
            cursor.execute("SELECT 1 FROM system.information_schema.catalogs LIMIT 1")
            return True
        finally:
            cursor.close()

    # ── catalogs ──────────────────────────────────────────────────────────────

    def list_catalogs(self, limit: int = _DEFAULT_LIMIT) -> list[dict]:
        """Return all accessible catalogs from system.information_schema.

        Args:
            limit: Maximum number of rows to return.

        Returns:
            List of dicts with keys: catalog_name, catalog_owner, comment.
        """
        cursor = self.db.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    catalog_name,
                    catalog_owner,
                    comment
                FROM system.information_schema.catalogs
                ORDER BY catalog_name
                LIMIT ?
                """,
                (limit,),
            )
            return self._rows_to_dicts(cursor)
        finally:
            cursor.close()

    # ── schemas ───────────────────────────────────────────────────────────────

    def list_schemas(
        self, catalog_name: str, limit: int = _DEFAULT_LIMIT
    ) -> list[dict]:
        """Return all schemas in a given catalog.

        Args:
            catalog_name: Target catalog.
            limit: Maximum number of rows to return.

        Returns:
            List of dicts with keys: catalog_name, schema_name, schema_owner, comment.
        """
        cursor = self.db.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    catalog_name,
                    schema_name,
                    schema_owner,
                    comment
                FROM system.information_schema.schemata
                WHERE catalog_name = ?
                ORDER BY schema_name
                LIMIT ?
                """,
                (catalog_name, limit),
            )
            return self._rows_to_dicts(cursor)
        finally:
            cursor.close()

    # ── tables ────────────────────────────────────────────────────────────────

    def list_tables(
        self,
        catalog_name: str,
        schema_name: str,
        table_type: Optional[str] = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> list[dict]:
        """Return all tables in a catalog.schema, optionally filtered by type.

        Args:
            catalog_name: Target catalog.
            schema_name: Target schema.
            table_type: Optional filter — e.g. ``"MANAGED"``, ``"EXTERNAL"``, ``"VIEW"``.
            limit: Maximum number of rows to return.

        Returns:
            List of dicts describing each table.
        """
        cursor = self.db.cursor()
        try:
            if table_type:
                cursor.execute(
                    """
                    SELECT
                        table_catalog  AS catalog_name,
                        table_schema   AS schema_name,
                        table_name,
                        table_type,
                        data_source_format,
                        table_owner,
                        comment,
                        CAST(created   AS STRING) AS created,
                        CAST(last_altered AS STRING) AS last_altered
                    FROM system.information_schema.tables
                    WHERE table_catalog = ?
                      AND table_schema  = ?
                      AND table_type    = ?
                    ORDER BY table_name
                    LIMIT ?
                    """,
                    (catalog_name, schema_name, table_type, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        table_catalog  AS catalog_name,
                        table_schema   AS schema_name,
                        table_name,
                        table_type,
                        data_source_format,
                        table_owner,
                        comment,
                        CAST(created   AS STRING) AS created,
                        CAST(last_altered AS STRING) AS last_altered
                    FROM system.information_schema.tables
                    WHERE table_catalog = ?
                      AND table_schema  = ?
                    ORDER BY table_name
                    LIMIT ?
                    """,
                    (catalog_name, schema_name, limit),
                )
            return self._rows_to_dicts(cursor)
        finally:
            cursor.close()

    # ── columns ───────────────────────────────────────────────────────────────

    def get_table_columns(
        self, catalog_name: str, schema_name: str, table_name: str
    ) -> list[dict]:
        """Return all columns for a specific table.

        Args:
            catalog_name: Target catalog.
            schema_name: Target schema.
            table_name: Target table.

        Returns:
            List of dicts describing each column in ordinal order.
        """
        cursor = self.db.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    column_name,
                    ordinal_position,
                    data_type,
                    CASE WHEN is_nullable = 'YES' THEN true ELSE false END AS is_nullable,
                    column_default,
                    comment,
                    partition_index
                FROM system.information_schema.columns
                WHERE table_catalog = ?
                  AND table_schema  = ?
                  AND table_name    = ?
                ORDER BY ordinal_position
                """,
                (catalog_name, schema_name, table_name),
            )
            return self._rows_to_dicts(cursor)
        finally:
            cursor.close()

    def get_table_meta(
        self, catalog_name: str, schema_name: str, table_name: str
    ) -> Optional[dict]:
        """Return table-level metadata for a single table.

        Args:
            catalog_name: Target catalog.
            schema_name: Target schema.
            table_name: Target table.

        Returns:
            Dict with table metadata, or ``None`` if not found.
        """
        cursor = self.db.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    table_catalog  AS catalog_name,
                    table_schema   AS schema_name,
                    table_name,
                    table_type,
                    data_source_format,
                    table_owner,
                    comment
                FROM system.information_schema.tables
                WHERE table_catalog = ?
                  AND table_schema  = ?
                  AND table_name    = ?
                LIMIT 1
                """,
                (catalog_name, schema_name, table_name),
            )
            rows = self._rows_to_dicts(cursor)
            return rows[0] if rows else None
        finally:
            cursor.close()

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _rows_to_dicts(cursor) -> list[dict]:
        """Convert cursor results to a list of dicts using column names."""
        rows = cursor.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in rows]
