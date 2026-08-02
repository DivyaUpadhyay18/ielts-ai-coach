"""
Database session helpers and error translation utilities.

Centralizes Supabase client access, error mapping to application exceptions,
and common query helpers used by repositories.
"""
from typing import Any

from app.core.exceptions import ConflictError, DatabaseError, NotFoundError, ValidationError
from app.db.supabase import get_supabase


class DatabaseSession:
    """
    Wraps the Supabase client with consistent error translation.

    All repository operations go through this class so that low-level
    Supabase exceptions are translated into the application's exception
    hierarchy (AppError subclasses) with a consistent envelope.
    """

    def __init__(self) -> None:
        self.client = get_supabase()

    # ------------------------------------------------------------------
    # Query builders
    # ------------------------------------------------------------------
    def table(self, table_name: str):
        """Return a Supabase table query builder for the given table."""
        try:
            return self.client.table(table_name)
        except Exception as e:
            raise DatabaseError(f"Failed to access table '{table_name}': {str(e)}")

    # ------------------------------------------------------------------
    # Execution helpers with error translation
    # ------------------------------------------------------------------
    def execute(self, query: Any, context: str = "database operation") -> Any:
        """
        Execute a Supabase query and translate any exception into an AppError.
        """
        try:
            return query.execute()
        except Exception as e:
            self._translate_error(e, context)
            raise DatabaseError(f"Database error during {context}: {str(e)}")

    def _translate_error(self, exc: Exception, context: str) -> None:
        """
        Map a Supabase exception to the appropriate application exception.
        """
        message = str(exc).lower()

        # Unique constraint violations
        if "duplicate" in message or "unique" in message or "violates unique" in message:
            raise ConflictError(
                f"Resource already exists: {context}",
                fields={"resource": context},
            )

        # Foreign key violations
        if "foreign key" in message or "violates foreign" in message:
            raise ValidationError(
                f"Referenced resource does not exist: {context}",
                fields={"resource": context},
            )

        # Check constraint violations (status/value out of range, etc.)
        if "check constraint" in message or "violates check" in message:
            raise ValidationError(
                f"Invalid value for {context}",
                fields={"resource": context},
            )

        # Not-null violations
        if "not null" in message or "null value in column" in message:
            raise ValidationError(
                f"Missing required value for {context}",
                fields={"resource": context},
            )

        # Invalid UUID / cast errors
        if "invalid input syntax" in message or "invalid uuid" in message:
            raise ValidationError(
                f"Invalid identifier format: {context}",
                fields={"resource": context},
            )

        # Everything else → generic database error
        raise DatabaseError(f"Database error during {context}: {str(exc)}")


# Singleton session instance shared across the application
db_session = DatabaseSession()


def get_db() -> DatabaseSession:
    """
    FastAPI dependency that returns the shared database session.
    """
    return db_session