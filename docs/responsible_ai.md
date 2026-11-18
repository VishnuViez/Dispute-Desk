# DisputeDesk – Responsible AI

This document describes the governance choices built into DisputeDesk and the limitations that a real bank would need to address before deploying it.

---

## Human in the loop

No dispute is approved, denied, escalated or sent to the customer automatically. After every investigation the agent ends with:

> "Reply approve, edit or override."

The analyst reviews the recommendation, the confidence score, the four named checks, the key evidence and the rule. They can:
- **Approve** the recommendation as-is.
- **Edit** the outcome (choosing a different one, with a mandatory reason).
- **Override** the recommendation entirely (also requiring a reason).

The analyst records the decision on the dashboard case page (decision, final outcome, analyst name and, for edits and overrides, a reason). It is saved to `data/activity.db`. The Letter Writer drafts the customer letter for the analyst to review — it does not send anything.

There are no automatic denials. Even when the deadline check returns `within_time_limits=false`, the recommendation is `deny` — which still requires the analyst to approve it before anything happens.

---

## Facts not people

The agent instructions explicitly prohibit describing customers in ways that imply character. All agents are instructed: *"Describe facts, never people. Say '3 earlier undisputed purchases from the same device', never 'the customer is a fraudster'."* The Letter Writer is instructed never to mention "friendly fraud", fraud suspicions, confidence scores or internal checks in a customer letter.

---

## No names, ZIP codes or demographics

The database contains no real names, addresses, phone numbers, email addresses, card numbers or ZIP codes. Customers are identified by synthetic IDs (`CUST-0001`). Devices are `DEV-0001`. Shipping addresses are `ADDR-0001`.

Decisions are made on transaction patterns (timing, device, address history, subscription dates, refund records) — not on who the customer is, where they live, or any demographic attribute. `test_no_email_addresses` and `test_no_phone_numbers` verify this automatically on every test run.

---

## Synthetic data only

`data/disputedesk.db` is generated entirely by `data/generate_data.py` using `random.seed(42)` and a fixed reference date of `2026-10-15`. All 60 customers, 25 merchants, 543 transactions and 30 open disputes are fictitious. No real transaction data was used at any stage of development.

---

## Audit log

Every `/tools/*` call is logged to `data/activity.db` by the `ActivityLogMiddleware`. Each row records the tool name, dispute ID, HTTP status code, timestamp and duration. `recommend_outcome` additionally writes its full result to the `recommendations` table. Analyst decisions (approve, edit, override) are written to the `decisions` table with the analyst's name and a mandatory reason for edits and overrides.

`GET /api/audit` returns a merged, sorted timeline of tool calls and decisions so a supervisor can reconstruct exactly what happened on any case. This log is not committed — it is created on first use and lives only on the team laptop.

---

## Deterministic deadline and decision rules

Deadlines and the final recommendation are computed in Python, not by the language model. `check_deadline` applies the 120-day card network limit and the 60-day Reg Z / Reg E notice limit by exact date arithmetic, using dates from the database. `recommend_outcome` applies a written decision tree with explicit conditions for each reason code. Both are covered by automated tests (121 tests, including 30/30 answer-key coverage for `recommend_outcome`).

This means the same case always produces the same recommendation regardless of which model version is running, and the recommendation can be explained line by line.

---

## Limitations

| Limitation | Impact |
|---|---|
| **Simplified time-limit rules** | The prototype uses a flat 120-day card network window and a 60-day notice window. Real Visa rules have exceptions, card-type variations and chargeback reason-code-specific limits. This is a known simplification and must not be used for real disputes. |
| **Visa only** | Only Visa reason codes are implemented. Mastercard, Amex and Discover have different code systems. |
| **Third-party model** | GPT-OSS 120B (via Groq) is the only model available in the lab account. It is not an IBM model. The language outputs — complaint classification, rule citation, letter text — are not deterministic and have not been formally evaluated for bias. |
| **No authentication** | The FastAPI backend has no login. Anyone who can reach `localhost:8000` (or the Cloudflare tunnel URL) can call any tool. A production deployment would require authentication and rate limiting. |
| **No real shipment or fraud data** | The fraud signals (device history, address history) are synthetic. Real patterns of fraud are more varied and would require a larger, real training dataset to validate. |
| **Single analyst, no access controls** | All decisions are logged under whatever name the analyst types. There is no session management or role-based access control. |

---

## What a real bank would add

- Authentication and audit log retention with tamper-proof storage.
- Formal bias evaluation across demographic proxies (not stored in this prototype, but available in real data).
- Legal review of the simplified time-limit rules against the full Visa Dispute Resolution Rules and applicable regulations.
- A model that has been evaluated and approved for financial services use.
- Integration with the bank's core systems rather than a local SQLite database.
- A formal human-review threshold: for example, any `escalate` recommendation that persists for 48 hours without analyst action triggers an automatic escalation to a manager.
