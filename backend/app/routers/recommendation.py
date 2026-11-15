"""
routers/recommendation.py – recommend_outcome tool for the DisputeDesk agent.

Plain code, no AI. The decision rules are written down once, here, so every
case is decided the same way and the reasons can be shown to the analyst.
The AI agents still do the language work: reading the complaint, choosing the
reason code, citing the rule and writing letters.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.activity_db import get_activity_db
from backend.app.db import get_db
from backend.app.routers import deadline as deadline_router
from backend.app.routers import tools as tools_router
from backend.app.routers.deadline import ReasonCode

router = APIRouter()

DUPLICATE_WINDOW_MINUTES = 60


class Check(BaseModel):
    name: str = Field(description="What was checked.")
    passed: bool = Field(description="True if the check passed.")
    detail: str = Field(description="One plain-English line explaining the result.")


class RecommendationResponse(BaseModel):
    dispute_id: str = Field(description="The dispute that was assessed.")
    reason_code: str = Field(description="The reason code the dispute was assessed under.")
    recommendation: str = Field(
        description="One of file_chargeback, deny, request_more_info or escalate. A human analyst makes the final decision."
    )
    rule_applied: str = Field(description="The decision rule that produced this recommendation, in plain English.")
    confidence: str = Field(description="High (4 checks passed), Medium (3) or Low (2 or fewer).")
    confidence_points: int = Field(description="How many of the 4 checks passed.")
    checks: list[Check] = Field(
        description="The 4 checks behind the confidence score: within time limits, evidence found, history fits the claim, reason code clear."
    )
    key_evidence: list[str] = Field(description="2 to 4 facts, with IDs, dates and amounts, that support the recommendation.")
    customer_message_hint: str = Field(
        description="What the customer should be told or asked, in plain English, for the letter writer."
    )


def _assess(code: str, contacted_merchant: bool, dispute, txn, deadline, db) -> tuple[str, str, bool, bool, list[str], str]:
    """Return (recommendation, rule, evidence_found, history_fits, evidence, hint)."""
    evidence: list[str] = [
        f"{txn.transaction_id}: ${txn.amount_usd:.2f} at {txn.merchant_name} on {txn.txn_datetime[:10]} ({txn.card_type} card)."
    ]

    if not deadline.within_time_limits:
        evidence.append(deadline.summary)
        return ("deny", "Filed too late: outside the card network or regulation time limit.", True, True, evidence,
                "Explain kindly that the dispute was filed after the time limit, and give the deadline dates.")

    if code == "12.6.1":
        dups = txn.possible_duplicates
        close = [d for d in dups if d.minutes_apart <= DUPLICATE_WINDOW_MINUTES]
        if close:
            d = close[0]
            evidence.append(f"Duplicate of {d.transaction_id}, {d.minutes_apart:g} minutes apart, same card, merchant and amount.")
            return ("file_chargeback", "A matching charge within 60 minutes is a duplicate.", True, True, evidence,
                    "Tell them we opened a dispute for the duplicate charge only.")
        if dups:
            d = dups[0]
            evidence.append(f"Same amount as {d.transaction_id}, but {d.minutes_apart / 60:.1f} hours apart.")
            return ("request_more_info", "Same amount hours apart may be two real purchases.", True, False, evidence,
                    "Ask whether they made two separate purchases that day.")
        return ("request_more_info", "No matching charge was found to support a duplicate.", False, False, evidence,
                "Ask for the receipt or details of the second charge.")

    if code == "13.1":
        merchant = tools_router.get_merchant_info(txn.merchant_id, txn.transaction_id, db)
        ship = merchant.shipment
        if deadline.too_early:
            evidence.append(f"Expected delivery date {deadline.network_start_date} has not passed yet.")
            return ("deny", "Too early: the expected delivery date has not passed.", True, True, evidence,
                    f"Explain they can dispute again after {deadline.network_start_date} if the item has not arrived.")
        if ship is None:
            evidence.append("No shipment record exists for this order.")
            return ("file_chargeback", "No shipment record and nothing delivered.", True, True, evidence,
                    "Tell them we opened a dispute because the item was never shipped.")
        evidence.append(
            f"Shipment by {ship.carrier}: status {ship.delivery_status}, expected {ship.expected_delivery_date}, "
            f"delivered {ship.delivered_date or 'never'}, proof of delivery {'yes' if ship.proof_of_delivery else 'no'}."
        )
        if ship.proof_of_delivery:
            return ("request_more_info", "The carrier has proof of delivery.", True, False, evidence,
                    "Ask them to check with neighbours or building staff and confirm the delivery address.")
        return ("file_chargeback", "Not delivered and the expected delivery date has passed.", True, True, evidence,
                "Tell them we opened a dispute because the item never arrived.")

    if code == "13.2":
        cancelled = txn.subscription_cancelled_date
        if not cancelled:
            evidence.append("No cancellation date is recorded for this subscription.")
            return ("request_more_info", "No record that the subscription was cancelled.", False, False, evidence,
                    "Ask for proof of cancellation, such as a confirmation email.")
        after = txn.txn_datetime[:10] > cancelled
        evidence.append(f"Subscription cancelled on {cancelled}; charge on {txn.txn_datetime[:10]}.")
        if after:
            return ("file_chargeback", "Charged after the subscription was cancelled.", True, True, evidence,
                    "Tell them we opened a dispute for the charge made after they cancelled.")
        return ("deny", "The charge happened before the cancellation date.", True, False, evidence,
                "Explain the charge was made before they cancelled, so it was valid.")

    if code == "13.3":
        if contacted_merchant:
            evidence.append("Customer says they contacted or returned the item to the merchant.")
            return ("file_chargeback", "Not as described, and the customer tried to resolve it with the merchant.", True, True, evidence,
                    "Tell them we opened a dispute with the merchant's bank.")
        evidence.append("Customer does not say they contacted the merchant or returned the item.")
        return ("request_more_info", "The customer must first try to resolve it with the merchant.", False, True, evidence,
                "Ask them to contact the merchant or return the item first, then tell us the outcome.")

    if code == "13.6":
        if txn.refunds:
            r = txn.refunds[0]
            evidence.append(f"Refund {r.refund_id} of ${r.amount_usd:.2f} already posted on {r.refund_date}.")
            return ("deny", "A refund was already posted.", True, False, evidence,
                    f"Tell them the refund of ${r.amount_usd:.2f} was posted on {r.refund_date}.")
        evidence.append("No refund has been posted for this charge.")
        return ("file_chargeback", "A promised refund was never posted.", True, True, evidence,
                "Tell them we opened a dispute for the missing refund.")

    if code == "10.4":
        hist = tools_router.get_customer_history(dispute.customer_id, txn.merchant_id, txn.transaction_id, db)
        s = hist.friendly_fraud_signals
        evidence.append(s.summary)
        genuine = (not s.device_seen_before) and (not s.address_seen_before) and s.prior_undisputed_with_merchant == 0
        if genuine and s.prior_disputes_lost == 0:
            return ("file_chargeback", "New device and new address, with no history at this merchant.", True, True, evidence,
                    "Tell them we opened a fraud dispute and they should watch their account.")
        return ("escalate", "The customer's own history conflicts with the claim (possible friendly fraud).", True, False, evidence,
                "Tell them a specialist is reviewing the case. Do not mention fraud suspicions.")

    # N/A – unclear complaint
    hist = tools_router.get_customer_history(dispute.customer_id, txn.merchant_id, txn.transaction_id, db)
    if txn.subscription_id:
        evidence.append(f"This is a recurring subscription charge ({txn.subscription_id}) that started on {txn.subscription_start_date}.")
    prior = [t for t in hist.transactions if t.merchant_id == txn.merchant_id and t.transaction_id != txn.transaction_id]
    evidence.append(f"{len(prior)} earlier charge(s) at this merchant on the customer's account.")
    return ("request_more_info", "The complaint does not describe a clear problem.", True, True, evidence,
            "Ask whether they recognise the merchant or a subscription with them.")


@router.get(
    "/disputes/{dispute_id}/recommendation",
    response_model=RecommendationResponse,
    operation_id="recommend_outcome",
    summary="Get the rule-based recommendation and confidence score for a dispute.",
    description=(
        "Applies DisputeDesk's written decision rules to a dispute and returns the recommendation "
        "(file_chargeback, deny, request_more_info or escalate), the rule that produced it, the 4 confidence "
        "checks (within time limits, evidence found, history fits the claim, reason code clear) and the key "
        "evidence. Use this as the final step of every investigation and present its recommendation exactly; "
        "do not change it. A human analyst makes the final decision."
    ),
)
def recommend_outcome(
    dispute_id: str,
    reason_code: ReasonCode = Query(
        description="The Visa reason code chosen for this dispute: 10.4, 12.6.1, 13.1, 13.2, 13.3, 13.6 or N/A."
    ),
    customer_contacted_merchant: Optional[bool] = Query(
        default=False,
        description="True if the complaint says the customer contacted the merchant or returned the item (matters for 13.3).",
    ),
    db: sqlite3.Connection | None = Depends(get_db),
) -> RecommendationResponse:
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not available.")

    dispute = tools_router.get_dispute(dispute_id, db)
    txn = tools_router.get_transaction(dispute.transaction_id, db)
    deadline = deadline_router.check_deadline(dispute_id, reason_code, db)
    code = reason_code.value

    rec, rule, evidence_found, history_fits, evidence, hint = _assess(
        code, bool(customer_contacted_merchant), dispute, txn, deadline, db
    )

    checks = [
        Check(name="Within time limits", passed=deadline.within_time_limits, detail=deadline.summary),
        Check(name="Evidence found", passed=evidence_found, detail=evidence[-1]),
        Check(
            name="History fits the claim",
            passed=history_fits,
            detail="The records agree with what the customer says." if history_fits
            else "Some records conflict with what the customer says.",
        ),
        Check(
            name="Reason code clear",
            passed=code != "N/A",
            detail=f"Reason code {code}." if code != "N/A" else "The complaint does not point to a clear reason code.",
        ),
    ]
    points = sum(c.passed for c in checks)
    level = "High" if points == 4 else "Medium" if points == 3 else "Low"

    # Safety net: never recommend a chargeback on weak evidence.
    if rec == "file_chargeback" and level == "Low":
        rec, rule = "escalate", rule + " Confidence is low, so a senior analyst should review it."

    result = RecommendationResponse(
        dispute_id=dispute_id,
        reason_code=code,
        recommendation=rec,
        rule_applied=rule,
        confidence=level,
        confidence_points=points,
        checks=checks,
        key_evidence=evidence[:4],
        customer_message_hint=hint,
    )

    # Persist to recommendations table so the dashboard can show it.
    # Wrapped in try/except so a DB write failure never breaks the tool call.
    try:
        aconn = get_activity_db()
        try:
            aconn.execute(
                """INSERT OR REPLACE INTO recommendations
                   (dispute_id, ts, reason_code, recommendation, confidence, response_json)
                   VALUES (?,?,?,?,?,?)""",
                (
                    dispute_id,
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    code,
                    rec,
                    level,
                    json.dumps(result.model_dump()),
                ),
            )
            aconn.commit()
        finally:
            aconn.close()
    except Exception:
        pass

    return result
