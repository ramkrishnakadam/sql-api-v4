"""Business logic for the SqlApiV4 feature."""

import logging
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Depends

from sql_api_v4.repository import SqlApiV4Repository
from sql_api_v4.schemas import SqlApiV4HealthResponse, SqlApiV4Item

logger = logging.getLogger(__name__)


@dataclass
class SqlApiV4Service:
    """Service layer for the SqlApiV4 feature."""

    repo: Annotated[SqlApiV4Repository, Depends(SqlApiV4Repository)]

    def health(self) -> SqlApiV4HealthResponse:
        """Verify the data source is reachable."""
        self.repo.ping()
        return SqlApiV4HealthResponse(status="healthy", feature="sql_api_v4")

    def get_item(self, item_id: str) -> Optional[SqlApiV4Item]:
        """Fetch one item by ID."""
        row = self.repo.get_item(item_id)
        if row is None:
            return None
        return SqlApiV4Item.model_validate(row)


SqlApiV4ServiceDep = Annotated[SqlApiV4Service, Depends(SqlApiV4Service)]
