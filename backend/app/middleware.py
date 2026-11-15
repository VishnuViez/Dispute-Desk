"""
middleware.py – Starlette middleware that logs every /tools/* request to
the tool_calls table in activity.db.

Design rules:
- Logging must NEVER raise or slow a tool call.  All DB writes are wrapped
  in try/except.
- The operation_id is extracted from the matched route's name attribute
  (FastAPI stores it there).
- dispute_id and transaction_id are pulled from path params and query params.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.activity_db import get_activity_db


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _extract_ids(request: Request) -> tuple[str | None, str | None]:
    """Pull dispute_id and transaction_id from path and query params."""
    path_params = dict(request.path_params)
    query_params = dict(request.query_params)
    dispute_id = path_params.get("dispute_id") or query_params.get("dispute_id")
    transaction_id = path_params.get("transaction_id") or query_params.get("transaction_id")
    return dispute_id, transaction_id


def _operation_id(request: Request) -> str | None:
    """Return the matched route's operation_id (stored as the route name)."""
    route = request.scope.get("route")
    if route is None:
        return None
    # FastAPI sets route.name = operation_id when operation_id is explicit.
    return getattr(route, "name", None)


class ActivityLogMiddleware(BaseHTTPMiddleware):
    """Log every /tools/* request into activity.db after the response is sent."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.url.path.startswith("/tools/"):
            return await call_next(request)

        t0 = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - t0) * 1000

        try:
            op_id = _operation_id(request)
            if op_id is None:
                return response  # unmatched route, skip

            dispute_id, transaction_id = _extract_ids(request)
            # Gather query params (excluding the standard FastAPI ones)
            params = {k: v for k, v in request.query_params.items()}

            conn = get_activity_db()
            try:
                conn.execute(
                    """INSERT INTO tool_calls
                       (ts, tool, dispute_id, transaction_id, params_json,
                        status_code, duration_ms)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        _now(),
                        op_id,
                        dispute_id,
                        transaction_id,
                        json.dumps(params) if params else None,
                        response.status_code,
                        round(duration_ms, 2),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass  # logging must never break a tool call

        return response
