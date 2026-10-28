"""
conftest.py – shared test fixtures for backend/tests.

Ensures that DISPUTEDESK_DB is reset to the real database path before any
test module that needs a live connection. This is needed because test_health.py
sets DISPUTEDESK_DB to a nonexistent path and reloads the db module.
"""

import importlib
import os
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_DB = str(_REPO_ROOT / "data" / "disputedesk.db")


@pytest.fixture(autouse=True, scope="session")
def reset_db_path_after_health_tests():
    """
    Guarantee the real DB path is in effect for all sessions.
    We yield first (runs before all tests), then reset after.
    """
    yield
    # After all tests: restore to the real DB and reload modules.
    os.environ["DISPUTEDESK_DB"] = _REAL_DB
    import backend.app.db as db_module
    import backend.app.main as main_module
    importlib.reload(db_module)
    importlib.reload(main_module)
