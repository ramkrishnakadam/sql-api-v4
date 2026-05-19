"""Pydantic request/response schemas for the catalog scanning feature.

Mirrors the Unity Catalog system.information_schema tables.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CatalogHealthResponse(BaseModel):
    """Health payload for the catalog feature."""

    status: str
    feature: str = "catalog"


# ── Catalogs ──────────────────────────────────────────────────────────────────

class CatalogItem(BaseModel):
    """A single Unity Catalog catalog entry."""

    catalog_name: str = Field(..., description="Catalog name", max_length=256)
    catalog_owner: Optional[str] = Field(default=None, description="Owner principal")
    comment: Optional[str] = Field(default=None, description="Optional description")

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "catalog_name": "main",
                "catalog_owner": "admins",
                "comment": "Default catalog",
            }
        },
    )


class CatalogListResponse(BaseModel):
    """Paginated list of catalogs."""

    catalogs: list[CatalogItem]
    total: int

    model_config = ConfigDict(
        json_schema_extra={"example": {"catalogs": [], "total": 0}}
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class SchemaItem(BaseModel):
    """A single Unity Catalog schema (database) entry."""

    catalog_name: str = Field(..., description="Parent catalog")
    schema_name: str = Field(..., description="Schema name", max_length=256)
    schema_owner: Optional[str] = Field(default=None, description="Owner principal")
    comment: Optional[str] = Field(default=None, description="Optional description")

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "catalog_name": "main",
                "schema_name": "information_schema",
                "schema_owner": "admins",
                "comment": None,
            }
        },
    )


class SchemaListResponse(BaseModel):
    """Paginated list of schemas."""

    schemas: list[SchemaItem]
    total: int

    model_config = ConfigDict(
        json_schema_extra={"example": {"schemas": [], "total": 0}}
    )


# ── Tables ────────────────────────────────────────────────────────────────────

class TableItem(BaseModel):
    """A single Unity Catalog table entry."""

    catalog_name: str = Field(..., description="Parent catalog")
    schema_name: str = Field(..., description="Parent schema")
    table_name: str = Field(..., description="Table name", max_length=256)
    table_type: Optional[str] = Field(
        default=None, description="BASE TABLE, VIEW, EXTERNAL, MANAGED, etc."
    )
    data_source_format: Optional[str] = Field(
        default=None, description="DELTA, PARQUET, CSV, etc."
    )
    table_owner: Optional[str] = Field(default=None, description="Owner principal")
    comment: Optional[str] = Field(default=None, description="Table description")
    created: Optional[str] = Field(default=None, description="ISO-8601 creation timestamp")
    last_altered: Optional[str] = Field(default=None, description="ISO-8601 last-altered timestamp")

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "catalog_name": "main",
                "schema_name": "default",
                "table_name": "flights",
                "table_type": "MANAGED",
                "data_source_format": "DELTA",
                "table_owner": "data_team",
                "comment": "Raw flight events",
                "created": "2025-01-15T08:00:00Z",
                "last_altered": "2026-04-01T12:00:00Z",
            }
        },
    )


class TableListResponse(BaseModel):
    """Paginated list of tables."""

    tables: list[TableItem]
    total: int

    model_config = ConfigDict(
        json_schema_extra={"example": {"tables": [], "total": 0}}
    )


# ── Columns ───────────────────────────────────────────────────────────────────

class ColumnItem(BaseModel):
    """A single column in a Unity Catalog table."""

    column_name: str = Field(..., description="Column name")
    ordinal_position: int = Field(..., description="1-based column position")
    data_type: str = Field(..., description="SQL data type")
    is_nullable: bool = Field(..., description="Whether the column accepts NULL")
    column_default: Optional[str] = Field(default=None, description="Default expression")
    comment: Optional[str] = Field(default=None, description="Column description")
    partition_index: Optional[int] = Field(
        default=None, description="Non-null if column is a partition key"
    )

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "column_name": "flight_id",
                "ordinal_position": 1,
                "data_type": "STRING",
                "is_nullable": False,
                "column_default": None,
                "comment": "Unique flight identifier",
                "partition_index": None,
            }
        },
    )


class TableDetailResponse(BaseModel):
    """Full table detail including all columns."""

    catalog_name: str
    schema_name: str
    table_name: str
    table_type: Optional[str] = None
    data_source_format: Optional[str] = None
    table_owner: Optional[str] = None
    comment: Optional[str] = None
    columns: list[ColumnItem] = Field(default_factory=list)
    column_count: int = 0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "catalog_name": "main",
                "schema_name": "default",
                "table_name": "flights",
                "table_type": "MANAGED",
                "data_source_format": "DELTA",
                "table_owner": "data_team",
                "comment": None,
                "columns": [],
                "column_count": 0,
            }
        }
    )
