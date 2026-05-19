"""Data access for the SqlApiV4 feature."""

import logging
from dataclasses import dataclass
from typing import Optional

from core.database import ConnectionDep

logger = logging.getLogger(__name__)


@dataclass
class SqlApiV4Repository:
    """Repository for SqlApiV4 data access."""

    db: ConnectionDep

    def ping(self) -> bool:
        """Lightweight connectivity check."""
        cursor = self.db.cursor()
        try:
            cursor.execute("SELECT 1")
            return True
        finally:
            cursor.close()

    def get_item(self, item_id: str) -> Optional[dict]:
        """Fetch one item by ID. Returns ``None`` if not found.

        Replace this stub with a real query against your table.
        """
        cursor = self.db.cursor()
        try:
            # Example: parameterised query — never use string formatting for values.
            cursor.execute(
                "SELECT id, name, status FROM sql_api_v4_items WHERE id = ? LIMIT 1",
                (item_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))
        finally:
            cursor.close()
