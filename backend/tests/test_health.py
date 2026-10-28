"""
test_health.py – Tests for the GET /health endpoint.
"""

import os
import pytest
from fastapi.testclient import TestClient


def _make_client(db_path: str) -> TestClient:
    """Return a TestClient with DISPUTEDESK_DB set to the given path.

    We must reload the db module after changing the env var because DB_PATH
    is resolved at import time.
    """
    os.environ["DISPUTEDESK_DB"] = db_path

    # Force re-evaluation of DB_PATH by reloading the modules that cache it.
    import importlib
    import backend.app.db as db_module
    import backend.app.main as main_module

    importlib.reload(db_module)
    importlib.reload(main_module)

    return TestClient(main_module.app)


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
