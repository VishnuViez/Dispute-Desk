"""
test_deadline_and_export.py – tests for check_deadline and the Orchestrate export.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ["DISPUTEDESK_DB"] = str(REPO_ROOT / "data" / "disputedesk.db")

LATE_CASES = {"DSP-0049", "DSP-0050", "DSP-0051"}


def _client() -> TestClient:
    import importlib
    import backend.app.db as _db_mod
    import backend.app.main as _main_mod
    importlib.reload(_db_mod)
    importlib.reload(_main_mod)
    return TestClient(_main_mod.app)


def _cases() -> list[dict]:
    with open(REPO_ROOT / "data" / "cases.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _check(client, dispute_id, code):
    return client.get(f"/tools/disputes/{dispute_id}/deadline-check", params={"reason_code": code})


def test_every_case_matches_the_answer_key():
    client = _client()
    for case in _cases():
        r = _check(client, case["dispute_id"], case["expected_reason_code"])
        assert r.status_code == 200, case["dispute_id"]
        body = r.json()
        expected_within = case["dispute_id"] not in LATE_CASES
        assert body["within_time_limits"] is expected_within, case["dispute_id"]


def test_demo_c_is_too_late():
    body = _check(_client(), "DSP-0049", "13.1").json()
    assert body["within_time_limits"] is False
    assert body["network_ok"] is False
    assert "too late" in body["summary"]


def test_too_early_case():
    body = _check(_client(), "DSP-0029", "13.1").json()
    assert body["too_early"] is True
    assert body["within_time_limits"] is True


def test_regulation_follows_card_type():
    client = _client()
    for case in _cases():
        body = _check(client, case["dispute_id"], case["expected_reason_code"]).json()
        if body["card_type"] == "credit":
            assert body["regulation"] == "Reg Z"
            assert body["bank_response_deadlines"]["acknowledge_by"]
        else:
            assert body["regulation"] == "Reg E"
            assert body["bank_response_deadlines"]["investigate_by"]


def test_unknown_dispute_and_bad_code():
    client = _client()
    assert _check(client, "DSP-9999", "13.1").status_code == 404
    assert _check(client, "DSP-0021", "99.9").status_code == 422


def _load_export_module():
    spec = importlib.util.spec_from_file_location("export_openapi", REPO_ROOT / "agent" / "export_openapi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_is_orchestrate_ready():
    module = _load_export_module()
    spec = module.build_spec("https://example.trycloudflare.com")
    assert spec["openapi"] == "3.0.3"
    assert spec["servers"] == [{"url": "https://example.trycloudflare.com"}]
    ids = {op["operationId"] for ops in spec["paths"].values() for op in ops.values()}
    assert ids == module.EXPECTED_TOOLS
    text = json.dumps(spec)
    assert '{"type": "null"}' not in text
    assert "/health" not in spec["paths"]
    try:
        from openapi_spec_validator import validate
    except ImportError:
        return
    validate(spec)
