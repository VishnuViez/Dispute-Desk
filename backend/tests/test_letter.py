"""
test_letter.py – Tests for POST /tools/disputes/{dispute_id}/letter-draft
and the matching dashboard plumbing (/api/activity stage + /api/cases detail).
"""

from __future__ import annotations

import importlib
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ["DISPUTEDESK_DB"] = str(REPO_ROOT / "data" / "disputedesk.db")


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
def client_tmp(tmp_path):
    db_path = str(tmp_path / "activity.db")
    c = _client(activity_path=db_path)
    yield c
    os.environ.pop("ACTIVITY_DB", None)


# ---------------------------------------------------------------------------
# Happy-path: file_chargeback with chargeback_summary
# ---------------------------------------------------------------------------

class TestRecordLetterDraft:
    def test_returns_200(self, client_tmp):
        r = client_tmp.post(
            "/tools/disputes/DSP-0021/letter-draft",
            json={
                "outcome": "file_chargeback",
                "letter_text": "Dear Cardholder, we have opened a dispute. Card Disputes Team",
                "chargeback_summary": "• TXN-000502 $6.50 duplicate",
            },
        )
        assert r.status_code == 200

    def test_response_shape(self, client_tmp):
        r = client_tmp.post(
            "/tools/disputes/DSP-0021/letter-draft",
            json={
                "outcome": "file_chargeback",
                "letter_text": "Dear Cardholder, we have opened a dispute. Card Disputes Team",
            },
        )
        body = r.json()
        assert body["dispute_id"] == "DSP-0021"
        assert body["outcome"] == "file_chargeback"
        assert "id" in body
        assert "ts" in body
        assert "message" in body

    def test_deny_without_summary(self, client_tmp):
        r = client_tmp.post(
            "/tools/disputes/DSP-0033/letter-draft",
            json={
                "outcome": "deny",
                "letter_text": "Dear Cardholder, the charge was made before cancellation. Card Disputes Team",
            },
        )
        assert r.status_code == 200
        assert r.json()["outcome"] == "deny"

    def test_unknown_dispute_returns_404(self, client_tmp):
        r = client_tmp.post(
            "/tools/disputes/DSP-9999/letter-draft",
            json={
                "outcome": "deny",
                "letter_text": "Dear Cardholder, text. Card Disputes Team",
            },
        )
        assert r.status_code == 404

    def test_missing_required_field_returns_422(self, client_tmp):
        # letter_text is required
        r = client_tmp.post(
            "/tools/disputes/DSP-0021/letter-draft",
            json={"outcome": "file_chargeback"},
        )
        assert r.status_code == 422

    def test_missing_outcome_returns_422(self, client_tmp):
        r = client_tmp.post(
            "/tools/disputes/DSP-0021/letter-draft",
            json={"letter_text": "Dear Cardholder, text. Card Disputes Team"},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Activity stage mapping
# ---------------------------------------------------------------------------

class TestLetterActivityStage:
    def test_record_letter_draft_stage_is_letter(self, client_tmp):
        client_tmp.post(
            "/tools/disputes/DSP-0021/letter-draft",
            json={
                "outcome": "file_chargeback",
                "letter_text": "Dear Cardholder, we opened a dispute. Card Disputes Team",
            },
        )
        rows = client_tmp.get("/api/activity").json()
        letter_rows = [r for r in rows if r["tool"] == "record_letter_draft"]
        assert letter_rows, "No record_letter_draft row in activity log"
        assert letter_rows[-1]["stage"] == "Letter"


# ---------------------------------------------------------------------------
# Case detail includes letter_draft
# ---------------------------------------------------------------------------

class TestCaseDetailLetterDraft:
    def test_letter_draft_null_before_posting(self, client_tmp):
        d = client_tmp.get("/api/cases/DSP-0021").json()
        assert d["letter_draft"] is None

    def test_letter_draft_present_after_posting(self, client_tmp):
        client_tmp.post(
            "/tools/disputes/DSP-0021/letter-draft",
            json={
                "outcome": "file_chargeback",
                "letter_text": "Dear Cardholder, we opened a dispute. Card Disputes Team",
                "chargeback_summary": "• $6.50 duplicate charge",
            },
        )
        d = client_tmp.get("/api/cases/DSP-0021").json()
        ld = d["letter_draft"]
        assert ld is not None
        assert ld["dispute_id"] == "DSP-0021"
        assert ld["outcome"] == "file_chargeback"
        assert "Dear Cardholder" in ld["letter_text"]
        assert ld["chargeback_summary"] is not None

    def test_latest_letter_returned_on_multiple_drafts(self, client_tmp):
        for i in range(3):
            client_tmp.post(
                "/tools/disputes/DSP-0021/letter-draft",
                json={
                    "outcome": "file_chargeback",
                    "letter_text": f"Draft version {i}",
                },
            )
        d = client_tmp.get("/api/cases/DSP-0021").json()
        assert "Draft version 2" in d["letter_draft"]["letter_text"]


# ---------------------------------------------------------------------------
# Export still counts all 7 tools
# ---------------------------------------------------------------------------

class TestExportNowHasSevenTools:
    def test_export_has_seven_operations(self, client_tmp):
        import backend.app.main as _main_mod
        spec = _main_mod.app.openapi()
        tool_ops = [
            op
            for path, methods in spec["paths"].items()
            if path.startswith("/tools/")
            for op in methods.values()
        ]
        op_ids = {op["operationId"] for op in tool_ops}
        assert "record_letter_draft" in op_ids
        assert len(op_ids) == 7
