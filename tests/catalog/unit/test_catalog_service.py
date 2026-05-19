"""Unit tests for CatalogService."""

from unittest.mock import MagicMock

import pytest

from catalog.repository import CatalogRepository
from catalog.service import CatalogService


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock(spec=CatalogRepository)
    repo.ping.return_value = True
    repo.list_catalogs.return_value = [
        {"catalog_name": "main", "catalog_owner": "admins", "comment": None},
        {"catalog_name": "hive_metastore", "catalog_owner": "admins", "comment": None},
    ]
    repo.list_schemas.return_value = [
        {"catalog_name": "main", "schema_name": "default", "schema_owner": "admins", "comment": None},
        {"catalog_name": "main", "schema_name": "information_schema", "schema_owner": "admins", "comment": None},
    ]
    repo.list_tables.return_value = [
        {
            "catalog_name": "main", "schema_name": "default", "table_name": "flights",
            "table_type": "MANAGED", "data_source_format": "DELTA",
            "table_owner": "data_team", "comment": "Raw flight events",
            "created": "2025-01-15T08:00:00Z", "last_altered": "2026-04-01T12:00:00Z",
        }
    ]
    repo.get_table_meta.return_value = {
        "catalog_name": "main", "schema_name": "default", "table_name": "flights",
        "table_type": "MANAGED", "data_source_format": "DELTA",
        "table_owner": "data_team", "comment": None,
    }
    repo.get_table_columns.return_value = [
        {
            "column_name": "flight_id", "ordinal_position": 1, "data_type": "STRING",
            "is_nullable": False, "column_default": None, "comment": "Unique ID",
            "partition_index": None,
        },
        {
            "column_name": "origin", "ordinal_position": 2, "data_type": "STRING",
            "is_nullable": True, "column_default": None, "comment": "Origin airport code",
            "partition_index": None,
        },
    ]
    return repo


@pytest.fixture
def service(mock_repo: MagicMock) -> CatalogService:
    return CatalogService(repo=mock_repo)


# ── health ────────────────────────────────────────────────────────────────────

def test_health_returns_healthy(service: CatalogService, mock_repo: MagicMock) -> None:
    result = service.health()
    assert result.status == "healthy"
    assert result.feature == "catalog"
    mock_repo.ping.assert_called_once()


# ── catalogs ──────────────────────────────────────────────────────────────────

def test_list_catalogs_returns_all(service: CatalogService, mock_repo: MagicMock) -> None:
    result = service.list_catalogs()
    assert result.total == 2
    assert result.catalogs[0].catalog_name == "main"
    mock_repo.list_catalogs.assert_called_once()


def test_list_catalogs_passes_limit(service: CatalogService, mock_repo: MagicMock) -> None:
    service.list_catalogs(limit=10)
    mock_repo.list_catalogs.assert_called_once_with(limit=10)


# ── schemas ───────────────────────────────────────────────────────────────────

def test_list_schemas_returns_schemas(service: CatalogService, mock_repo: MagicMock) -> None:
    result = service.list_schemas("main")
    assert result.total == 2
    assert result.schemas[0].schema_name == "default"
    mock_repo.list_schemas.assert_called_once_with(catalog_name="main", limit=500)


def test_list_schemas_raises_for_unknown_catalog(
    service: CatalogService, mock_repo: MagicMock
) -> None:
    mock_repo.list_schemas.return_value = []
    mock_repo.list_catalogs.return_value = [
        {"catalog_name": "main", "catalog_owner": "admins", "comment": None}
    ]
    with pytest.raises(LookupError, match="Catalog 'missing'"):
        service.list_schemas("missing")


# ── tables ────────────────────────────────────────────────────────────────────

def test_list_tables_returns_tables(service: CatalogService, mock_repo: MagicMock) -> None:
    result = service.list_tables("main", "default")
    assert result.total == 1
    assert result.tables[0].table_name == "flights"
    assert result.tables[0].table_type == "MANAGED"


def test_list_tables_passes_type_filter(service: CatalogService, mock_repo: MagicMock) -> None:
    service.list_tables("main", "default", table_type="MANAGED")
    mock_repo.list_tables.assert_called_once_with(
        catalog_name="main", schema_name="default", table_type="MANAGED", limit=500
    )


def test_list_tables_raises_for_unknown_schema(
    service: CatalogService, mock_repo: MagicMock
) -> None:
    mock_repo.list_tables.return_value = []
    mock_repo.list_schemas.return_value = [
        {"catalog_name": "main", "schema_name": "default", "schema_owner": "a", "comment": None}
    ]
    with pytest.raises(LookupError, match="Schema 'main.missing'"):
        service.list_tables("main", "missing")


# ── table detail ──────────────────────────────────────────────────────────────

def test_get_table_detail_returns_columns(
    service: CatalogService, mock_repo: MagicMock
) -> None:
    result = service.get_table_detail("main", "default", "flights")
    assert result.table_name == "flights"
    assert result.column_count == 2
    assert result.columns[0].column_name == "flight_id"
    assert result.columns[0].is_nullable is False
    assert result.columns[1].column_name == "origin"


def test_get_table_detail_raises_for_unknown_table(
    service: CatalogService, mock_repo: MagicMock
) -> None:
    mock_repo.get_table_meta.return_value = None
    with pytest.raises(LookupError, match="Table 'main.default.ghost'"):
        service.get_table_detail("main", "default", "ghost")
