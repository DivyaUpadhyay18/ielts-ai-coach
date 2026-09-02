"""Supabase client bootstrap.

The client is built **lazily** on first attribute access so that the FastAPI
application can boot even when ``SUPABASE_URL`` / ``SUPABASE_SERVICE_ROLE_KEY``
are not yet configured (e.g. local development with a placeholder ``.env``).
Every ``from app.db.supabase import supabase`` import keeps working unchanged;
DB-backed routes surface a clear error message instead of crashing the whole
app at import time.
"""
from typing import Any

from supabase import ClientOptions, create_client, Client

from app.core.config import settings

_client: Client | None = None
_client_error: Exception | None = None


class _LazySupabaseClient:
    """Builds the underlying Supabase client on first attribute access."""

    def _get_client(self) -> Client:
        global _client, _client_error
        if _client is not None:
            return _client
        if _client_error is not None:
            raise _client_error
        try:
            _client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY,
                # Defense in depth: cap PostgREST (table) requests at 10s
                # instead of the library default of 120s, so any blocking
                # supabase.table(...) call that is not individually wrapped
                # in asyncio.wait_for still fails fast rather than hanging
                # the single-worker event loop for 2 minutes.
                options=ClientOptions(postgrest_client_timeout=10),
            )
        except Exception as exc:  # pragma: no cover - depends on env config
            _client_error = exc
            raise exc
        return _client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_client(), name)


# Lazy proxy — existing `from app.db.supabase import supabase` usages work
# unchanged (``supabase.table(...)``, ``supabase.auth(...)``, etc.).
supabase: Client = _LazySupabaseClient()  # type: ignore[assignment]


def get_supabase():
    """
    Helper function to return the supabase client.

    The client is created on first use; can be used for Dependency Injection
    in FastAPI routes.
    """
    return supabase