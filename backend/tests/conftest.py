"""
Test configuration: mock Supabase before any app imports so tests can run
without a live Supabase connection.
"""
import os
import sys
from unittest.mock import MagicMock

# Set dummy env vars so settings loads.
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ALGORITHM", "HS256")

# Inject mock supabase into sys.modules before app imports.
_mock_supabase = MagicMock()
_mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = {
    "data": None,
    "error": None,
}
sys.modules.setdefault("app.db.supabase", _mock_supabase)

# Ensure backend is on the path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
