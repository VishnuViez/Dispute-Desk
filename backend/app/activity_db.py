"""
activity_db.py – writable SQLite database for the analyst dashboard.

Kept completely separate from data/disputedesk.db (which is read-only).
Path defaults to data/activity.db next to the main database; override with
the ACTIVITY_DB env var. The file is created with the correct schema on first
use and is NOT committed to git.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT = _REPO_ROOT / "data" / "activity.db"
ACTIVITY_DB_PATH = Path(os.environ.get("ACTIVITY_DB", str(_DEFAULT)))

_DDL = """
CREATE TABLE IF NOT EXISTS tool_calls (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT    NOT NULL,          -- ISO-8601 datetime
    tool         TEXT    NOT NULL,          -- operation_id
    dispute_id   TEXT,
    transaction_id TEXT,
    params_json  TEXT,                      -- JSON string of query params
    status_code  INTEGER,
    duration_ms  REAL
);

CREATE TABLE IF NOT EXISTS recommendations (
    dispute_id   TEXT PRIMARY KEY,
    ts           TEXT NOT NULL,
    reason_code  TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    confidence   TEXT NOT NULL,
    response_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    dispute_id   TEXT NOT NULL,
    decision     TEXT NOT NULL,            -- approve | edit | override
    final_outcome TEXT NOT NULL,
    reason       TEXT,
    analyst      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS letters (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    dispute_id          TEXT NOT NULL,
    ts                  TEXT NOT NULL,
    outcome             TEXT NOT NULL,
    letter_text         TEXT NOT NULL,
    chargeback_summary  TEXT             -- NULL when outcome is not file_chargeback
);
"""


def _init(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


def get_activity_db() -> sqlite3.Connection:
    """Return a writable connection; create the schema on first call."""
    conn = sqlite3.connect(ACTIVITY_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init(conn)
    return conn
