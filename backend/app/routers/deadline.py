"""
routers/deadline.py – check_deadline tool for the DisputeDesk agent.

Plain code, no AI: deadlines must be exact, so the agent never works them
out itself. The rules are the simplified ones in docs/PROJECT_BRIEF.md:
- Card network: filed within 120 days of the transaction date
  (for 13.1, counted from the expected delivery date).
- Reg Z (credit) / Reg E (debit): notice within 60 days after the statement.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.db import get_db

router = APIRouter()

NETWORK_LIMIT_DAYS = 120
NOTICE_LIMIT_DAYS = 60


class ReasonCode(str, Enum):
    """Visa reason codes DisputeDesk uses (N/A = complaint is unclear)."""

    fraud_card_absent = "10.4"
    duplicate_processing = "12.6.1"
    not_received = "13.1"
    cancelled_recurring = "13.2"
    not_as_described = "13.3"
    credit_not_processed = "13.6"
    unclear = "N/A"


class BankResponseDeadlines(BaseModel):
    acknowledge_by: Optional[str] = Field(
        default=None,
        description="Credit cards only: date by which the bank must acknowledge the dispute in writing (Reg Z, 30 days).",
    )
    investigate_by: Optional[str] = Field(
        default=None,
        description="Debit cards only: date by which the bank must finish investigating (Reg E, 10 business days).",
    )
    resolve_by: str = Field(
        description="Latest date by which the bank must resolve the dispute (90 days after it was filed)."
    )
    note: str = Field(description="Plain-English explanation of these bank deadlines.")


class DeadlineCheckResponse(BaseModel):
    dispute_id: str = Field(description="The dispute that was checked.")
    reason_code: str = Field(description="The reason code the deadlines were checked for.")
    card_type: str = Field(description="'credit' or 'debit'.")
    regulation: str = Field(description="'Reg Z' for credit cards or 'Reg E' for debit cards.")
    transaction_date: str = Field(description="Date of the disputed charge (YYYY-MM-DD).")
    statement_date: str = Field(description="Statement on which the charge first appeared (YYYY-MM-DD).")
    filed_date: str = Field(description="Date the customer filed the dispute (YYYY-MM-DD).")
    network_start_date: str = Field(
        description="Date the 120-day card network limit counts from: the transaction date, or the expected delivery date for 13.1."
    )
    network_deadline: str = Field(description="Last day to file under the 120-day card network limit.")
    network_ok: bool = Field(description="True if the dispute was filed within the card network limit.")
    regulation_notice_deadline: str = Field(
        description="Last day for the customer's notice under Reg Z or Reg E (60 days after the statement)."
    )
    regulation_ok: bool = Field(description="True if the customer's notice was within the 60-day regulation limit.")
    too_early: bool = Field(
        description="True only for 13.1 when the dispute was filed before the expected delivery date."
    )
    within_time_limits: bool = Field(
        description="True only if both the card network limit and the regulation limit were met. If false, the dispute was filed too late."
    )
    bank_response_deadlines: BankResponseDeadlines = Field(
        description="Deadlines the bank itself must meet when handling this dispute."
    )
    summary: str = Field(description="One plain-English sentence summarizing the deadline check.")


def _d(value: str) -> date:
    return date.fromisoformat(value[:10])


def _add_business_days(start: date, days: int) -> date:
    """Add weekdays only (weekends skipped, holidays ignored for the prototype)."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


@router.get(
    "/disputes/{dispute_id}/deadline-check",
    response_model=DeadlineCheckResponse,
    operation_id="check_deadline",
    summary="Check whether a dispute was filed within the time limits.",
    description=(
        "Checks a dispute against the card network's 120-day limit (counted from the "
        "expected delivery date for reason code 13.1) and the 60-day customer notice "
        "limit in Regulation Z (credit cards) or Regulation E (debit cards). Returns "
        "within_time_limits, too_early (13.1 only), the exact deadline dates, and the "
        "deadlines the bank must meet. Always use this instead of calculating dates yourself."
    ),
)
def check_deadline(
    dispute_id: str,
    reason_code: ReasonCode = Query(
        description="The Visa reason code chosen for this dispute: 10.4, 12.6.1, 13.1, 13.2, 13.3, 13.6 or N/A."
    ),
    db: sqlite3.Connection | None = Depends(get_db),
) -> DeadlineCheckResponse:
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not available.")

    dispute = db.execute(
        "SELECT dispute_id, transaction_id, filed_date FROM disputes WHERE dispute_id = ?",
        (dispute_id,),
    ).fetchone()
    if dispute is None:
        raise HTTPException(status_code=404, detail=f"Dispute '{dispute_id}' not found.")

    txn = db.execute(
        """SELECT t.txn_datetime, t.statement_date, c.card_type
           FROM transactions t JOIN cards c ON c.card_id = t.card_id
           WHERE t.transaction_id = ?""",
        (dispute["transaction_id"],),
    ).fetchone()
    if txn is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{dispute['transaction_id']}' for dispute '{dispute_id}' not found.",
        )

    filed = _d(dispute["filed_date"])
    txn_date = _d(txn["txn_datetime"])
    statement = _d(txn["statement_date"])
    card_type = txn["card_type"]
    code = reason_code.value

    # 13.1 counts from the expected delivery date, because the customer
    # cannot know an item is missing until it was due to arrive.
    network_start = txn_date
    too_early = False
    if code == "13.1":
        ship = db.execute(
            "SELECT expected_delivery_date FROM shipments WHERE transaction_id = ?",
            (dispute["transaction_id"],),
        ).fetchone()
        if ship and ship["expected_delivery_date"]:
            expected = _d(ship["expected_delivery_date"])
            network_start = expected
            too_early = filed < expected

    network_deadline = network_start + timedelta(days=NETWORK_LIMIT_DAYS)
    network_ok = filed <= network_deadline
    notice_deadline = statement + timedelta(days=NOTICE_LIMIT_DAYS)
    regulation_ok = filed <= notice_deadline
    within = network_ok and regulation_ok

    if card_type == "credit":
        regulation = "Reg Z"
        bank = BankResponseDeadlines(
            acknowledge_by=(filed + timedelta(days=30)).isoformat(),
            resolve_by=(filed + timedelta(days=90)).isoformat(),
            note="Reg Z: acknowledge within 30 days; resolve within two complete billing cycles and never later than 90 days.",
        )
    else:
        regulation = "Reg E"
        bank = BankResponseDeadlines(
            investigate_by=_add_business_days(filed, 10).isoformat(),
            resolve_by=(filed + timedelta(days=90)).isoformat(),
            note="Reg E: investigate within 10 business days, or up to 90 days for debit card purchases if a provisional credit is given within those 10 business days.",
        )

    if too_early:
        summary = (
            f"Filed on {filed} before the expected delivery date {network_start}, so it is too early; "
            "the customer can dispute again after that date."
        )
    elif within:
        summary = (
            f"Filed on {filed}, within the card network deadline ({network_deadline}) "
            f"and the {regulation} notice deadline ({notice_deadline})."
        )
    else:
        missed = []
        if not network_ok:
            missed.append(f"the card network deadline ({network_deadline})")
        if not regulation_ok:
            missed.append(f"the {regulation} notice deadline ({notice_deadline})")
        summary = f"Filed on {filed}, which is after " + " and ".join(missed) + ", so it was filed too late."

    return DeadlineCheckResponse(
        dispute_id=dispute_id,
        reason_code=code,
        card_type=card_type,
        regulation=regulation,
        transaction_date=txn_date.isoformat(),
        statement_date=statement.isoformat(),
        filed_date=filed.isoformat(),
        network_start_date=network_start.isoformat(),
        network_deadline=network_deadline.isoformat(),
        network_ok=network_ok,
        regulation_notice_deadline=notice_deadline.isoformat(),
        regulation_ok=regulation_ok,
        too_early=too_early,
        within_time_limits=within,
        bank_response_deadlines=bank,
        summary=summary,
    )
