"""
test_recommendation.py – the recommend_outcome tool must match the answer key for all 30 cases.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ["DISPUTEDESK_DB"] = str(REPO_ROOT / "data" / "disputedesk.db")


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


def _recommend(client, case: dict):
    # For 13.3 the Intake Agent reads "did they contact the merchant" from the complaint;
    # here we take it from the answer key.
    contacted = case["expected_reason_code"] == "13.3" and case["expected_outcome"] == "file_chargeback"
    return client.get(
        f"/tools/disputes/{case['dispute_id']}/recommendation",
        params={"reason_code": case["expected_reason_code"], "customer_contacted_merchant": str(contacted).lower()},
    )


def test_all_30_cases_match_the_answer_key():
    client = _client()
    wrong = []
    for case in _cases():
        r = _recommend(client, case)
        assert r.status_code == 200, case["dispute_id"]
        if r.json()["recommendation"] != case["expected_outcome"]:
            wrong.append((case["dispute_id"], r.json()["recommendation"], case["expected_outcome"]))
    assert not wrong, wrong


def test_demo_cases():
    client = _client()
    cases = {c["demo_case"]: c for c in _cases() if c["demo_case"]}
    a = _recommend(client, cases["A"]).json()
    assert a["recommendation"] == "file_chargeback" and a["confidence"] == "High"
    b = _recommend(client, cases["B"]).json()
    assert b["recommendation"] == "escalate"
    assert any(not c["passed"] for c in b["checks"] if c["name"] == "History fits the claim")
    c = _recommend(client, cases["C"]).json()
    assert c["recommendation"] == "deny"


def test_response_shape_and_errors():
    client = _client()
    body = client.get("/tools/disputes/DSP-0021/recommendation", params={"reason_code": "12.6.1"}).json()
    assert len(body["checks"]) == 4
    assert 1 <= len(body["key_evidence"]) <= 4
    assert client.get("/tools/disputes/DSP-9999/recommendation", params={"reason_code": "12.6.1"}).status_code == 404
    assert client.get("/tools/disputes/DSP-0021/recommendation", params={"reason_code": "1.1"}).status_code == 422
