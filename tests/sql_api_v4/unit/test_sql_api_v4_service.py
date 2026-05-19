"""Unit tests for the SqlApiV4 service."""

from unittest.mock import MagicMock


def test_health_returns_healthy(service, mock_repo: MagicMock) -> None:
    result = service.health()
    assert result.status == "healthy"
    assert result.feature == "sql_api_v4"
    mock_repo.ping.assert_called_once()


def test_get_item_returns_item(service, mock_repo: MagicMock) -> None:
    item = service.get_item("i-1")
    assert item is not None
    assert item.id == "i-1"
    assert item.name == "Example"
    mock_repo.get_item.assert_called_once_with("i-1")


def test_get_item_returns_none_when_missing(service, mock_repo: MagicMock) -> None:
    mock_repo.get_item.return_value = None
    assert service.get_item("missing") is None
