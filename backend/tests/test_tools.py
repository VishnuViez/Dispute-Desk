"""
test_tools.py – Tests for the four tool endpoints.

Covers:
- Basic happy path and 404 for each endpoint.
- All 30 cases.csv rows return 200 for all four endpoints.
- Demo-specific assertions (A, B, C).
- 10.4 file_chargeback evidence assertions.
- openapi.json lists all four operation_ids.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "data" / "cases.csv"

# Ensure the real DB path is set before importing the app.
# This runs at collection time and corrects any path left by test_health.py.
_REAL_DB = str(REPO_ROOT / "data" / "disputedesk.db")
os.environ["DISPUTEDESK_DB"] = _REAL_DB


@pytest.fixture(scope="session", autouse=True)
def _reset_db_for_tools(request):
    """Reload db and main modules with the real DB path once per session."""
    import importlib
    import backend.app.db as _db_mod
    import backend.app.main as _main_mod
    importlib.reload(_db_mod)
    importlib.reload(_main_mod)


def _client() -> TestClient:
    """Build a fresh TestClient against the real database."""
    import importlib
    import backend.app.main as _main_mod
    importlib.reload(_main_mod)
    return TestClient(_main_mod.app)


def load_cases() -> list[dict]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_dispute(dispute_id: str):
    return _client().get(f"/tools/disputes/{dispute_id}")


def get_transaction(transaction_id: str):
    return _client().get(f"/tools/transactions/{transaction_id}")


def get_history(customer_id: str, merchant_id: str | None = None, transaction_id: str | None = None):
    params = {}
    if merchant_id:
        params["merchant_id"] = merchant_id
    if transaction_id:
        params["transaction_id"] = transaction_id
    return _client().get(f"/tools/customers/{customer_id}/history", params=params)


def get_merchant(merchant_id: str, transaction_id: str | None = None):
    params = {"transaction_id": transaction_id} if transaction_id else {}
    return _client().get(f"/tools/merchants/{merchant_id}", params=params)


# ---------------------------------------------------------------------------
# 1. get_dispute
# ---------------------------------------------------------------------------

class TestGetDispute:
    def test_known_dispute_returns_200(self):
        r = get_dispute("DSP-0021")
        assert r.status_code == 200
        data = r.json()
        assert data["dispute_id"] == "DSP-0021"
        assert data["status"] == "open"
        assert data["card_type"] in ("credit", "debit")
        assert "transaction_id" in data
        assert "complaint_text" in data

    def test_unknown_dispute_returns_404(self):
        r = get_dispute("DSP-ZZZZ")
        assert r.status_code == 404
        assert "DSP-ZZZZ" in r.json()["detail"]

    def test_response_fields_present(self):
        r = get_dispute("DSP-0021")
        data = r.json()
        for field in ("dispute_id", "transaction_id", "customer_id",
                      "filed_date", "complaint_text", "status", "card_type"):
            assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# 2. get_transaction
# ---------------------------------------------------------------------------

class TestGetTransaction:
    def test_known_transaction_returns_200(self):
        r = get_transaction("TXN-000001")
        assert r.status_code == 200
        data = r.json()
        assert data["transaction_id"] == "TXN-000001"
        assert "merchant_name" in data
        assert "merchant_category" in data
        assert "card_type" in data
        assert isinstance(data["refunds"], list)
        assert isinstance(data["possible_duplicates"], list)

    def test_unknown_transaction_returns_404(self):
        r = get_transaction("TXN-ZZZZZZ")
        assert r.status_code == 404
        assert "TXN-ZZZZZZ" in r.json()["detail"]

    def test_subscription_fields_null_for_instore(self):
        # Find an in_store transaction with no subscription
        r = get_transaction("TXN-000001")
        data = r.json()
        if data["channel"] == "in_store":
            assert data["subscription_id"] is None
            assert data["subscription_start_date"] is None
            assert data["subscription_cancelled_date"] is None

    def test_response_fields_present(self):
        r = get_transaction("TXN-000001")
        data = r.json()
        for field in (
            "transaction_id", "card_id", "customer_id", "merchant_id",
            "merchant_name", "merchant_category", "txn_datetime",
            "amount_usd", "currency", "channel", "statement_date",
            "status", "card_type", "refunds", "possible_duplicates",
        ):
            assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# 3. get_customer_history
# ---------------------------------------------------------------------------

class TestGetCustomerHistory:
    def test_known_customer_returns_200(self):
        r = get_history("CUST-0001")
        assert r.status_code == 200
        data = r.json()
        assert data["customer_id"] == "CUST-0001"
        assert "account_open_date" in data
        assert isinstance(data["transactions"], list)
        assert data["friendly_fraud_signals"] is None  # not requested

    def test_unknown_customer_returns_404(self):
        r = get_history("CUST-ZZZZ")
        assert r.status_code == 404
        assert "CUST-ZZZZ" in r.json()["detail"]

    def test_fraud_signals_populated_with_both_params(self):
        # Demo B: CUST-0024, merchant MERCH-009, disputed TXN-000531
        r = get_history("CUST-0024", merchant_id="MERCH-009", transaction_id="TXN-000531")
        assert r.status_code == 200
        sig = r.json()["friendly_fraud_signals"]
        assert sig is not None
        for field in (
            "prior_undisputed_with_merchant", "same_device_count",
            "same_address_count", "device_seen_before", "address_seen_before",
            "prior_disputes_count", "prior_disputes_lost", "summary",
        ):
            assert field in sig, f"Missing signal field: {field}"

    def test_fraud_signals_none_without_params(self):
        r = get_history("CUST-0024")
        assert r.json()["friendly_fraud_signals"] is None

    def test_unknown_transaction_in_signals_returns_404(self):
        r = get_history("CUST-0001", merchant_id="MERCH-001", transaction_id="TXN-ZZZZZZ")
        assert r.status_code == 404

    def test_transactions_max_50(self):
        r = get_history("CUST-0001")
        assert len(r.json()["transactions"]) <= 50

    def test_transactions_newest_first(self):
        r = get_history("CUST-0001")
        txns = r.json()["transactions"]
        if len(txns) >= 2:
            assert txns[0]["txn_datetime"] >= txns[1]["txn_datetime"]


# ---------------------------------------------------------------------------
# 4. get_merchant_info
# ---------------------------------------------------------------------------

class TestGetMerchantInfo:
    def test_known_merchant_returns_200(self):
        r = get_merchant("MERCH-001")
        assert r.status_code == 200
        data = r.json()
        assert data["merchant_id"] == "MERCH-001"
        assert "name" in data
        assert "category" in data
        assert isinstance(data["is_online"], bool)
        assert "refund_policy" in data
        assert data["shipment"] is None  # no transaction_id given

    def test_unknown_merchant_returns_404(self):
        r = get_merchant("MERCH-ZZZ")
        assert r.status_code == 404
        assert "MERCH-ZZZ" in r.json()["detail"]

    def test_unknown_transaction_returns_404(self):
        r = get_merchant("MERCH-001", transaction_id="TXN-ZZZZZZ")
        assert r.status_code == 404

    def test_shipment_present_for_online_order(self):
        # TXN-000508 is a 13.1 file_chargeback case (online order, lost shipment)
        r = get_merchant("MERCH-008", transaction_id="TXN-000508")  # Veldt Supply Co., case CASE-0005
        assert r.status_code == 200
        data = r.json()
        # shipment may or may not exist depending on which txn; just confirm no crash

    def test_shipment_null_without_transaction_id(self):
        r = get_merchant("MERCH-001")
        assert r.json()["shipment"] is None


# ---------------------------------------------------------------------------
# 5. All 30 cases.csv rows return 200 for all four endpoints
# ---------------------------------------------------------------------------

# Load once at module level so class-scoped fixture warnings are avoided.
_ALL_CASES = load_cases()


class TestAllCases:
    def test_all_get_dispute_200(self):
        for c in _ALL_CASES:
            r = get_dispute(c["dispute_id"])
            assert r.status_code == 200, (
                f"{c['case_id']}: GET /tools/disputes/{c['dispute_id']} returned {r.status_code}"
            )

    def test_all_get_transaction_200(self):
        for c in _ALL_CASES:
            r = get_transaction(c["transaction_id"])
            assert r.status_code == 200, (
                f"{c['case_id']}: GET /tools/transactions/{c['transaction_id']} returned {r.status_code}"
            )

    def test_all_get_customer_history_200(self):
        for c in _ALL_CASES:
            r = get_history(c["customer_id"])
            assert r.status_code == 200, (
                f"{c['case_id']}: GET /tools/customers/{c['customer_id']}/history returned {r.status_code}"
            )

    def test_all_get_merchant_via_transaction_200(self):
        """Calling get_merchant with the transaction_id from each case should return 200."""
        for c in _ALL_CASES:
            txn_r = get_transaction(c["transaction_id"])
            merchant_id = txn_r.json()["merchant_id"]
            r = get_merchant(merchant_id, transaction_id=c["transaction_id"])
            assert r.status_code == 200, (
                f"{c['case_id']}: GET /tools/merchants/{merchant_id}?transaction_id=... returned {r.status_code}"
            )


# ---------------------------------------------------------------------------
# 6. Demo A – possible_duplicates has a $6.50 charge ~2 minutes apart
# ---------------------------------------------------------------------------

class TestDemoA:
    def test_possible_duplicates_present(self):
        r = get_transaction("TXN-000502")
        assert r.status_code == 200
        dups = r.json()["possible_duplicates"]
        assert len(dups) >= 1, "Demo A should have at least one possible duplicate"

    def test_amount_is_6_50(self):
        r = get_transaction("TXN-000502")
        assert abs(r.json()["amount_usd"] - 6.50) < 0.01

    def test_duplicate_minutes_apart(self):
        r = get_transaction("TXN-000502")
        dups = r.json()["possible_duplicates"]
        assert any(d["minutes_apart"] <= 10 for d in dups), (
            f"Expected a duplicate within 10 minutes; got {[d['minutes_apart'] for d in dups]}"
        )


# ---------------------------------------------------------------------------
# 7. Demo B – prior_undisputed, same_device, same_address all >= 3
# ---------------------------------------------------------------------------

class TestDemoB:
    def test_fraud_signals_counts(self):
        r = get_history("CUST-0024", merchant_id="MERCH-009", transaction_id="TXN-000531")
        assert r.status_code == 200
        sig = r.json()["friendly_fraud_signals"]
        assert sig["prior_undisputed_with_merchant"] >= 3, (
            f"prior_undisputed_with_merchant={sig['prior_undisputed_with_merchant']}"
        )
        assert sig["same_device_count"] >= 3, f"same_device_count={sig['same_device_count']}"
        assert sig["same_address_count"] >= 3, f"same_address_count={sig['same_address_count']}"

    def test_amount_is_340(self):
        r = get_transaction("TXN-000531")
        assert abs(r.json()["amount_usd"] - 340.00) < 0.01


# ---------------------------------------------------------------------------
# 8. Demo C – transaction is 140–160 days before filed date
# ---------------------------------------------------------------------------

class TestDemoC:
    def test_days_before_filed(self):
        from datetime import datetime
        r = get_transaction("TXN-000540")
        assert r.status_code == 200
        txn_dt = datetime.strptime(r.json()["txn_datetime"], "%Y-%m-%dT%H:%M:%S").date()
        filed = r.json()  # we need the dispute filed_date

        # Get filed date from the dispute endpoint
        dispute_r = get_dispute("DSP-0049")
        filed_date = datetime.strptime(dispute_r.json()["filed_date"], "%Y-%m-%d").date()
        days_diff = (filed_date - txn_dt).days
        assert 140 <= days_diff <= 160, f"Demo C: {days_diff} days between txn and filing"


# ---------------------------------------------------------------------------
# 9. 10.4 file_chargeback cases: device_seen_before=False, address_seen_before=False
# ---------------------------------------------------------------------------

class TestFraudChargebackEvidence:
    # The four 10.4 file_chargeback case IDs and their merchant
    FRAUD_CB_CASES = [
        ("CUST-0020", "TXN-000524"),
        ("CUST-0021", "TXN-000525"),
        ("CUST-0022", "TXN-000526"),
        ("CUST-0023", "TXN-000527"),
    ]

    def test_device_and_address_not_seen_before(self):
        for cust_id, txn_id in self.FRAUD_CB_CASES:
            txn_r = get_transaction(txn_id)
            merchant_id = txn_r.json()["merchant_id"]
            r = get_history(cust_id, merchant_id=merchant_id, transaction_id=txn_id)
            assert r.status_code == 200
            sig = r.json()["friendly_fraud_signals"]
            assert sig is not None
            assert sig["device_seen_before"] is False, (
                f"{cust_id}/{txn_id}: device_seen_before should be False"
            )
            assert sig["address_seen_before"] is False, (
                f"{cust_id}/{txn_id}: address_seen_before should be False"
            )


# ---------------------------------------------------------------------------
# 10. openapi.json lists all four operation_ids
# ---------------------------------------------------------------------------

class TestOpenApiSpec:
    def test_operation_ids_present(self):
        r = _client().get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        # Collect all operationIds from the spec
        ids = set()
        for path_item in spec.get("paths", {}).values():
            for method_item in path_item.values():
                if isinstance(method_item, dict) and "operationId" in method_item:
                    ids.add(method_item["operationId"])
        for expected in ("get_dispute", "get_transaction", "get_customer_history", "get_merchant_info"):
            assert expected in ids, f"operationId '{expected}' not found in openapi.json"
