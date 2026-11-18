"""
routers/api.py – Analyst dashboard API (prefix /api).

These endpoints are NOT under /tools so watsonx Orchestrate never sees them.
They read from both the read-only data DB and the writable activity DB.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.activity_db import get_activity_db
from backend.app.db import get_db

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[3]
CASES_CSV = REPO_ROOT / "data" / "cases.csv"

# The 120-day network filing limit used to compute "days to deadline".
NETWORK_DAYS = 120

# Stage labels for each operation_id used in /api/activity
_STAGE = {
    "get_dispute": "Intake",
    "get_transaction": "Intake",
    "get_customer_history": "Evidence",
    "get_merchant_info": "Evidence",
    "check_deadline": "Compliance",
    "recommend_outcome": "Decision",
    "record_letter_draft": "Letter",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_db(db: sqlite3.Connection | None) -> sqlite3.Connection:
    if db is None:
        raise HTTPException(status_code=503, detail="Data database is not available.")
    return db


def _days_to_deadline(filed_date: str, txn_date: str) -> int:
    """Days remaining until the 120-day network deadline from the transaction date."""
    filed = date.fromisoformat(filed_date)
    txn = date.fromisoformat(txn_date[:10])
    deadline = txn + timedelta(days=NETWORK_DAYS)
    return (deadline - filed).days


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class StatsResponse(BaseModel):
    open_disputes: int = Field(description="Number of disputes with status 'open'.")
    by_card_type: dict[str, int] = Field(description="Count of open disputes by card type (credit/debit).")
    by_recommendation: dict[str, int] = Field(
        description="Count by agent recommendation, including 'not_investigated' for cases the agent has not assessed yet."
    )
    by_reason_code: dict[str, int] = Field(
        description="Count by Visa reason code saved from the last recommendation run, plus 'not_investigated'."
    )
    near_deadline: int = Field(
        description="Number of open disputes that are within 14 days of the 120-day card network deadline."
    )


class CaseSummary(BaseModel):
    dispute_id: str
    filed_date: str
    customer_id: str
    merchant_name: str
    amount_usd: float
    card_type: str
    days_to_deadline: int = Field(description="Days until the 120-day network deadline (may be negative if past).")
    recommendation: str = Field(description="Latest agent recommendation, or 'not_investigated'.")
    confidence: str = Field(description="High/Medium/Low from the last recommendation, or '' if not investigated.")


class CasesResponse(BaseModel):
    total: int
    cases: list[CaseSummary]


class DecisionIn(BaseModel):
    decision: str = Field(description="One of: approve, edit, override.")
    final_outcome: str = Field(description="The outcome the analyst chose.")
    reason: Optional[str] = Field(default=None, description="Required for 'edit' and 'override'.")
    analyst: str = Field(description="Name or ID of the analyst making the decision.")


class DecisionOut(BaseModel):
    id: int
    ts: str
    dispute_id: str
    decision: str
    final_outcome: str
    reason: Optional[str]
    analyst: str


class ToolCallRow(BaseModel):
    id: int
    ts: str
    tool: str
    stage: str
    dispute_id: Optional[str]
    transaction_id: Optional[str]
    status_code: Optional[int]
    duration_ms: Optional[float]


class AuditRow(BaseModel):
    ts: str
    type: str = Field(description="'tool_call' or 'decision'.")
    tool: Optional[str] = None
    stage: Optional[str] = None
    dispute_id: Optional[str] = None
    decision: Optional[str] = None
    analyst: Optional[str] = None
    detail: Optional[str] = None


class EvalMatch(BaseModel):
    dispute_id: str
    expected: str
    actual: str
    correct: bool


class EvaluationResponse(BaseModel):
    total_cases: int
    investigated: int
    correct: int
    accuracy: float = Field(description="Fraction of investigated cases where recommendation matches the answer key.")
    matches: list[EvalMatch]


# ---------------------------------------------------------------------------
# 1. GET /api/stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=StatsResponse, operation_id="api_stats",
            summary="Aggregate statistics for the analyst dashboard.")
def get_stats(
    db: sqlite3.Connection | None = Depends(get_db),
) -> StatsResponse:
    conn = _require_db(db)
    aconn = get_activity_db()
    try:
        # Open disputes
        open_rows = conn.execute(
            """SELECT d.dispute_id, d.filed_date, d.customer_id,
                      t.txn_datetime, c.card_type
               FROM disputes d
               JOIN transactions t ON t.transaction_id = d.transaction_id
               JOIN cards c ON c.card_id = t.card_id
               WHERE d.status = 'open'"""
        ).fetchall()

        total_open = len(open_rows)

        by_card: dict[str, int] = {}
        near = 0
        ids = [r["dispute_id"] for r in open_rows]
        for r in open_rows:
            ct = r["card_type"]
            by_card[ct] = by_card.get(ct, 0) + 1
            dtd = _days_to_deadline(r["filed_date"], r["txn_datetime"])
            if dtd <= 14:
                near += 1

        # Recommendations
        recs = {
            row["dispute_id"]: row["recommendation"]
            for row in aconn.execute("SELECT dispute_id, recommendation FROM recommendations").fetchall()
        }
        by_rec: dict[str, int] = {}
        by_code: dict[str, int] = {}
        recs_with_code = {
            row["dispute_id"]: row["reason_code"]
            for row in aconn.execute("SELECT dispute_id, reason_code FROM recommendations").fetchall()
        }
        for did in ids:
            rec = recs.get(did, "not_investigated")
            by_rec[rec] = by_rec.get(rec, 0) + 1
            code = recs_with_code.get(did, "not_investigated")
            by_code[code] = by_code.get(code, 0) + 1

        return StatsResponse(
            open_disputes=total_open,
            by_card_type=by_card,
            by_recommendation=by_rec,
            by_reason_code=by_code,
            near_deadline=near,
        )
    finally:
        aconn.close()


# ---------------------------------------------------------------------------
# 2. GET /api/cases
# ---------------------------------------------------------------------------

@router.get("/cases", response_model=CasesResponse, operation_id="api_cases",
            summary="List open disputes with optional filters and sorting.")
def list_cases(
    status: Optional[str] = Query(default=None, description="Filter by dispute status."),
    card_type: Optional[str] = Query(default=None, description="Filter by card type (credit/debit)."),
    reason_code: Optional[str] = Query(default=None, description="Filter by saved reason code."),
    recommendation: Optional[str] = Query(default=None, description="Filter by saved recommendation (or 'not_investigated')."),
    deadline_within_days: Optional[int] = Query(default=None, description="Only cases with ≤ this many days to the network deadline."),
    q: Optional[str] = Query(default=None, description="Search in complaint text, dispute ID, customer ID."),
    sort: Optional[str] = Query(default="filed_date", description="Sort field: filed_date, days_to_deadline, merchant_name, amount_usd."),
    db: sqlite3.Connection | None = Depends(get_db),
) -> CasesResponse:
    conn = _require_db(db)
    aconn = get_activity_db()
    try:
        rows = conn.execute(
            """SELECT d.dispute_id, d.filed_date, d.customer_id, d.complaint_text,
                      d.status,
                      t.txn_datetime, t.amount_usd, c.card_type,
                      m.name AS merchant_name
               FROM disputes d
               JOIN transactions t ON t.transaction_id = d.transaction_id
               JOIN cards c ON c.card_id = t.card_id
               JOIN merchants m ON m.merchant_id = t.merchant_id
               ORDER BY d.filed_date DESC"""
        ).fetchall()

        recs: dict[str, dict] = {
            row["dispute_id"]: dict(row)
            for row in aconn.execute(
                "SELECT dispute_id, recommendation, confidence, reason_code FROM recommendations"
            ).fetchall()
        }

        cases: list[CaseSummary] = []
        for r in rows:
            did = r["dispute_id"]
            rec_row = recs.get(did)
            rec = rec_row["recommendation"] if rec_row else "not_investigated"
            conf = rec_row["confidence"] if rec_row else ""
            rc = rec_row["reason_code"] if rec_row else None
            dtd = _days_to_deadline(r["filed_date"], r["txn_datetime"])

            # Filters
            if status and r["status"] != status:
                continue
            if card_type and r["card_type"] != card_type:
                continue
            if reason_code and rc != reason_code:
                continue
            if recommendation:
                if recommendation == "not_investigated" and rec_row:
                    continue
                if recommendation != "not_investigated" and rec != recommendation:
                    continue
            if deadline_within_days is not None and dtd > deadline_within_days:
                continue
            if q:
                ql = q.lower()
                if (
                    ql not in did.lower()
                    and ql not in r["customer_id"].lower()
                    and ql not in r["complaint_text"].lower()
                ):
                    continue

            cases.append(CaseSummary(
                dispute_id=did,
                filed_date=r["filed_date"],
                customer_id=r["customer_id"],
                merchant_name=r["merchant_name"],
                amount_usd=r["amount_usd"],
                card_type=r["card_type"],
                days_to_deadline=dtd,
                recommendation=rec,
                confidence=conf,
            ))

        # Sorting
        sort_key = sort or "filed_date"
        reverse = sort_key in ("filed_date",)  # newest first for dates
        if sort_key == "days_to_deadline":
            cases.sort(key=lambda c: c.days_to_deadline)
        elif sort_key == "merchant_name":
            cases.sort(key=lambda c: c.merchant_name.lower())
        elif sort_key == "amount_usd":
            cases.sort(key=lambda c: c.amount_usd, reverse=True)
        else:
            cases.sort(key=lambda c: c.filed_date, reverse=True)

        return CasesResponse(total=len(cases), cases=cases)
    finally:
        aconn.close()


# ---------------------------------------------------------------------------
# 3. GET /api/cases/{dispute_id}
# ---------------------------------------------------------------------------

@router.get("/cases/{dispute_id}", operation_id="api_case_detail",
            summary="Full case page: dispute, transaction, merchant, signals, deadline, recommendation, decisions.")
def case_detail(
    dispute_id: str,
    db: sqlite3.Connection | None = Depends(get_db),
) -> dict:
    conn = _require_db(db)
    aconn = get_activity_db()
    try:
        # Dispute
        dispute = conn.execute(
            "SELECT * FROM disputes WHERE dispute_id = ?", (dispute_id,)
        ).fetchone()
        if dispute is None:
            raise HTTPException(status_code=404, detail=f"Dispute '{dispute_id}' not found.")

        # Transaction + card
        txn = conn.execute(
            """SELECT t.*, c.card_type, m.name AS merchant_name, m.category,
                      m.is_online, m.refund_policy
               FROM transactions t
               JOIN cards c ON c.card_id = t.card_id
               JOIN merchants m ON m.merchant_id = t.merchant_id
               WHERE t.transaction_id = ?""",
            (dispute["transaction_id"],),
        ).fetchone()

        # Shipment
        shipment = conn.execute(
            "SELECT * FROM shipments WHERE transaction_id = ?",
            (dispute["transaction_id"],),
        ).fetchone()

        # Subscription
        sub = None
        if txn["subscription_id"]:
            sub = conn.execute(
                "SELECT start_date, cancelled_date FROM subscriptions WHERE subscription_id = ?",
                (txn["subscription_id"],),
            ).fetchone()

        # Refunds
        refunds = conn.execute(
            "SELECT * FROM refunds WHERE transaction_id = ?",
            (dispute["transaction_id"],),
        ).fetchall()

        # Friendly-fraud signals (always compute for the case page)
        disputed_dt = txn["txn_datetime"]
        disputed_device = txn["device_id"]
        disputed_addr = txn["shipping_address_id"]
        prior_rows = conn.execute(
            """SELECT transaction_id, device_id, shipping_address_id FROM transactions
               WHERE customer_id = ? AND merchant_id = ? AND txn_datetime < ?
                 AND transaction_id != ?""",
            (dispute["customer_id"], txn["merchant_id"], disputed_dt, dispute["transaction_id"]),
        ).fetchall()
        disputed_txn_ids = {
            r[0] for r in conn.execute(
                "SELECT transaction_id FROM disputes WHERE customer_id = ?",
                (dispute["customer_id"],),
            ).fetchall()
        }
        prior_undisputed = [r for r in prior_rows if r["transaction_id"] not in disputed_txn_ids]
        same_dev = sum(1 for r in prior_undisputed if r["device_id"] == disputed_device and disputed_device)
        same_addr = sum(1 for r in prior_undisputed if r["shipping_address_id"] == disputed_addr and disputed_addr)
        device_seen = False
        addr_seen = False
        if disputed_device:
            device_seen = conn.execute(
                "SELECT 1 FROM transactions WHERE customer_id=? AND device_id=? AND txn_datetime<? LIMIT 1",
                (dispute["customer_id"], disputed_device, disputed_dt),
            ).fetchone() is not None
        if disputed_addr:
            addr_seen = conn.execute(
                "SELECT 1 FROM transactions WHERE customer_id=? AND shipping_address_id=? AND txn_datetime<? LIMIT 1",
                (dispute["customer_id"], disputed_addr, disputed_dt),
            ).fetchone() is not None
        past_disputes = conn.execute(
            "SELECT status FROM disputes WHERE customer_id=? AND transaction_id!=?",
            (dispute["customer_id"], dispute["transaction_id"]),
        ).fetchall()
        signals = {
            "prior_undisputed_with_merchant": len(prior_undisputed),
            "same_device_count": same_dev,
            "same_address_count": same_addr,
            "device_seen_before": device_seen,
            "address_seen_before": addr_seen,
            "prior_disputes_count": len(past_disputes),
            "prior_disputes_lost": sum(1 for d in past_disputes if d["status"] == "resolved_merchant"),
        }

        # Deadline (use saved reason code if available, else skip)
        saved_rec = aconn.execute(
            "SELECT * FROM recommendations WHERE dispute_id = ?", (dispute_id,)
        ).fetchone()
        deadline_info: dict | None = None
        if saved_rec:
            from backend.app.routers.deadline import check_deadline, ReasonCode
            try:
                rc_enum = ReasonCode(saved_rec["reason_code"])
                dl = check_deadline(dispute_id, rc_enum, conn)
                deadline_info = dl.model_dump()
            except Exception:
                pass

        # Decisions
        decisions = [
            dict(row)
            for row in aconn.execute(
                "SELECT * FROM decisions WHERE dispute_id = ? ORDER BY ts", (dispute_id,)
            ).fetchall()
        ]

        # Latest letter draft (may be None if the Letter Writer hasn't run yet)
        # Order by id DESC (autoincrement) so the last inserted row is always returned.
        letter_row = aconn.execute(
            "SELECT * FROM letters WHERE dispute_id = ? ORDER BY id DESC LIMIT 1",
            (dispute_id,),
        ).fetchone()

        return {
            "dispute": dict(dispute),
            "transaction": dict(txn),
            "shipment": dict(shipment) if shipment else None,
            "subscription": dict(sub) if sub else None,
            "refunds": [dict(r) for r in refunds],
            "friendly_fraud_signals": signals,
            "deadline": deadline_info,
            "recommendation": dict(saved_rec) if saved_rec else None,
            "decisions": decisions,
            "letter_draft": dict(letter_row) if letter_row else None,
        }
    finally:
        aconn.close()


# ---------------------------------------------------------------------------
# 4. POST /api/cases/{dispute_id}/decision
# ---------------------------------------------------------------------------

@router.post("/cases/{dispute_id}/decision", response_model=DecisionOut,
             operation_id="api_post_decision",
             summary="Record the analyst's final decision for a dispute.")
def post_decision(
    dispute_id: str,
    body: DecisionIn,
    db: sqlite3.Connection | None = Depends(get_db),
) -> DecisionOut:
    conn = _require_db(db)

    # Validate the dispute exists
    if not conn.execute(
        "SELECT 1 FROM disputes WHERE dispute_id = ?", (dispute_id,)
    ).fetchone():
        raise HTTPException(status_code=404, detail=f"Dispute '{dispute_id}' not found.")

    # Validate decision value
    if body.decision not in ("approve", "edit", "override"):
        raise HTTPException(status_code=422, detail="decision must be approve, edit or override.")

    # reason is required for edit and override
    if body.decision in ("edit", "override") and not body.reason:
        raise HTTPException(
            status_code=422,
            detail=f"reason is required when decision is '{body.decision}'.",
        )

    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    aconn = get_activity_db()
    try:
        cur = aconn.execute(
            """INSERT INTO decisions (ts, dispute_id, decision, final_outcome, reason, analyst)
               VALUES (?,?,?,?,?,?)""",
            (ts, dispute_id, body.decision, body.final_outcome, body.reason, body.analyst),
        )
        aconn.commit()
        row_id = cur.lastrowid
    finally:
        aconn.close()

    return DecisionOut(
        id=row_id,
        ts=ts,
        dispute_id=dispute_id,
        decision=body.decision,
        final_outcome=body.final_outcome,
        reason=body.reason,
        analyst=body.analyst,
    )


# ---------------------------------------------------------------------------
# 5. GET /api/activity
# ---------------------------------------------------------------------------

@router.get("/activity", response_model=list[ToolCallRow], operation_id="api_activity",
            summary="Tool calls newer than a given ID, with stage labels.")
def get_activity(
    since: int = Query(default=0, description="Return rows with id > this value. Use 0 for all."),
) -> list[ToolCallRow]:
    aconn = get_activity_db()
    try:
        rows = aconn.execute(
            "SELECT * FROM tool_calls WHERE id > ? ORDER BY id ASC", (since,)
        ).fetchall()
        return [
            ToolCallRow(
                id=r["id"],
                ts=r["ts"],
                tool=r["tool"],
                stage=_STAGE.get(r["tool"], "Other"),
                dispute_id=r["dispute_id"],
                transaction_id=r["transaction_id"],
                status_code=r["status_code"],
                duration_ms=r["duration_ms"],
            )
            for r in rows
        ]
    finally:
        aconn.close()


# ---------------------------------------------------------------------------
# 6. GET /api/audit
# ---------------------------------------------------------------------------

@router.get("/audit", response_model=list[AuditRow], operation_id="api_audit",
            summary="Tool calls and analyst decisions merged into a single timeline.")
def get_audit() -> list[AuditRow]:
    aconn = get_activity_db()
    try:
        tool_rows = aconn.execute(
            "SELECT id, ts, tool, dispute_id, status_code FROM tool_calls ORDER BY ts"
        ).fetchall()
        decision_rows = aconn.execute(
            "SELECT ts, dispute_id, decision, analyst, final_outcome, reason FROM decisions ORDER BY ts"
        ).fetchall()

        timeline: list[AuditRow] = []
        for r in tool_rows:
            timeline.append(AuditRow(
                ts=r["ts"],
                type="tool_call",
                tool=r["tool"],
                stage=_STAGE.get(r["tool"], "Other"),
                dispute_id=r["dispute_id"],
                detail=f"HTTP {r['status_code']}",
            ))
        for r in decision_rows:
            timeline.append(AuditRow(
                ts=r["ts"],
                type="decision",
                dispute_id=r["dispute_id"],
                decision=r["decision"],
                analyst=r["analyst"],
                detail=f"{r['final_outcome']}: {r['reason'] or ''}".strip(": "),
            ))

        timeline.sort(key=lambda x: x.ts)
        return timeline
    finally:
        aconn.close()


# ---------------------------------------------------------------------------
# 7. GET /api/evaluation
# ---------------------------------------------------------------------------

@router.get("/evaluation", response_model=EvaluationResponse, operation_id="api_evaluation",
            summary="Compare saved recommendations against the answer key (data/cases.csv).")
def get_evaluation() -> EvaluationResponse:
    if not CASES_CSV.exists():
        raise HTTPException(status_code=503, detail="Answer key (data/cases.csv) not found.")

    with open(CASES_CSV, newline="", encoding="utf-8") as f:
        answer_key = {row["dispute_id"]: row["expected_outcome"] for row in csv.DictReader(f)}

    aconn = get_activity_db()
    try:
        saved = {
            row["dispute_id"]: row["recommendation"]
            for row in aconn.execute("SELECT dispute_id, recommendation FROM recommendations").fetchall()
        }
    finally:
        aconn.close()

    matches: list[EvalMatch] = []
    correct = 0
    for did, expected in answer_key.items():
        if did not in saved:
            continue
        actual = saved[did]
        ok = actual == expected
        if ok:
            correct += 1
        matches.append(EvalMatch(dispute_id=did, expected=expected, actual=actual, correct=ok))

    investigated = len(matches)
    accuracy = correct / investigated if investigated > 0 else 0.0

    return EvaluationResponse(
        total_cases=len(answer_key),
        investigated=investigated,
        correct=correct,
        accuracy=round(accuracy, 4),
        matches=matches,
    )
