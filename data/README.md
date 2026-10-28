# data/

This folder contains the synthetic database, the answer key for the 30 test
cases, and the generator that produces both.

## Files

| File | Description |
|---|---|
| `generate_data.py` | Creates `disputedesk.db` and `cases.csv` from scratch. |
| `disputedesk.db` | SQLite database committed to the repo. Everyone (and the deployed backend) uses this identical file. |
| `cases.csv` | Answer key for the 30 open test cases. |
| `rules/` | PDF copies of Reg Z §1026.13 and Reg E §1005.11 for offline reference. |
| `tests/` | pytest suite that validates the generated data. |

## Tables

| Table | What it holds |
|---|---|
| `customers` | 60 synthetic customers identified by `CUST-NNNN`. Each has an account open date. |
| `cards` | One or two Visa cards per customer (`credit` or `debit`), with a fake `last4`. |
| `merchants` | 25 fictional merchants across 8 categories (coffee shop, restaurant, grocery, online retail, electronics, streaming, fitness, travel). |
| `subscriptions` | Recurring billing relationships between a customer, card, and streaming merchant. Includes `cancelled_date` when applicable. |
| `transactions` | ~540 posted transactions spanning 400 days before the reference date. Includes `statement_date` (next 5th of month after the transaction), `channel` (in_store / online / recurring), `device_id`, `shipping_address_id`, and `subscription_id`. |
| `shipments` | One row per online order of physical goods. Tracks carrier, expected and actual delivery, and proof-of-delivery flag. |
| `refunds` | Credits applied to transactions. About 15 background refunds plus any planted for test cases. |
| `disputes` | ~20 resolved background disputes plus the 30 open test cases (status `open`). Does **not** contain the correct answers — those are in `cases.csv`. |

## How to regenerate

From the repo root:

```bash
python data/generate_data.py
```

The generator uses `random.seed(42)` and `REFERENCE_DATE = 2026-10-15`, so every run produces an identical database and CSV. The script deletes and recreates `disputedesk.db` each time.

After regenerating, run the validation tests:

```bash
pytest data/tests/
```

## cases.csv columns

| Column | Description |
|---|---|
| `case_id` | Unique case identifier (CASE-NNNN). |
| `dispute_id` | Foreign key into `disputes`. |
| `transaction_id` | The disputed transaction. |
| `customer_id` | Customer who filed the dispute. |
| `filed_date` | Date the dispute was filed. |
| `complaint_text` | The customer's complaint in their own words. |
| `expected_reason_code` | Visa reason code the agent should assign (or N/A). |
| `expected_outcome` | One of: `file_chargeback`, `deny`, `request_more_info`, `escalate`. |
| `demo_case` | `A`, `B`, or `C` for the three slide/video demo cases; empty otherwise. |
| `notes` | One sentence explaining why the expected outcome is correct. |
