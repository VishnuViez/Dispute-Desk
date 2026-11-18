# DisputeDesk

DisputeDesk is a prototype AI agent that helps a bank's card dispute analyst investigate credit and debit card disputes. Given a customer's complaint, it picks the card-network reason code, checks deadlines, gathers evidence through backend tools, and recommends one of four outcomes (file chargeback, deny, request more info, or escalate) with a confidence score and the rule it relied on. A human analyst always makes the final decision.

Built for the IBM SkillsBuild AI Experiential Learning Lab (US Fall 2026), track: Revolutionizing Banking & Financial Services.

---

## Architecture

```
Analyst ── Orchestrate chat ── DisputeDesk (supervisor, IBM cloud)
                                   │ hands work to 4 specialist agents
                                   │ (Intake, Evidence Investigator,
                                   │  Compliance Agent, Letter Writer)
                                   │ they call tools in disputedesk_tools_openapi.json
                                   ▼
               Cloudflare tunnel (https://….trycloudflare.com)
                                   ▼
          FastAPI on the team laptop, port 8000  (/tools/*)
                                   ▼
          data/disputedesk.db (read-only)  +  data/activity.db (activity log)
                                   ▲
   Analyst dashboard in the browser: http://localhost:8000  (/api/*)
   – the dashboard never needs the tunnel; it talks directly to localhost.
```

**Key design choices:**

- The lab's cloud accounts do not support hosting, so the API runs on a laptop and the tunnel gives Orchestrate a public HTTPS address.
- Deadlines and the final recommendation are plain code (no AI) so results are deterministic and testable.
- The dashboard reads from both the read-only SQLite data DB and a separate writable activity DB (`data/activity.db`).

Detailed docs: [`agent/ORCHESTRATE_SETUP.md`](agent/ORCHESTRATE_SETUP.md) · [`docs/sources.md`](docs/sources.md)

---

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

---

## Running

### Run order for a full session

```
Terminal 1 – start the API (port 8000)
    uvicorn backend.app.main:app --port 8000

Terminal 2 – give it a public HTTPS address (copy the *.trycloudflare.com URL)
    cloudflared tunnel --url http://localhost:8000

Terminal 3 – write the OpenAPI file Orchestrate imports (paste the tunnel URL)
    python agent/export_openapi.py --server-url https://YOUR-ADDRESS.trycloudflare.com
```

Then import `agent/disputedesk_tools_openapi.json` in Orchestrate (Toolset → Add tool → OpenAPI file).

### Analyst dashboard

Open **http://localhost:8000** in a browser on the same laptop. The dashboard does not go through the tunnel — it talks directly to the local API on port 8000.

### Run tests

```bash
pytest
```

---

## Whenever the tunnel address changes

Every time `cloudflared` restarts it gets a new address. Update Orchestrate before the next session:

1. Copy the new `https://….trycloudflare.com` address from Terminal 2.
2. Re-run the export: `python agent/export_openapi.py --server-url https://NEW-ADDRESS.trycloudflare.com`
3. In Orchestrate → Toolset → Add tool → OpenAPI file → import `agent/disputedesk_tools_openapi.json` again.
4. Check each agent still has its tools and re-deploy the supervisor.

To avoid this mid-demo, keep the tunnel window open from testing through recording.

---

## Tools API (`/tools`)

All endpoints return JSON. Unknown IDs return `404`; malformed input returns `422`.
Interactive docs: http://localhost:8000/docs · OpenAPI spec: http://localhost:8000/openapi.json

| Endpoint | Operation ID | What it does |
|---|---|---|
| `GET /tools/disputes/{dispute_id}` | `get_dispute` | Dispute record and card type |
| `GET /tools/transactions/{transaction_id}` | `get_transaction` | Transaction, duplicates within 24 h, subscription dates, refunds |
| `GET /tools/customers/{customer_id}/history` | `get_customer_history` | Purchase history and friendly-fraud signals |
| `GET /tools/merchants/{merchant_id}` | `get_merchant_info` | Merchant, refund policy and optional shipment record |
| `GET /tools/disputes/{dispute_id}/deadline-check?reason_code=…` | `check_deadline` | 120-day card network limit, 60-day Reg Z / Reg E limit, `too_early` flag |
| `GET /tools/disputes/{dispute_id}/recommendation?reason_code=…` | `recommend_outcome` | Rule-based recommendation, 4 confidence checks, key evidence |
| `POST /tools/disputes/{dispute_id}/letter-draft` | `record_letter_draft` | Saves a drafted customer letter for analyst review in the dashboard |

### Example: get_dispute

```
GET /tools/disputes/DSP-0021
```
```json
{
  "dispute_id": "DSP-0021",
  "transaction_id": "TXN-000502",
  "customer_id": "CUST-0001",
  "filed_date": "2026-10-10",
  "complaint_text": "I was charged twice at a coffee shop…",
  "status": "open",
  "card_type": "credit"
}
```

---

## Dashboard API (`/api`)

The `/api` endpoints power the analyst dashboard. They are **not** in the OpenAPI file that Orchestrate imports, so agents never see them. Activity is stored in `data/activity.db` (not committed; created automatically on first request).

| Endpoint | Description |
|---|---|
| `GET /api/stats` | Open dispute count, breakdowns by card type / recommendation / reason code, cases near the 120-day deadline |
| `GET /api/cases` | List of disputes with optional filters (`status`, `card_type`, `reason_code`, `recommendation`, `deadline_within_days`, `q`) and `sort` |
| `GET /api/cases/{dispute_id}` | Full case page: dispute, transaction, merchant, shipment, friendly-fraud signals, deadline, recommendation, decisions and the latest letter draft |
| `POST /api/cases/{dispute_id}/decision` | Record an analyst decision (`approve`, `edit`, or `override`). `reason` is required for edit and override |
| `GET /api/activity?since=<id>` | Tool calls newer than a given row ID, with a `stage` label (Intake / Evidence / Compliance / Decision / Letter) |
| `GET /api/audit` | Tool calls and analyst decisions merged into a single timeline |
| `GET /api/evaluation` | Compare saved recommendations against `data/cases.csv`; returns accuracy and per-case match results |

---

## Connect to watsonx Orchestrate

Full instructions, agent descriptions, every value to paste in and the test checklist are in **[`agent/ORCHESTRATE_SETUP.md`](agent/ORCHESTRATE_SETUP.md)**.

The team's Orchestrate instance is at `ap-south-1.dl.watson-orchestrate.ibm.com`. All agents use **GPT-OSS 120B – OpenAI (via Groq)** (the only model available in the lab account).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Orchestrate says "tool not found" or tools time out | Check that `uvicorn` and `cloudflared` are both running. Run the export and re-import the tools with the current tunnel address. |
| `GET /` returns 404 or a plain JSON error | The UI files in `ui/` were not found. Make sure you are running from the repo root and that `ui/index.html` exists. |
| `GET /health` shows `"database": "missing"` | Run `python data/generate_data.py` first to create `data/disputedesk.db`. |
| Ad blocker warning or Orchestrate can't reach the API | The browser or a corporate proxy is blocking `trycloudflare.com`. Disable the ad blocker for that domain or use a different network. The dashboard itself is not affected because it connects directly to `localhost:8000`. |
| Orchestrate answers without calling specialist agents | Check all four collaborators are listed under Toolset → Agents and that each one is deployed. Try a larger model for the supervisor only. |
| Wrong tunnel address after a restart | Re-run the export and re-import in Orchestrate (see "Whenever the tunnel address changes" above). |
| `pytest` fails with `ModuleNotFoundError` | Make sure the virtual environment is active (`source .venv/bin/activate`) and `pip install -r requirements.txt` has been run. |
