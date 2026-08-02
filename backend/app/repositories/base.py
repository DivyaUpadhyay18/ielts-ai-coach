"""
Base repository abstraction implementing common CRUD operations.

All domain repositories inherit from BaseRepository to guarantee a
consistent data-access interface and error-handling story.
"""
from abc import ABC
from typing import Any, Dict, List, Optional, TypeVar, Generic

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import DatabaseSession

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository with standard CRUD helpers.

    Subclasses must set:
      - table_name: the Supabase table name
      - id_column:  the primary key column (defaults to "id")
      - user_id_column: the owner FK column (defaults to "user_id")
    """

    table_name: str
    id_column: str = "id"
    user_id_column: str = "user_id"
    _ownable: bool = True

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _table(self):
        return self.db.table(self.table_name)

    def _execute(self, query, context: Optional[str] = None):
        return self.db.execute(query, context or self.table_name)

    def _row_to_dict(self, row: Any) -> Dict[str, Any]:
        """Convert a Supabase result row to a dict if needed."""
        if hasattr(row, "model_dump"):
            return row.model_dump()
        if isinstance(row, dict):
            return row
        return dict(row) if row else {}

    # ------------------------------------------------------------------
    # Standard CRUD
    # ------------------------------------------------------------------
    def get_by_id(self, record_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch a single record by primary key.

        If user_id is provided (and the repository is ownable), the query is
        scoped to that owner to prevent cross-user access (IDOR).
        """
        query = (
            self._table()
            .select("*")
            .eq(self.id_column, record_id)
        )
        if self._ownable and user_id is not None:
            query = query.eq(self.user_id_column, user_id)
        result = self._execute(query)
        if not result.data:
            raise NotFoundError(f"{self.table_name} not found")
        return result.data[0]

    def list(
        self,
        user_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List records with optional owner scoping, filters, ordering, pagination.
        """
        query = self._table().select("*")

        if self._ownable and user_id is not None:
            query = query.eq(self.user_id_column, user_id)

        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)

        if order_by:
            query = query.order(order_by, desc=descending)

        if limit is not None:
            query = query.limit(limit)

        if offset is not None:
            query = query.offset(offset)

        result = self._execute(query)
        return result.data or []

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record."""
        query = self._table().insert(data)
        result = self._execute(query)
        if not result.data:
            raise ConflictError(f"Failed to create {self.table_name}")
        return result.data[0]

    def update(
        self,
        record_id: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing record by primary key.

        If user_id is provided (and the repository is ownable), the update
        is scoped to the owner to prevent cross-user modification.
        """
        query = self._table().update(data).eq(self.id_column, record_id)
        if self._ownable and user_id is not None:
            query = query.eq(self.user_id_column, user_id)
        result = self._execute(query)
        if not result.data:
            raise NotFoundError(f"{self.table_name} not found")
        return result.data[0]

    def delete(self, record_id: str, user_id: Optional[str] = None) -> None:
        """
        Delete a record by primary key.

        If user_id is provided (and the repository is ownable), the delete
        is scoped to the owner to prevent cross-user deletion.
        """
        query = self._table().delete().eq(self.id_column, record_id)
        if self._ownable and user_id is not None:
            query = query.eq(self.user_id_column, user_id)
        result = self._execute(query)
        if not result.data:
            raise NotFoundError(f"{self.table_name} not found")

    def exists(self, record_id: str, user_id: Optional[str] = None) -> bool:
        """Check whether a record exists, optionally owner-scoped."""
        try:
            self.get_by_id(record_id, user_id)
            return True
        except NotFoundError:
            return False

    def count(
        self,
        user_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Count records matching the optional owner + filters."""
        query = self._table().select("*", count="exact")
        if self._ownable and user_id is not None:
            query = query.eq(self.user_id_column, user_id)
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        result = self._execute(query)
        return result.count or 0