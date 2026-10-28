# DisputeDesk

DisputeDesk is a prototype AI agent that helps a bank's card dispute analyst investigate credit and debit card disputes. Given a customer's complaint, it picks the card-network reason code, checks deadlines, gathers evidence through backend tools, and recommends one of four outcomes (file chargeback, deny, request more info, or escalate) with a confidence score and the rule it relied on. A human analyst always makes the final decision.

Built for the IBM SkillsBuild AI Experiential Learning Lab (US Fall 2026), track: Revolutionizing Banking & Financial Services.

## Setup

**1. Create a virtual environment**

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

**2. Install requirements**

```bash
pip install -r requirements.txt
```

**3. Generate synthetic data**

```bash
python data/generate_data.py
```

**4. Start the API**

```bash
# macOS / Linux
uvicorn backend.app.main:app --reload

# Windows
uvicorn backend.app.main:app --reload
```

The API will be available at http://127.0.0.1:8000. Interactive docs at http://127.0.0.1:8000/docs.

**5. Run tests**

```bash
pytest
```

## Tools API

All endpoints are under `/tools`. The API returns JSON. Unknown IDs return `404`; malformed input returns `422`.
Interactive docs: http://127.0.0.1:8000/docs · OpenAPI spec: http://127.0.0.1:8000/openapi.json

---

### `GET /tools/disputes/{dispute_id}` — `get_dispute`

Look up a dispute and find out whether the card is credit or debit.

**Example request**
```
GET /tools/disputes/DSP-0021
```

**Example response** _(shortened)_
```json
{
  "dispute_id": "DSP-0021",
  "transaction_id": "TXN-000502",
  "customer_id": "CUST-0001",
  "filed_date": "2026-10-10",
  "complaint_text": "I was charged twice at a coffee shop. Both charges are $6.50 and I only bought one drink.",
  "status": "open",
  "card_type": "credit"
}
```

---

### `GET /tools/transactions/{transaction_id}` — `get_transaction`

Full transaction details including merchant name, card type, subscription dates, refunds, and any duplicate charges within 24 hours.

**Example request**
```
GET /tools/transactions/TXN-000502
```

**Example response** _(shortened)_
```json
{
  "transaction_id": "TXN-000502",
  "merchant_name": "Bramble & Bean Coffee",
  "merchant_category": "coffee_shop",
  "txn_datetime": "2026-10-01T09:14:00",
  "amount_usd": 6.5,
  "channel": "in_store",
  "card_type": "credit",
  "refunds": [],
  "possible_duplicates": [
    { "transaction_id": "TXN-000501", "txn_datetime": "2026-10-01T09:14:00", "minutes_apart": 2.0 }
  ]
}
```

---

### `GET /tools/customers/{customer_id}/history` — `get_customer_history`

Account open date and up to 50 recent transactions (newest first). Add `?merchant_id=…&transaction_id=…` to also get `friendly_fraud_signals`.

**Example request — with fraud signals**
```
GET /tools/customers/CUST-0024/history?merchant_id=MERCH-009&transaction_id=TXN-000531
```

**Example response** _(shortened)_
```json
{
  "customer_id": "CUST-0024",
  "account_open_date": "2024-03-10",
  "transactions": [ "…up to 50 items…" ],
  "friendly_fraud_signals": {
    "prior_undisputed_with_merchant": 3,
    "same_device_count": 3,
    "same_address_count": 3,
    "device_seen_before": true,
    "address_seen_before": true,
    "prior_disputes_count": 2,
    "prior_disputes_lost": 2,
    "summary": "This customer has 3 earlier undisputed purchase(s) at this merchant …"
  }
}
```

---

### `GET /tools/merchants/{merchant_id}` — `get_merchant_info`

Merchant name, category, online flag, and refund policy. Add `?transaction_id=…` to include the shipment record for that order.

**Example request — with shipment**
```
GET /tools/merchants/MERCH-008?transaction_id=TXN-000508
```

**Example response** _(shortened)_
```json
{
  "merchant_id": "MERCH-008",
  "name": "Veldt Supply Co.",
  "category": "online_retail",
  "is_online": true,
  "refund_policy": "Returns accepted within 30 days; customer pays return shipping.",
  "shipment": {
    "carrier": "UPS",
    "shipped_date": "2026-08-12",
    "expected_delivery_date": "2026-08-20",
    "delivered_date": null,
    "delivery_status": "lost",
    "proof_of_delivery": false
  }
}
```
