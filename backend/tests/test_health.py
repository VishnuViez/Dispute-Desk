"""
test_health.py – Tests for the GET /health endpoint.
"""

import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_DB = str(_REPO_ROOT / "data" / "disputedesk.db")


def _make_client(db_path: str) -> TestClient:
    """Return a TestClient with DISPUTEDESK_DB set to the given path.

    We must reload the db module after changing the env var because DB_PATH
    is resolved at import time.
    """
    os.environ["DISPUTEDESK_DB"] = db_path

    # Force re-evaluation of DB_PATH by reloading the modules that cache it.
    import backend.app.db as db_module
    import backend.app.main as main_module

    importlib.reload(db_module)
    importlib.reload(main_module)

    return TestClient(main_module.app)


@pytest.fixture(autouse=True)
def _restore_real_db():
    """Reset DISPUTEDESK_DB to the real database after each health test."""
    yield
    # Restore the real DB path so subsequent test modules work correctly.
    os.environ["DISPUTEDESK_DB"] = _REAL_DB
    import backend.app.db as db_module
    import backend.app.main as main_module
    importlib.reload(db_module)
    importlib.reload(main_module)


def test_health_returns_200():
    """/health always returns HTTP 200."""
    # Use a path we know doesn't exist so the test is hermetic.
    client = _make_client("/nonexistent/path/disputedesk.db")
    response = client.get("/health")
    assert response.status_code == 200


def test_health_database_missing_when_db_absent():
    """/health reports database='missing' when DISPUTEDESK_DB points to a non-existent file."""
    client = _make_client("/nonexistent/path/disputedesk.db")
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["database"] == "missing"
