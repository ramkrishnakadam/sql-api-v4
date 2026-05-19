"""Shared fixtures for SqlApiV4 unit tests."""

from unittest.mock import MagicMock

import pytest

from sql_api_v4.repository import SqlApiV4Repository
from sql_api_v4.service import SqlApiV4Service


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock(spec=SqlApiV4Repository)
    repo.ping.return_value = True
    repo.get_item.return_value = {"id": "i-1", "name": "Example", "status": "active"}
    return repo


@pytest.fixture
def service(mock_repo: MagicMock) -> SqlApiV4Service:
    return SqlApiV4Service(repo=mock_repo)
