"""
db.py – SQLite connection management.

One connection is opened per request and closed when the request ends.
The database is always opened read-only so backend tool endpoints cannot
accidentally mutate shared test data.
"""

import os
import sqlite3
from pathlib import Path
from typing import Generator

# Resolve the DB path once at import time.
# DISPUTEDESK_DB env var overrides the default; the default is always
# relative to the repo root (the directory that contains this package),
# not the process's current working directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]  # backend/app/ -> repo root
_DEFAULT_DB = _REPO_ROOT / "data" / "disputedesk.db"
DB_PATH = Path(os.environ.get("DISPUTEDESK_DB", str(_DEFAULT_DB)))


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: yield a read-only SQLite connection, then close it."""
    if not DB_PATH.exists():
        # Yield None so callers can detect a missing database gracefully.
        yield None
        return

    # uri=True enables the SQLite URI filename syntax needed for read-only mode.
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
