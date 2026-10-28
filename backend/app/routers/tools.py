"""
routers/tools.py – Tool endpoints for the DisputeDesk agent.

All endpoints are read-only. They report facts; the AI agent in watsonx
Orchestrate draws conclusions from what they return.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.db import get_db
from backend.app.models import (
    CustomerHistoryResponse,
    DisputeResponse,
    FraudSignals,
    MerchantResponse,
    PossibleDuplicate,
    RefundRecord,
    ShipmentRecord,
    TransactionResponse,
    TransactionSummary,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_db(db: sqlite3.Connection | None) -> sqlite3.Connection:
    """Raise a 503 if the database is unavailable (missing file)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not available.")
    return db


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# 1. GET /tools/disputes/{dispute_id}
# ---------------------------------------------------------------------------

@router.get(
    "/disputes/{dispute_id}",
    response_model=DisputeResponse,
    operation_id="get_dispute",
    summary="Look up a dispute by ID.",
    description=(
        "Returns the dispute record and the card type (credit or debit) of the "
        "charged account. Use this as your first call when a customer reports a problem."
    ),
)
def get_dispute(
    dispute_id: str,
    db: sqlite3.Connection | None = Depends(get_db),
) -> DisputeResponse:
    conn = _require_db(db)

    row = conn.execute(
        "SELECT * FROM disputes WHERE dispute_id = ?", (dispute_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Dispute '{dispute_id}' not found.")

    # Fetch card_type through the disputed transaction's card
    card_type_row = conn.execute(
        """SELECT c.card_type
           FROM transactions t
           JOIN cards c ON c.card_id = t.card_id
           WHERE t.transaction_id = ?""",
        (row["transaction_id"],),
    ).fetchone()
    card_type = card_type_row["card_type"] if card_type_row else "unknown"

    return DisputeResponse(
        dispute_id=row["dispute_id"],
        transaction_id=row["transaction_id"],
        customer_id=row["customer_id"],
        filed_date=row["filed_date"],
        complaint_text=row["complaint_text"],
        status=row["status"],
        card_type=card_type,
    )


# ---------------------------------------------------------------------------
# 2. GET /tools/transactions/{transaction_id}
# ---------------------------------------------------------------------------

@router.get(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse,
    operation_id="get_transaction",
    summary="Look up a transaction and check for duplicates.",
    description=(
        "Returns all details of a transaction including the merchant name, card type, "
        "any subscription dates, any refunds, and any other charges on the same card "
        "at the same merchant for the same amount within 24 hours."
    ),
)
def get_transaction(
    transaction_id: str,
    db: sqlite3.Connection | None = Depends(get_db),
) -> TransactionResponse:
    conn = _require_db(db)

    txn = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()
    if txn is None:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found.")

    # Merchant name and category
    merch = conn.execute(
        "SELECT name, category FROM merchants WHERE merchant_id = ?", (txn["merchant_id"],)
    ).fetchone()

    # Card type
    card = conn.execute(
        "SELECT card_type FROM cards WHERE card_id = ?", (txn["card_id"],)
    ).fetchone()

    # Subscription dates (if this is a recurring charge)
    sub_start = sub_cancelled = None
    if txn["subscription_id"]:
        sub = conn.execute(
            "SELECT start_date, cancelled_date FROM subscriptions WHERE subscription_id = ?",
            (txn["subscription_id"],),
        ).fetchone()
        if sub:
            sub_start = sub["start_date"]
            sub_cancelled = sub["cancelled_date"]

    # Refunds for this transaction
    refund_rows = conn.execute(
        "SELECT refund_id, refund_date, amount_usd FROM refunds WHERE transaction_id = ?",
        (transaction_id,),
    ).fetchall()
    refunds = [
        RefundRecord(
            refund_id=r["refund_id"],
            refund_date=r["refund_date"],
            amount_usd=r["amount_usd"],
        )
        for r in refund_rows
    ]

    # Possible duplicates: same card, merchant, amount within 24 hours
    this_dt = _parse_dt(txn["txn_datetime"])
    dup_rows = conn.execute(
        """SELECT transaction_id, txn_datetime
           FROM transactions
           WHERE card_id = ? AND merchant_id = ? AND ABS(amount_usd - ?) < 0.005
             AND transaction_id != ?""",
        (txn["card_id"], txn["merchant_id"], txn["amount_usd"], transaction_id),
    ).fetchall()
    duplicates: list[PossibleDuplicate] = []
    for d in dup_rows:
        d_dt = _parse_dt(d["txn_datetime"])
        diff_seconds = abs((d_dt - this_dt).total_seconds())
        if diff_seconds <= 86400:  # 24 hours
            duplicates.append(
                PossibleDuplicate(
                    transaction_id=d["transaction_id"],
                    txn_datetime=d["txn_datetime"],
                    minutes_apart=round(diff_seconds / 60, 2),
                )
            )

    return TransactionResponse(
        transaction_id=txn["transaction_id"],
        card_id=txn["card_id"],
        customer_id=txn["customer_id"],
        merchant_id=txn["merchant_id"],
        merchant_name=merch["name"] if merch else "",
        merchant_category=merch["category"] if merch else "",
        txn_datetime=txn["txn_datetime"],
        amount_usd=txn["amount_usd"],
        currency=txn["currency"],
        channel=txn["channel"],
        device_id=txn["device_id"],
        shipping_address_id=txn["shipping_address_id"],
        subscription_id=txn["subscription_id"],
        subscription_start_date=sub_start,
        subscription_cancelled_date=sub_cancelled,
        statement_date=txn["statement_date"],
        status=txn["status"],
        card_type=card["card_type"] if card else "unknown",
        refunds=refunds,
        possible_duplicates=duplicates,
    )


# ---------------------------------------------------------------------------
# 3. GET /tools/customers/{customer_id}/history
# ---------------------------------------------------------------------------

@router.get(
    "/customers/{customer_id}/history",
    response_model=CustomerHistoryResponse,
    operation_id="get_customer_history",
    summary="Get a customer's transaction history and optional fraud signals.",
    description=(
        "Returns the customer's account open date and up to 50 recent transactions. "
        "When you also supply merchant_id and transaction_id, the response includes "
        "friendly_fraud_signals: counts of prior purchases at the same merchant using "
        "the same device or shipping address, device/address novelty flags, and the "
        "customer's dispute history."
    ),
)
def get_customer_history(
    customer_id: str,
    merchant_id: Optional[str] = Query(default=None, description="Filter signals to this merchant."),
    transaction_id: Optional[str] = Query(
        default=None,
        description="The disputed transaction ID. Required with merchant_id to get fraud signals.",
    ),
    db: sqlite3.Connection | None = Depends(get_db),
) -> CustomerHistoryResponse:
    conn = _require_db(db)

    cust = conn.execute(
        "SELECT account_open_date FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    if cust is None:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found.")

    # Up to 50 transactions, newest first
    txn_rows = conn.execute(
        """SELECT t.transaction_id, t.merchant_id, m.name AS merchant_name,
                  t.txn_datetime, t.amount_usd, t.channel,
                  t.device_id, t.shipping_address_id
           FROM transactions t
           JOIN merchants m ON m.merchant_id = t.merchant_id
           WHERE t.customer_id = ?
           ORDER BY t.txn_datetime DESC
           LIMIT 50""",
        (customer_id,),
    ).fetchall()

    transactions = [
        TransactionSummary(
            transaction_id=r["transaction_id"],
            merchant_id=r["merchant_id"],
            merchant_name=r["merchant_name"],
            txn_datetime=r["txn_datetime"],
            amount_usd=r["amount_usd"],
            channel=r["channel"],
            device_id=r["device_id"],
            shipping_address_id=r["shipping_address_id"],
        )
        for r in txn_rows
    ]

    # Fraud signals require both merchant_id and transaction_id
    signals: FraudSignals | None = None
    if merchant_id and transaction_id:
        # Look up the disputed transaction to get its device and address
        disputed = conn.execute(
            "SELECT txn_datetime, device_id, shipping_address_id FROM transactions WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()
        if disputed is None:
            raise HTTPException(
                status_code=404, detail=f"Transaction '{transaction_id}' not found."
            )

        disputed_dt = disputed["txn_datetime"]
        disputed_device = disputed["device_id"]
        disputed_addr = disputed["shipping_address_id"]

        # Prior transactions at this merchant before the disputed charge
        prior_rows = conn.execute(
            """SELECT t.transaction_id, t.device_id, t.shipping_address_id
               FROM transactions t
               WHERE t.customer_id = ? AND t.merchant_id = ?
                 AND t.txn_datetime < ?
                 AND t.transaction_id != ?""",
            (customer_id, merchant_id, disputed_dt, transaction_id),
        ).fetchall()

        # Only those not already disputed
        disputed_txn_ids = {
            r[0] for r in conn.execute(
                "SELECT transaction_id FROM disputes WHERE customer_id = ?", (customer_id,)
            ).fetchall()
        }
        prior_undisputed = [r for r in prior_rows if r["transaction_id"] not in disputed_txn_ids]

        same_dev = sum(1 for r in prior_undisputed if r["device_id"] == disputed_device and disputed_device)
        same_addr = sum(1 for r in prior_undisputed if r["shipping_address_id"] == disputed_addr and disputed_addr)

        # Device / address novelty: seen anywhere in customer history before this charge
        device_seen = False
        addr_seen = False
        if disputed_device:
            device_seen = conn.execute(
                """SELECT 1 FROM transactions
                   WHERE customer_id = ? AND device_id = ? AND txn_datetime < ?
                   LIMIT 1""",
                (customer_id, disputed_device, disputed_dt),
            ).fetchone() is not None
        if disputed_addr:
            addr_seen = conn.execute(
                """SELECT 1 FROM transactions
                   WHERE customer_id = ? AND shipping_address_id = ? AND txn_datetime < ?
                   LIMIT 1""",
                (customer_id, disputed_addr, disputed_dt),
            ).fetchone() is not None

        # Past disputes for this customer
        past_disputes = conn.execute(
            """SELECT status FROM disputes
               WHERE customer_id = ? AND transaction_id != ?""",
            (customer_id, transaction_id),
        ).fetchall()
        prior_disputes_count = len(past_disputes)
        prior_disputes_lost = sum(1 for d in past_disputes if d["status"] == "resolved_merchant")

        n_prior = len(prior_undisputed)
        summary = (
            f"This customer has {n_prior} earlier undisputed purchase(s) at this merchant "
            f"({same_dev} with the same device, {same_addr} with the same shipping address); "
            f"the device was {'previously seen' if device_seen else 'not previously seen'} "
            f"and the shipping address was {'previously seen' if addr_seen else 'not previously seen'} "
            f"across all their transactions; "
            f"they have filed {prior_disputes_count} past dispute(s), "
            f"{prior_disputes_lost} of which were resolved in the merchant's favour."
        )

        signals = FraudSignals(
            prior_undisputed_with_merchant=n_prior,
            same_device_count=same_dev,
            same_address_count=same_addr,
            device_seen_before=device_seen,
            address_seen_before=addr_seen,
            prior_disputes_count=prior_disputes_count,
            prior_disputes_lost=prior_disputes_lost,
            summary=summary,
        )

    return CustomerHistoryResponse(
        customer_id=customer_id,
        account_open_date=cust["account_open_date"],
        transactions=transactions,
        friendly_fraud_signals=signals,
    )


# ---------------------------------------------------------------------------
# 4. GET /tools/merchants/{merchant_id}
# ---------------------------------------------------------------------------

@router.get(
    "/merchants/{merchant_id}",
    response_model=MerchantResponse,
    operation_id="get_merchant_info",
    summary="Look up a merchant and optional shipment details.",
    description=(
        "Returns the merchant's name, category, whether they operate online, and their "
        "refund policy. Provide transaction_id to also get the shipment record for that order."
    ),
)
def get_merchant_info(
    merchant_id: str,
    transaction_id: Optional[str] = Query(
        default=None,
        description="Include the shipment record for this transaction, if one exists.",
    ),
    db: sqlite3.Connection | None = Depends(get_db),
) -> MerchantResponse:
    conn = _require_db(db)

    merch = conn.execute(
        "SELECT * FROM merchants WHERE merchant_id = ?", (merchant_id,)
    ).fetchone()
    if merch is None:
        raise HTTPException(status_code=404, detail=f"Merchant '{merchant_id}' not found.")

    shipment: ShipmentRecord | None = None
    if transaction_id:
        # Verify the transaction exists
        txn_check = conn.execute(
            "SELECT transaction_id FROM transactions WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()
        if txn_check is None:
            raise HTTPException(
                status_code=404, detail=f"Transaction '{transaction_id}' not found."
            )

        ship_row = conn.execute(
            "SELECT * FROM shipments WHERE transaction_id = ?", (transaction_id,)
        ).fetchone()
        if ship_row:
            shipment = ShipmentRecord(
                shipment_id=ship_row["shipment_id"],
                carrier=ship_row["carrier"],
                shipped_date=ship_row["shipped_date"],
                expected_delivery_date=ship_row["expected_delivery_date"],
                delivered_date=ship_row["delivered_date"],
                delivery_status=ship_row["delivery_status"],
                proof_of_delivery=bool(ship_row["proof_of_delivery"]),
            )

    return MerchantResponse(
        merchant_id=merch["merchant_id"],
        name=merch["name"],
        category=merch["category"],
        is_online=bool(merch["is_online"]),
        refund_policy=merch["refund_policy"],
        shipment=shipment,
    )
