# DisputeDesk – Project Brief

Read this file before doing any work in this repo. It is the shared source of truth for the whole team and for IBM Bob.

## What we are building

DisputeDesk is a prototype AI agent that helps a bank's card dispute analyst investigate credit and debit card disputes. The agent:

1. reads the customer's complaint in their own words,
2. picks the card-network reason code,
3. checks deadlines,
4. gathers evidence through our backend tools,
5. checks the rules,
6. recommends one of four outcomes, with a confidence score, the evidence and the rule it relied on.

A human analyst always makes the final decision. The agent never denies a customer on its own.

Built for the IBM SkillsBuild AI Experiential Learning Lab (US Fall 2026), track: Revolutionizing Banking & Financial Services.

## Program rules that affect our code

- IBM Bob IDE is a required, core part of how we build. After every Bob task, export the task session report into `bob-reports/`.
- Synthetic data only. No real names, card numbers, emails, phone numbers or street addresses. Customers are IDs like `CUST-0001`.
- Every outside source goes in `docs/sources.md` (URL, date accessed, license or terms, what we used it for).
- Do not copy Visa or Mastercard documents into the repo. We summarize their rules in our own words (see below) and link to them.
- The agent runs in IBM watsonx Orchestrate with an IBM Granite model. It calls our FastAPI backend as tools through the OpenAPI spec.

## Tech stack

- Python 3.11+, FastAPI, Pydantic v2, uvicorn
- SQLite through Python's built-in `sqlite3` module (no ORM)
- pytest and FastAPI's TestClient for tests
- No AI or LLM calls inside the backend tools. Tools only read data. The AI part lives in Orchestrate.

## Repo layout

```
README.md
requirements.txt
.gitignore
pytest.ini
docs/          PROJECT_BRIEF.md, sources.md, design notes
data/          generate_data.py, disputedesk.db, cases.csv, rules/, tests/
backend/       app/ (main.py, db.py, models.py, routers/tools.py), tests/
agent/         Orchestrate agent instructions and tool specs (later)
ui/            analyst dashboard (later)
bob-reports/   exported Bob task session reports
```

`data/disputedesk.db` is committed so everyone (and the deployed backend) uses identical data.

## Fixed "world date"

The synthetic world's "today" is `REFERENCE_DATE = 2026-10-15`. All dates are generated relative to it, and the generator uses `random.seed(42)`, so every run produces the same data.

## Database schema (team contract – do not rename without team agreement)

All IDs are TEXT. Dates are `YYYY-MM-DD`. Datetimes are `YYYY-MM-DDTHH:MM:SS`. Money is USD as REAL rounded to 2 decimals.

**customers**
- `customer_id` TEXT PRIMARY KEY – e.g. `CUST-0001`
- `account_open_date` TEXT

**cards**
- `card_id` TEXT PRIMARY KEY – e.g. `CARD-0001`
- `customer_id` TEXT – references customers
- `network` TEXT – always `visa` in this prototype
- `card_type` TEXT – `credit` or `debit`
- `last4` TEXT – fake 4 digits

**merchants**
- `merchant_id` TEXT PRIMARY KEY – e.g. `MERCH-001`
- `name` TEXT – fictional business name
- `category` TEXT – one of `coffee_shop`, `restaurant`, `grocery`, `online_retail`, `electronics`, `streaming`, `fitness`, `travel`
- `is_online` INTEGER – 0 or 1
- `refund_policy` TEXT – one plain sentence

**subscriptions**
- `subscription_id` TEXT PRIMARY KEY – e.g. `SUB-0001`
- `customer_id` TEXT, `card_id` TEXT, `merchant_id` TEXT
- `monthly_amount_usd` REAL
- `start_date` TEXT
- `cancelled_date` TEXT, NULL if still active

**transactions**
- `transaction_id` TEXT PRIMARY KEY – e.g. `TXN-000001`
- `card_id` TEXT, `customer_id` TEXT, `merchant_id` TEXT
- `txn_datetime` TEXT
- `amount_usd` REAL
- `currency` TEXT – always `USD`
- `channel` TEXT – `in_store`, `online` or `recurring`
- `device_id` TEXT – NULL for in-store; e.g. `DEV-0001`
- `shipping_address_id` TEXT – only for online orders of physical goods; e.g. `ADDR-0001`
- `subscription_id` TEXT – NULL unless channel is `recurring`
- `statement_date` TEXT – the statement on which this charge first appeared (all cards' statements close on the 5th of each month, so this is the next 5th after the transaction)
- `status` TEXT – `posted` or `refunded`

**shipments**
- `shipment_id` TEXT PRIMARY KEY
- `transaction_id` TEXT – references transactions
- `carrier` TEXT
- `shipped_date` TEXT, NULL if never shipped
- `expected_delivery_date` TEXT
- `delivered_date` TEXT, NULL if not delivered
- `delivery_status` TEXT – `delivered`, `in_transit`, `lost` or `not_shipped`
- `proof_of_delivery` INTEGER – 0 or 1

**refunds**
- `refund_id` TEXT PRIMARY KEY
- `transaction_id` TEXT
- `refund_date` TEXT
- `amount_usd` REAL

**disputes** – past resolved disputes plus the 30 open test cases. The correct answers are NOT stored here.
- `dispute_id` TEXT PRIMARY KEY – e.g. `DSP-0001`
- `transaction_id` TEXT, `customer_id` TEXT
- `filed_date` TEXT
- `complaint_text` TEXT – the customer's own words
- `status` TEXT – `open`, `resolved_customer`, `resolved_merchant` or `withdrawn`

## Outcomes the agent can recommend

- `file_chargeback` – the claim is valid, the evidence supports it, and it is within the time limits
- `deny` – the claim is not valid or is outside the time limits (a human always confirms)
- `request_more_info` – facts are missing that the customer can provide
- `escalate` – conflicting evidence or high risk, for example friendly-fraud signals; goes to a senior analyst

## The 30 test cases

`data/cases.csv` is the answer key. Columns: `case_id, dispute_id, transaction_id, customer_id, filed_date, complaint_text, expected_reason_code, expected_outcome, demo_case, notes`

| Category | Visa code | Cases | Expected outcomes |
|---|---|---|---|
| Duplicate charge | 12.6.1 | 4 | 3 file_chargeback (same amount minutes apart, incl. demo A), 1 request_more_info (same amount 4+ hours apart – may be two real purchases) |
| Item not received | 13.1 | 5 | 3 file_chargeback (no delivery and the expected date has passed), 1 request_more_info (proof of delivery to the customer's usual address), 1 deny (too early – expected delivery date not reached yet) |
| Charged after cancelling a subscription | 13.2 | 4 | 3 file_chargeback (charge after `cancelled_date`), 1 deny (charge was before `cancelled_date`) |
| Not as described or defective | 13.3 | 3 | 2 file_chargeback (customer contacted or returned to the merchant), 1 request_more_info (no attempt to resolve with the merchant) |
| Refund never arrived | 13.6 | 3 | 2 file_chargeback (no refund row), 1 deny (refund already posted before filing) |
| Fraud – online purchase | 10.4 | 7 | 4 file_chargeback (new device and new address, no history with the merchant), 3 escalate (friendly-fraud signals, incl. demo B) |
| Filed too late | 13.1 / 13.3 / 13.6 | 3 | 3 deny (past the time limits, incl. demo C) |
| Unclear complaint | N/A | 1 | request_more_info (the charge is from a subscription the customer may have forgotten) |
| **Total** | | **30** | **17 file_chargeback, 6 deny, 4 request_more_info, 3 escalate** |

### Demo cases (must match our slides and video)

- **A** – "I was charged twice at a coffee shop." Two identical $6.50 charges, 2 minutes apart, same card, same coffee shop. Expected: `file_chargeback`, 12.6.1.
- **B** – "I never made this $340 online order." The customer has 3 earlier undisputed orders from the same merchant, 120–365 days earlier, using the same device and shipping address. Expected: `escalate` (likely friendly fraud), 10.4.
- **C** – "I want to dispute this charge from last spring. The item never arrived." The transaction is about 150 days before the filed date, in spring 2026. Expected: `deny` (time limit), 13.1.

## Visa reason codes we use (our own summary – verify against Visa's public merchant dispute guide)

| Code | Meaning | Key evidence |
|---|---|---|
| 10.4 | Other fraud – card-absent (online) | device and address history, earlier undisputed purchases with the merchant |
| 12.6.1 | Duplicate processing | two charges, same card, merchant and amount, close in time |
| 13.1 | Merchandise or services not received | shipment record, expected delivery date |
| 13.2 | Cancelled recurring transaction | subscription cancel date compared with the charge date |
| 13.3 | Not as described or defective | customer tried to return or contact the merchant |
| 13.6 | Credit not processed | refund promised, refunds table |

## Time limits (simplified for the prototype)

- **Card network (simplified):** most disputes must be filed within 120 days of the transaction date. For 13.1, count from the expected delivery date. Verify against Visa's guide before relying on it.
- **Regulation Z, credit cards (12 CFR 1026.13):** the customer's notice must arrive within 60 days after the first statement showing the charge. The bank must acknowledge within 30 days and resolve within two complete billing cycles, and in no case later than 90 days.
- **Regulation E, debit cards (12 CFR 1005.11):** the customer's notice must arrive within 60 days after the statement first showing the error. The bank must investigate within 10 business days, or take up to 45 days (90 days for debit card purchases at a point of sale) if it gives a provisional credit within those 10 business days.

Sources: https://www.consumerfinance.gov/rules-policy/regulations/1026/13/ and https://www.consumerfinance.gov/rules-policy/regulations/1005/11/ (U.S. government text, public domain).

## Coding conventions

- Small, readable functions. Comments explain why, not what.
- Every endpoint has a Pydantic response model, field descriptions written for a non-expert (Orchestrate reads them), and an explicit `operation_id` and summary.
- Unknown IDs return 404 with a clear message. Bad input returns 422.
- All tests pass before committing.
