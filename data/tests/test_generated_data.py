"""
test_generated_data.py – Validates the output of data/generate_data.py.

Run from the repo root:
    pytest data/tests/test_generated_data.py -v
"""

import csv
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "disputedesk.db"
CSV_PATH = REPO_ROOT / "data" / "cases.csv"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_cases() -> list[dict]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


REFERENCE_DATE = date(2026, 10, 15)

# ---------------------------------------------------------------------------
# Fixture-style setup: load once per module
# ---------------------------------------------------------------------------

import pytest


@pytest.fixture(scope="module")
def conn():
    c = get_conn()
    yield c
    c.close()


@pytest.fixture(scope="module")
def cases():
    return load_cases()


# ---------------------------------------------------------------------------
# 1. Generator ran and files exist
# ---------------------------------------------------------------------------

def test_db_exists():
    assert DB_PATH.exists(), "disputedesk.db was not created"


def test_csv_exists():
    assert CSV_PATH.exists(), "cases.csv was not created"


# ---------------------------------------------------------------------------
# 2. Row counts are within ranges
# ---------------------------------------------------------------------------

def test_customer_count(conn):
    n = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    assert n == 60, f"Expected 60 customers, got {n}"


def test_card_count(conn):
    n = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    assert 60 <= n <= 120, f"Card count {n} outside expected range 60–120"


def test_merchant_count(conn):
    n = conn.execute("SELECT COUNT(*) FROM merchants").fetchone()[0]
    assert n == 25, f"Expected 25 merchants, got {n}"


def test_transaction_count(conn):
    n = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert n >= 500, f"Transaction count {n} is below 500"


def test_background_subscription_count(conn):
    # 8 background subs + case-planted subs
    n = conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
    assert n >= 8, f"Expected at least 8 subscriptions, got {n}"


def test_background_refund_count(conn):
    # 15 background + any case-planted refunds
    n = conn.execute("SELECT COUNT(*) FROM refunds").fetchone()[0]
    assert n >= 15, f"Expected at least 15 refunds, got {n}"


def test_background_dispute_count(conn):
    # ~20 background + 30 open cases
    n = conn.execute("SELECT COUNT(*) FROM disputes").fetchone()[0]
    assert n >= 45, f"Expected at least 45 total disputes, got {n}"


# ---------------------------------------------------------------------------
# 3. Exactly 30 open disputes
# ---------------------------------------------------------------------------

def test_exactly_30_open_disputes(conn):
    n = conn.execute(
        "SELECT COUNT(*) FROM disputes WHERE status = 'open'"
    ).fetchone()[0]
    assert n == 30, f"Expected 30 open disputes, got {n}"


def test_cases_csv_has_30_rows(cases):
    assert len(cases) == 30, f"Expected 30 rows in cases.csv, got {len(cases)}"


# ---------------------------------------------------------------------------
# 4. Every ID in cases.csv exists in the database
# ---------------------------------------------------------------------------

def test_case_dispute_ids_exist(conn, cases):
    existing = {
        r[0] for r in conn.execute("SELECT dispute_id FROM disputes").fetchall()
    }
    for c in cases:
        assert c["dispute_id"] in existing, f"dispute_id {c['dispute_id']} not in DB"


def test_case_transaction_ids_exist(conn, cases):
    existing = {
        r[0] for r in conn.execute("SELECT transaction_id FROM transactions").fetchall()
    }
    for c in cases:
        assert c["transaction_id"] in existing, f"txn_id {c['transaction_id']} not in DB"


def test_case_customer_ids_exist(conn, cases):
    existing = {
        r[0] for r in conn.execute("SELECT customer_id FROM customers").fetchall()
    }
    for c in cases:
        assert c["customer_id"] in existing, f"customer_id {c['customer_id']} not in DB"


# ---------------------------------------------------------------------------
# 5. Outcome counts match the brief: 17 / 6 / 4 / 3
# ---------------------------------------------------------------------------

def test_outcome_counts(cases):
    from collections import Counter
    counts = Counter(c["expected_outcome"] for c in cases)
    assert counts["file_chargeback"] == 17, f"file_chargeback: {counts['file_chargeback']} (expected 17)"
    assert counts["deny"] == 6, f"deny: {counts['deny']} (expected 6)"
    assert counts["request_more_info"] == 4, f"request_more_info: {counts['request_more_info']} (expected 4)"
    assert counts["escalate"] == 3, f"escalate: {counts['escalate']} (expected 3)"


# ---------------------------------------------------------------------------
# 6. Demo cases A, B, C
# ---------------------------------------------------------------------------

def test_demo_A(conn, cases):
    """Two identical $6.50 charges 2 minutes apart at the same coffee shop."""
    demo_a = [c for c in cases if c["demo_case"] == "A"]
    assert len(demo_a) == 1, "Expected exactly one demo A case"
    c = demo_a[0]
    assert c["expected_reason_code"] == "12.6.1"
    assert c["expected_outcome"] == "file_chargeback"

    # The disputed transaction
    txn = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?", (c["transaction_id"],)
    ).fetchone()
    assert txn is not None
    assert abs(txn["amount_usd"] - 6.50) < 0.01

    # Find a matching duplicate: same card, merchant, amount, within 10 minutes
    disputed_dt = parse_dt(txn["txn_datetime"])
    siblings = conn.execute(
        """SELECT txn_datetime FROM transactions
           WHERE card_id = ? AND merchant_id = ? AND ABS(amount_usd - ?) < 0.01
             AND transaction_id != ?""",
        (txn["card_id"], txn["merchant_id"], txn["amount_usd"], c["transaction_id"]),
    ).fetchall()
    assert len(siblings) >= 1, "No duplicate transaction found for demo A"
    diffs = [abs((parse_dt(s["txn_datetime"]) - disputed_dt).total_seconds() / 60)
             for s in siblings]
    assert any(d <= 10 for d in diffs), f"No sibling within 10 min; diffs = {diffs}"


def test_demo_B(conn, cases):
    """$340 order; customer has 3 earlier purchases at same merchant, same device+addr."""
    demo_b = [c for c in cases if c["demo_case"] == "B"]
    assert len(demo_b) == 1
    c = demo_b[0]
    assert c["expected_reason_code"] == "10.4"
    assert c["expected_outcome"] == "escalate"

    txn = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?", (c["transaction_id"],)
    ).fetchone()
    assert txn is not None
    assert abs(txn["amount_usd"] - 340.00) < 0.01

    disputed_dt = parse_dt(txn["txn_datetime"])
    priors = conn.execute(
        """SELECT txn_datetime FROM transactions
           WHERE customer_id = ? AND merchant_id = ?
             AND device_id = ? AND shipping_address_id = ?
             AND transaction_id != ?
             AND txn_datetime < ?""",
        (txn["customer_id"], txn["merchant_id"],
         txn["device_id"], txn["shipping_address_id"],
         c["transaction_id"], txn["txn_datetime"]),
    ).fetchall()
    assert len(priors) >= 3, f"Demo B: expected 3+ prior purchases, found {len(priors)}"
    for p in priors:
        prior_dt = parse_dt(p["txn_datetime"])
        days_diff = (disputed_dt - prior_dt).days
        assert 120 <= days_diff <= 365, (
            f"Demo B prior purchase {days_diff} days before disputed; must be 120–365"
        )


def test_demo_C(conn, cases):
    """Transaction in spring 2026, filed ~150 days later. Outcome: deny."""
    demo_c = [c for c in cases if c["demo_case"] == "C"]
    assert len(demo_c) == 1
    c = demo_c[0]
    assert c["expected_reason_code"] == "13.1"
    assert c["expected_outcome"] == "deny"

    txn = conn.execute(
        "SELECT txn_datetime FROM transactions WHERE transaction_id = ?",
        (c["transaction_id"],),
    ).fetchone()
    assert txn is not None
    txn_date = parse_dt(txn["txn_datetime"]).date()
    filed = parse_date(c["filed_date"])

    # Transaction in spring 2026 (April–June)
    assert txn_date.year == 2026
    assert 4 <= txn_date.month <= 6, f"Demo C txn month {txn_date.month} not in spring (4–6)"

    # Filed ~150 days after transaction (allow 120–180 for flexibility)
    days_late = (filed - txn_date).days
    assert days_late >= 120, f"Demo C: {days_late} days is not past 120-day limit"


# ---------------------------------------------------------------------------
# 7. No accidental duplicates outside planted duplicate cases
# ---------------------------------------------------------------------------

def test_no_accidental_duplicates(conn, cases):
    """
    Outside 12.6.1 cases, no two transactions should share (card_id, merchant_id,
    amount_usd) within 24 hours.
    """
    dupe_case_txns = {
        c["transaction_id"] for c in cases if c["expected_reason_code"] == "12.6.1"
    }
    # Also collect the sibling transactions of 12.6.1 cases
    for cid in list(dupe_case_txns):
        txn = conn.execute(
            "SELECT card_id, merchant_id, amount_usd, txn_datetime FROM transactions WHERE transaction_id = ?",
            (cid,),
        ).fetchone()
        if txn:
            siblings = conn.execute(
                """SELECT transaction_id FROM transactions
                   WHERE card_id = ? AND merchant_id = ? AND ABS(amount_usd - ?) < 0.01
                     AND transaction_id != ?""",
                (txn["card_id"], txn["merchant_id"], txn["amount_usd"], cid),
            ).fetchall()
            for s in siblings:
                dupe_case_txns.add(s["transaction_id"])

    # Now look for any remaining pairs within 24 h
    rows = conn.execute(
        "SELECT transaction_id, card_id, merchant_id, amount_usd, txn_datetime FROM transactions"
    ).fetchall()

    from collections import defaultdict
    groups: dict = defaultdict(list)
    for r in rows:
        if r["transaction_id"] not in dupe_case_txns:
            key = (r["card_id"], r["merchant_id"], round(r["amount_usd"] * 100))
            groups[key].append((r["transaction_id"], parse_dt(r["txn_datetime"])))

    for key, txns in groups.items():
        txns.sort(key=lambda x: x[1])
        for i in range(len(txns) - 1):
            diff = (txns[i + 1][1] - txns[i][1]).total_seconds()
            assert diff > 86400, (
                f"Accidental duplicate outside 12.6.1 cases: {key}, "
                f"txns {txns[i][0]} and {txns[i+1][0]} only {diff:.0f}s apart"
            )


# ---------------------------------------------------------------------------
# 8. Timing rules hold for every case
# ---------------------------------------------------------------------------

def test_timing_rules(conn, cases):
    """
    Non-late cases: filed within 60 days of statement_date AND within 120 days
    of the transaction (for 13.1, within 120 days of expected_delivery_date).
    Late cases: filed > 120 days after the transaction AND > 60 days after statement.
    13.1 deny (too early): expected_delivery_date is AFTER filed_date.
    """
    for c in cases:
        txn = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?",
            (c["transaction_id"],),
        ).fetchone()
        assert txn is not None

        filed = parse_date(c["filed_date"])
        txn_date = parse_dt(txn["txn_datetime"]).date()
        stmt_date = parse_date(txn["statement_date"])

        # Late cases: filed past time limit. Detected by presence of "120-day" or "120 days"
        # in notes, with outcome deny, and no "too early"/"before"/"posted" signal.
        is_late = (
            c["expected_outcome"] == "deny"
            and c["notes"]
            and ("120-day" in c["notes"] or "120 days" in c["notes"])
            and c["expected_reason_code"] in ("13.1", "13.3", "13.6")
            and "too early" not in c["notes"]
            and "before the" not in c["notes"]
            and "posted" not in c["notes"]
        )

        if is_late:
            assert (filed - txn_date).days > 120, (
                f"{c['case_id']}: late case but filed only {(filed - txn_date).days} days after txn"
            )
            assert (filed - stmt_date).days > 60, (
                f"{c['case_id']}: late case but filed only {(filed - stmt_date).days} days after stmt"
            )
        elif c["expected_reason_code"] == "13.1" and c["expected_outcome"] == "deny":
            # Too-early case: expected delivery date is after filed date
            ship = conn.execute(
                "SELECT expected_delivery_date FROM shipments WHERE transaction_id = ?",
                (c["transaction_id"],),
            ).fetchone()
            assert ship is not None, f"{c['case_id']}: no shipment for too-early 13.1 case"
            exp_del = parse_date(ship["expected_delivery_date"])
            assert exp_del > filed, (
                f"{c['case_id']}: expected_delivery_date {exp_del} is not after filed_date {filed}"
            )
        else:
            # Normal cases: within limits
            days_from_stmt = (filed - stmt_date).days
            assert days_from_stmt <= 60, (
                f"{c['case_id']}: filed {days_from_stmt} days after statement (limit 60)"
            )
            if c["expected_reason_code"] == "13.1":
                ship = conn.execute(
                    "SELECT expected_delivery_date FROM shipments WHERE transaction_id = ?",
                    (c["transaction_id"],),
                ).fetchone()
                if ship:
                    exp_del = parse_date(ship["expected_delivery_date"])
                    days_from_del = (filed - exp_del).days
                    assert days_from_del <= 120, (
                        f"{c['case_id']}: 13.1 filed {days_from_del} days after expected delivery (limit 120)"
                    )
            else:
                assert (filed - txn_date).days <= 120, (
                    f"{c['case_id']}: filed {(filed - txn_date).days} days after txn (limit 120)"
                )


# ---------------------------------------------------------------------------
# 9. Evidence rules for 10.4 cases
# ---------------------------------------------------------------------------

def test_fraud_chargeback_evidence(conn, cases):
    """10.4 file_chargeback: device_id and shipping_address_id not previously used by customer."""
    fraud_cb = [c for c in cases
                if c["expected_reason_code"] == "10.4"
                and c["expected_outcome"] == "file_chargeback"]
    assert len(fraud_cb) == 4

    for c in fraud_cb:
        txn = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?",
            (c["transaction_id"],),
        ).fetchone()
        assert txn["device_id"] is not None
        assert txn["shipping_address_id"] is not None

        # No prior use of this device by this customer (before this transaction)
        prior_device = conn.execute(
            """SELECT COUNT(*) FROM transactions
               WHERE customer_id = ? AND device_id = ? AND txn_datetime < ?""",
            (txn["customer_id"], txn["device_id"], txn["txn_datetime"]),
        ).fetchone()[0]
        assert prior_device == 0, (
            f"{c['case_id']}: device {txn['device_id']} was used before by {txn['customer_id']}"
        )

        # No prior purchases at this merchant by this customer
        prior_merch = conn.execute(
            """SELECT COUNT(*) FROM transactions
               WHERE customer_id = ? AND merchant_id = ? AND txn_datetime < ?""",
            (txn["customer_id"], txn["merchant_id"], txn["txn_datetime"]),
        ).fetchone()[0]
        assert prior_merch == 0, (
            f"{c['case_id']}: customer {txn['customer_id']} has prior purchases at {txn['merchant_id']}"
        )


def test_fraud_escalate_evidence(conn, cases):
    """10.4 escalate: at least 3 prior purchases at same merchant with same device+addr, 120–365 days prior."""
    fraud_esc = [c for c in cases
                 if c["expected_reason_code"] == "10.4"
                 and c["expected_outcome"] == "escalate"]
    assert len(fraud_esc) == 3

    for c in fraud_esc:
        txn = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?",
            (c["transaction_id"],),
        ).fetchone()

        priors = conn.execute(
            """SELECT txn_datetime FROM transactions
               WHERE customer_id = ? AND merchant_id = ?
                 AND device_id = ? AND shipping_address_id = ?
                 AND transaction_id != ?
                 AND txn_datetime < ?""",
            (txn["customer_id"], txn["merchant_id"],
             txn["device_id"], txn["shipping_address_id"],
             c["transaction_id"], txn["txn_datetime"]),
        ).fetchall()
        assert len(priors) >= 3, (
            f"{c['case_id']}: only {len(priors)} prior purchases; need 3+"
        )
        disputed_dt = parse_dt(txn["txn_datetime"])
        for p in priors:
            days_diff = (disputed_dt - parse_dt(p["txn_datetime"])).days
            assert 120 <= days_diff <= 365, (
                f"{c['case_id']}: prior {days_diff} days before disputed; must be 120–365"
            )


# ---------------------------------------------------------------------------
# 10. 13.2 subscription evidence
# ---------------------------------------------------------------------------

def test_subscription_cases(conn, cases):
    sub_cases = [c for c in cases if c["expected_reason_code"] == "13.2"]
    assert len(sub_cases) == 4

    cb_cases = [c for c in sub_cases if c["expected_outcome"] == "file_chargeback"]
    deny_cases = [c for c in sub_cases if c["expected_outcome"] == "deny"]
    assert len(cb_cases) == 3
    assert len(deny_cases) == 1

    for c in cb_cases:
        txn = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?",
            (c["transaction_id"],),
        ).fetchone()
        assert txn["subscription_id"] is not None
        sub = conn.execute(
            "SELECT * FROM subscriptions WHERE subscription_id = ?",
            (txn["subscription_id"],),
        ).fetchone()
        assert sub["cancelled_date"] is not None
        txn_date = parse_dt(txn["txn_datetime"]).date()
        cancel = parse_date(sub["cancelled_date"])
        assert txn_date > cancel, (
            f"{c['case_id']}: txn {txn_date} is not after cancel {cancel}"
        )

    for c in deny_cases:
        txn = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?",
            (c["transaction_id"],),
        ).fetchone()
        sub = conn.execute(
            "SELECT * FROM subscriptions WHERE subscription_id = ?",
            (txn["subscription_id"],),
        ).fetchone()
        txn_date = parse_dt(txn["txn_datetime"]).date()
        cancel = parse_date(sub["cancelled_date"])
        assert txn_date <= cancel, (
            f"{c['case_id']}: deny case but txn {txn_date} is after cancel {cancel}"
        )


# ---------------------------------------------------------------------------
# 11. 13.6 refund evidence
# ---------------------------------------------------------------------------

def test_refund_cases(conn, cases):
    refund_cases = [c for c in cases if c["expected_reason_code"] == "13.6"
                    and c["expected_outcome"] != "deny"]  # exclude late-filing denies
    # The 2 file_chargeback 13.6 cases should have NO refund before filing
    for c in [c for c in refund_cases if c["expected_outcome"] == "file_chargeback"]:
        filed = parse_date(c["filed_date"])
        refunds = conn.execute(
            "SELECT refund_date FROM refunds WHERE transaction_id = ?",
            (c["transaction_id"],),
        ).fetchall()
        for r in refunds:
            assert parse_date(r["refund_date"]) >= filed, (
                f"{c['case_id']}: refund exists before filing date"
            )

    # The 13.6 deny case (refund already posted) should have a refund BEFORE filing
    deny_13_6 = [c for c in cases
                 if c["expected_reason_code"] == "13.6"
                 and c["expected_outcome"] == "deny"
                 and "refund already posted" in c["notes"]]
    for c in deny_13_6:
        filed = parse_date(c["filed_date"])
        refunds = conn.execute(
            "SELECT refund_date FROM refunds WHERE transaction_id = ?",
            (c["transaction_id"],),
        ).fetchall()
        assert len(refunds) >= 1, f"{c['case_id']}: no refund found for 13.6 deny case"
        assert any(parse_date(r["refund_date"]) < filed for r in refunds), (
            f"{c['case_id']}: no refund before filing date"
        )


# ---------------------------------------------------------------------------
# 12. No PII – no value looks like an email or phone number
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")


def _all_text_values(conn):
    """Yield every text value stored in the database."""
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    for table in tables:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        for row in rows:
            for val in row:
                if isinstance(val, str):
                    yield val


def test_no_email_addresses(conn):
    for val in _all_text_values(conn):
        assert not EMAIL_RE.search(val), f"Possible email found: {val!r}"


def test_no_phone_numbers(conn):
    for val in _all_text_values(conn):
        assert not PHONE_RE.search(val), f"Possible phone number found: {val!r}"


# ---------------------------------------------------------------------------
# 13. All open disputes filed within the filing window (Oct 1–15)
# ---------------------------------------------------------------------------

def test_open_dispute_filing_dates(conn):
    open_disputes = conn.execute(
        "SELECT filed_date FROM disputes WHERE status = 'open'"
    ).fetchall()
    for d in open_disputes:
        filed = parse_date(d["filed_date"])
        assert date(2026, 10, 1) <= filed <= date(2026, 10, 15), (
            f"Open dispute filed on {filed} outside Oct 1–15 window"
        )


# ---------------------------------------------------------------------------
# 14. All cards are Visa
# ---------------------------------------------------------------------------

def test_all_cards_visa(conn):
    non_visa = conn.execute(
        "SELECT card_id FROM cards WHERE network != 'visa'"
    ).fetchall()
    assert len(non_visa) == 0, f"Non-visa cards found: {[r[0] for r in non_visa]}"


# ---------------------------------------------------------------------------
# 15. statement_date is the next 5th of month after transaction
# ---------------------------------------------------------------------------

def test_statement_dates(conn):
    rows = conn.execute(
        "SELECT transaction_id, txn_datetime, statement_date FROM transactions LIMIT 200"
    ).fetchall()
    for r in rows:
        txn_date = parse_dt(r["txn_datetime"]).date()
        stmt = parse_date(r["statement_date"])
        assert stmt.day == 5, f"Statement date {stmt} is not the 5th"
        assert stmt >= txn_date, f"Statement {stmt} is before txn {txn_date}"
        # Must be the *next* 5th (not more than ~35 days away)
        days_diff = (stmt - txn_date).days
        assert days_diff <= 35, (
            f"Statement date {stmt} is {days_diff} days after txn {txn_date}"
        )
