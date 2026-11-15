"""
main.py – DisputeDesk Tools API entry point.
"""

import sqlite3
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from backend.app.db import get_db
from backend.app.middleware import ActivityLogMiddleware
from backend.app.models import HealthResponse
from backend.app.routers import api, deadline, recommendation, tools

app = FastAPI(
    title="DisputeDesk Tools API",
    description="Backend tools for the DisputeDesk card-dispute AI agent.",
)

# Allow all origins for local development. Tighten this before any deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Log every /tools/* request to the activity database.
app.add_middleware(ActivityLogMiddleware)

app.include_router(tools.router, prefix="/tools")
app.include_router(deadline.router, prefix="/tools")
app.include_router(recommendation.router, prefix="/tools")

# Dashboard API – NOT under /tools so Orchestrate never sees it.
app.include_router(api.router, prefix="/api")


@app.get(
    "/health",
    response_model=HealthResponse,
    operation_id="health_check",
    summary="Check that the API and database are reachable.",
)
def health_check(db: sqlite3.Connection | None = Depends(get_db)) -> HealthResponse:
    """Return API status and whether the database file is present."""
    db_status = "connected" if db is not None else "missing"
    return HealthResponse(status="ok", database=db_status)
