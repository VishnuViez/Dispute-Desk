"""
test_api.py – Tests for the /api dashboard endpoints and the activity-log
middleware.

Covers:
- GET /api/stats
- GET /api/cases (and filters)
- GET /api/cases/{dispute_id}
- POST /api/cases/{dispute_id}/decision (happy path + validation)
- GET /api/activity  (and that a /tools call creates a row)
- GET /api/audit
- GET /api/evaluation
- export_openapi still exports only the 7 /tools operations
"""

from __future__ import annotations

import importlib
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]

# Point both DBs at real data / a temp activity DB for the session.
os.environ["DISPUTEDESK_DB"] = str(REPO_ROOT / "data" / "disputedesk.db")


# ---------------------------------------------------------------------------
# Helpers – build a fresh client + temp activity DB for each test that needs
# an isolated activity DB, so tests don't pollute each other.
# ---------------------------------------------------------------------------

def _client(activity_path: str | None = None) -> TestClient:
    if activity_path:
        os.environ["ACTIVITY_DB"] = activity_path
    import backend.app.activity_db as _adb
    import backend.app.db as _db_mod
    import backend.app.main as _main_mod
    importlib.reload(_adb)
    importlib.reload(_db_mod)
    importlib.reload(_main_mod)
    return TestClient(_main_mod.app)


@pytest.fixture()
def client_with_tmpdb(tmp_path):
    """Client that uses a fresh empty activity.db in a temp dir."""
    db_path = str(tmp_path / "activity.db")
    c = _client(activity_path=db_path)
    yield c
    # Reset env so other tests get the default path.
    os.environ.pop("ACTIVITY_DB", None)


# ---------------------------------------------------------------------------
# 1. GET /api/stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_returns_200(self, client_with_tmpdb):
        r = client_with_tmpdb.get("/api/stats")
        assert r.status_code == 200

    def test_shape(self, client_with_tmpdb):
        data = client_with_tmpdb.get("/api/stats").json()
        for key in ("open_disputes", "by_card_type", "by_recommendation",
                    "by_reason_code", "near_deadline"):
            assert key in data, f"Missing key: {key}"

    def test_open_disputes_matches_db(self, client_with_tmpdb):
        data = client_with_tmpdb.get("/api/stats").json()
        # We know the generated DB has exactly 30 open disputes.
        assert data["open_disputes"] == 30

    def test_not_investigated_present(self, client_with_tmpdb):
        # With a fresh activity DB, every case is not_investigated.
        data = client_with_tmpdb.get("/api/stats").json()
        assert data["by_recommendation"].get("not_investigated", 0) == 30


# ---------------------------------------------------------------------------
# 2. GET /api/cases
# ---------------------------------------------------------------------------

class TestCases:
    def test_returns_200(self, client_with_tmpdb):
        r = client_with_tmpdb.get("/api/cases")
        assert r.status_code == 200

    def test_total_matches_open_disputes(self, client_with_tmpdb):
        # Default: returns all disputes (open and others), but our DB
        # has 30 open + ~20 background.
        data = client_with_tmpdb.get("/api/cases").json()
        assert "total" in data
        assert "cases" in data
        assert data["total"] >= 30

    def test_status_filter(self, client_with_tmpdb):
        data = client_with_tmpdb.get("/api/cases", params={"status": "open"}).json()
        assert data["total"] == 30
        assert all(c["recommendation"] == "not_investigated" for c in data["cases"])

    def test_card_type_filter(self, client_with_tmpdb):
        data = client_with_tmpdb.get("/api/cases", params={"card_type": "credit"}).json()
        assert all(c["card_type"] == "credit" for c in data["cases"])

    def test_q_search(self, client_with_tmpdb):
        data = client_with_tmpdb.get("/api/cases", params={"q": "DSP-0021"}).json()
        assert any(c["dispute_id"] == "DSP-0021" for c in data["cases"])

    def test_deadline_within_days(self, client_with_tmpdb):
        data = client_with_tmpdb.get(
            "/api/cases", params={"deadline_within_days": 9999}
        ).json()
        assert all(c["days_to_deadline"] <= 9999 for c in data["cases"])

    def test_case_summary_fields(self, client_with_tmpdb):
        cases = client_with_tmpdb.get("/api/cases", params={"status": "open"}).json()["cases"]
        assert len(cases) > 0
        c = cases[0]
        for field in ("dispute_id", "filed_date", "customer_id", "merchant_name",
                      "amount_usd", "card_type", "days_to_deadline",
                      "recommendation", "confidence"):
            assert field in c, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# 3. GET /api/cases/{dispute_id}
# ---------------------------------------------------------------------------

class TestCaseDetail:
    def test_known_case_returns_200(self, client_with_tmpdb):
        r = client_with_tmpdb.get("/api/cases/DSP-0021")
        assert r.status_code == 200

    def test_unknown_returns_404(self, client_with_tmpdb):
        r = client_with_tmpdb.get("/api/cases/DSP-9999")
        assert r.status_code == 404

    def test_shape(self, client_with_tmpdb):
        data = client_with_tmpdb.get("/api/cases/DSP-0021").json()
        for key in ("dispute", "transaction", "friendly_fraud_signals",
                    "recommendation", "decisions"):
            assert key in data, f"Missing key: {key}"

    def test_friendly_fraud_signals_present(self, client_with_tmpdb):
        data = client_with_tmpdb.get("/api/cases/DSP-0021").json()
        sig = data["friendly_fraud_signals"]
        for field in ("prior_undisputed_with_merchant", "same_device_count",
                      "same_address_count", "device_seen_before",
                      "address_seen_before", "prior_disputes_count",
                      "prior_disputes_lost"):
            assert field in sig

    def test_recommendation_null_before_investigated(self, client_with_tmpdb):
        data = client_with_tmpdb.get("/api/cases/DSP-0021").json()
        assert data["recommendation"] is None

    def test_deadline_populated_after_recommendation(self, client_with_tmpdb):
        # Run recommend_outcome so a recommendation row is saved.
        client_with_tmpdb.get(
            "/tools/disputes/DSP-0021/recommendation",
            params={"reason_code": "12.6.1"},
        )
        data = client_with_tmpdb.get("/api/cases/DSP-0021").json()
        assert data["recommendation"] is not None
        assert data["deadline"] is not None


# ---------------------------------------------------------------------------
# 4. POST /api/cases/{dispute_id}/decision
# ---------------------------------------------------------------------------

class TestPostDecision:
    _APPROVE = {
        "decision": "approve",
        "final_outcome": "file_chargeback",
        "analyst": "analyst-1",
    }

    def test_approve_returns_201_or_200(self, client_with_tmpdb):
        r = client_with_tmpdb.post("/api/cases/DSP-0021/decision", json=self._APPROVE)
        assert r.status_code in (200, 201)
        data = r.json()
        assert data["dispute_id"] == "DSP-0021"
        assert data["decision"] == "approve"
        assert "id" in data

    def test_override_requires_reason(self, client_with_tmpdb):
        r = client_with_tmpdb.post(
            "/api/cases/DSP-0021/decision",
            json={"decision": "override", "final_outcome": "deny", "analyst": "a"},
        )
        assert r.status_code == 422

    def test_edit_requires_reason(self, client_with_tmpdb):
        r = client_with_tmpdb.post(
            "/api/cases/DSP-0021/decision",
            json={"decision": "edit", "final_outcome": "escalate", "analyst": "a"},
        )
        assert r.status_code == 422

    def test_edit_with_reason_succeeds(self, client_with_tmpdb):
        r = client_with_tmpdb.post(
            "/api/cases/DSP-0021/decision",
            json={
                "decision": "edit",
                "final_outcome": "deny",
                "reason": "Reviewed and disagree",
                "analyst": "analyst-2",
            },
        )
        assert r.status_code == 200

    def test_bad_decision_value_returns_422(self, client_with_tmpdb):
        r = client_with_tmpdb.post(
            "/api/cases/DSP-0021/decision",
            json={"decision": "invalid", "final_outcome": "deny", "analyst": "a"},
        )
        assert r.status_code == 422

    def test_unknown_dispute_returns_404(self, client_with_tmpdb):
        r = client_with_tmpdb.post(
            "/api/cases/DSP-9999/decision", json=self._APPROVE
        )
        assert r.status_code == 404

    def test_decision_appears_in_case_detail(self, client_with_tmpdb):
        client_with_tmpdb.post("/api/cases/DSP-0021/decision", json=self._APPROVE)
        detail = client_with_tmpdb.get("/api/cases/DSP-0021").json()
        assert len(detail["decisions"]) >= 1
        assert detail["decisions"][0]["decision"] == "approve"


# ---------------------------------------------------------------------------
# 5. GET /api/activity – and middleware creates tool_calls rows
# ---------------------------------------------------------------------------

class TestActivity:
    def test_empty_on_fresh_db(self, client_with_tmpdb):
        r = client_with_tmpdb.get("/api/activity")
        assert r.status_code == 200
        assert r.json() == []

    def test_tools_call_creates_row(self, client_with_tmpdb):
        # Make a /tools call.
        client_with_tmpdb.get("/tools/disputes/DSP-0021")
        rows = client_with_tmpdb.get("/api/activity").json()
        assert len(rows) >= 1
        assert rows[0]["tool"] == "get_dispute"
        assert rows[0]["stage"] == "Intake"
        assert rows[0]["dispute_id"] == "DSP-0021"

    def test_since_parameter(self, client_with_tmpdb):
        client_with_tmpdb.get("/tools/disputes/DSP-0021")
        client_with_tmpdb.get("/tools/disputes/DSP-0022")
        all_rows = client_with_tmpdb.get("/api/activity").json()
        first_id = all_rows[0]["id"]
        later = client_with_tmpdb.get("/api/activity", params={"since": first_id}).json()
        assert all(r["id"] > first_id for r in later)

    def test_stage_labels(self, client_with_tmpdb):
        client_with_tmpdb.get("/tools/disputes/DSP-0021")
        client_with_tmpdb.get(
            "/tools/customers/CUST-0001/history"
        )
        rows = {r["tool"]: r for r in client_with_tmpdb.get("/api/activity").json()}
        assert rows.get("get_dispute", {}).get("stage") == "Intake"
        assert rows.get("get_customer_history", {}).get("stage") == "Evidence"

    def test_recommend_outcome_stage(self, client_with_tmpdb):
        client_with_tmpdb.get(
            "/tools/disputes/DSP-0021/recommendation",
            params={"reason_code": "12.6.1"},
        )
        rows = client_with_tmpdb.get("/api/activity").json()
        rec_rows = [r for r in rows if r["tool"] == "recommend_outcome"]
        assert len(rec_rows) >= 1
        assert rec_rows[0]["stage"] == "Decision"


# ---------------------------------------------------------------------------
# 6. GET /api/audit
# ---------------------------------------------------------------------------

class TestAudit:
    def test_returns_200(self, client_with_tmpdb):
        r = client_with_tmpdb.get("/api/audit")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_combines_tool_calls_and_decisions(self, client_with_tmpdb):
        client_with_tmpdb.get("/tools/disputes/DSP-0021")
        client_with_tmpdb.post(
            "/api/cases/DSP-0021/decision",
            json={"decision": "approve", "final_outcome": "file_chargeback", "analyst": "a"},
        )
        rows = client_with_tmpdb.get("/api/audit").json()
        types = {r["type"] for r in rows}
        assert "tool_call" in types
        assert "decision" in types

    def test_sorted_by_ts(self, client_with_tmpdb):
        client_with_tmpdb.get("/tools/disputes/DSP-0021")
        rows = client_with_tmpdb.get("/api/audit").json()
        if len(rows) >= 2:
            assert rows[0]["ts"] <= rows[-1]["ts"]


# ---------------------------------------------------------------------------
# 7. GET /api/evaluation
# ---------------------------------------------------------------------------

class TestEvaluation:
    def test_returns_200(self, client_with_tmpdb):
        r = client_with_tmpdb.get("/api/evaluation")
        assert r.status_code == 200

    def test_shape(self, client_with_tmpdb):
        data = client_with_tmpdb.get("/api/evaluation").json()
        for key in ("total_cases", "investigated", "correct", "accuracy", "matches"):
            assert key in data

    def test_zero_investigated_on_fresh_db(self, client_with_tmpdb):
        data = client_with_tmpdb.get("/api/evaluation").json()
        assert data["investigated"] == 0
        assert data["accuracy"] == 0.0
        assert data["matches"] == []

    def test_accuracy_improves_after_recommendation(self, client_with_tmpdb):
        # Run recommend_outcome for Demo A (should be file_chargeback – correct).
        client_with_tmpdb.get(
            "/tools/disputes/DSP-0021/recommendation",
            params={"reason_code": "12.6.1"},
        )
        data = client_with_tmpdb.get("/api/evaluation").json()
        assert data["investigated"] == 1
        assert data["matches"][0]["dispute_id"] == "DSP-0021"
        assert data["matches"][0]["correct"] is True


# ---------------------------------------------------------------------------
# 8. export_openapi still exports only the 7 /tools operations
# ---------------------------------------------------------------------------

class TestExportStillClean:
    def test_export_has_only_tools_operations(self):
        import importlib.util
        spec_obj = importlib.util.spec_from_file_location(
            "export_openapi", REPO_ROOT / "agent" / "export_openapi.py"
        )
        module = importlib.util.module_from_spec(spec_obj)
        spec_obj.loader.exec_module(module)
        spec = module.build_spec("https://example.trycloudflare.com")
        ids = {op["operationId"] for ops in spec["paths"].values() for op in ops.values()}
        assert ids == module.EXPECTED_TOOLS, f"Unexpected operation IDs: {ids}"
        assert not any(p.startswith("/api/") for p in spec["paths"]), "/api/ leaked into tools spec"


# ---------------------------------------------------------------------------
# 9. GET / – analyst dashboard SPA is served
# ---------------------------------------------------------------------------

class TestDashboardUI:
    def test_root_returns_200_html(self, client_with_tmpdb):
        r = client_with_tmpdb.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_root_contains_disputedesk(self, client_with_tmpdb):
        r = client_with_tmpdb.get("/")
        assert b"DisputeDesk" in r.content
