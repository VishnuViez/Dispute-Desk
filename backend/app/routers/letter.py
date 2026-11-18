"""
routers/letter.py – record_letter_draft tool for the DisputeDesk agent.

The Letter Writer agent calls this once after writing a customer letter so
the analyst can review it in the dashboard and the "Letter" pipeline stage
lights up.  Nothing is sent to the customer; this endpoint only saves the
draft to data/activity.db.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.activity_db import get_activity_db
from backend.app.db import get_db

router = APIRouter()


class LetterDraftIn(BaseModel):
    outcome: str = Field(
        description=(
            "The dispute outcome this letter covers: file_chargeback, deny, "
            "request_more_info or escalate."
        )
    )
    letter_text: str = Field(
        description="The full customer letter text, 100–170 words, addressed to 'Dear Cardholder'."
    )
    chargeback_summary: Optional[str] = Field(
        default=None,
        description=(
            "Bullet-point chargeback summary for the merchant's bank. "
            "Required when outcome is file_chargeback, omitted otherwise."
        ),
    )


class LetterDraftResponse(BaseModel):
    id: int = Field(description="Row ID of the saved draft in the letters table.")
    dispute_id: str = Field(description="The dispute the letter was written for.")
    ts: str = Field(description="ISO-8601 timestamp of when the draft was saved.")
    outcome: str = Field(description="The outcome this letter covers.")
    message: str = Field(description="Confirmation that the draft was saved for analyst review.")


@router.post(
    "/disputes/{dispute_id}/letter-draft",
    response_model=LetterDraftResponse,
    operation_id="record_letter_draft",
    summary="Save a drafted customer letter for analyst review.",
    description=(
        "Saves the drafted customer letter so the analyst can review it in the "
        "DisputeDesk dashboard. Call once after writing a letter. "
        "Nothing is sent to the customer."
    ),
)
def record_letter_draft(
    dispute_id: str,
    body: LetterDraftIn,
    db: sqlite3.Connection | None = Depends(get_db),
) -> LetterDraftResponse:
    # Verify the dispute exists (read-only data DB).
    if db is None:
        raise HTTPException(status_code=503, detail="Data database is not available.")
    row = db.execute(
        "SELECT 1 FROM disputes WHERE dispute_id = ?", (dispute_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Dispute '{dispute_id}' not found.")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    aconn = get_activity_db()
    try:
        cur = aconn.execute(
            """INSERT INTO letters (dispute_id, ts, outcome, letter_text, chargeback_summary)
               VALUES (?, ?, ?, ?, ?)""",
            (dispute_id, ts, body.outcome, body.letter_text, body.chargeback_summary),
        )
        aconn.commit()
        row_id = cur.lastrowid
    finally:
        aconn.close()

    return LetterDraftResponse(
        id=row_id,
        dispute_id=dispute_id,
        ts=ts,
        outcome=body.outcome,
        message="Draft saved. The analyst can now review it in the DisputeDesk dashboard.",
    )
