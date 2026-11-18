# DisputeDesk – Technology Statement

## IBM Bob

IBM Bob was used as the primary build tool throughout the project. Every major component — the synthetic data generator, the FastAPI backend, the agent instruction files, the dashboard, the deadline and recommendation logic, the OpenAPI export script, and the test suite — was built in Bob task sessions. Session screenshots and exported task history are in `bob_sessions/`.

Bob's ability to read the entire codebase and reason about interdependencies across files made it possible to build consistent, testable components in a small team. It was used not just to write code but to run the credential and synthetic-data audits, refactor the router layout, and diagnose test failures.

## watsonx Orchestrate

DisputeDesk is a **multi-agent system** in watsonx Orchestrate with one supervisor and four specialist agents:

| Agent | Role | Tools |
|---|---|---|
| DisputeDesk (supervisor) | Talks to the analyst, delegates, calls `recommend_outcome`, shows the result, waits for approval | `recommend_outcome` |
| Intake Agent | Classifies the dispute: picks the reason code and returns key IDs | `get_dispute`, `get_transaction` |
| Evidence Investigator | Gathers the evidence the reason code needs | `get_transaction`, `get_customer_history`, `get_merchant_info` |
| Compliance Agent | Checks deadlines and cites the rule, with access to the knowledge base | `check_deadline` |
| Letter Writer | Drafts the customer letter and chargeback summary after the analyst approves | `record_letter_draft` |

A sixth agent, **DisputeDesk Backup**, is a single-agent fallback that calls all tools itself in case the team misbehaves on demo day.

**Knowledge base ("DisputeDesk Card Dispute Rules"):** the Compliance Agent and the Backup have access to three files — the Regulation Z §1026.13 PDF, the Regulation E §1005.11 PDF, and the team's own plain-English summary of Visa reason codes (`agent/knowledge/disputedesk_card_rules_summary.txt`). The agents search these to quote the rule behind a recommendation.

**OpenAPI tools:** the backend is exposed to Orchestrate through a generated OpenAPI 3.0.3 file (`agent/disputedesk_tools_openapi.json`), produced by `agent/export_openapi.py`. This script pulls the spec from the running FastAPI app, filters to `/tools/*` paths only, converts nullable fields for 3.0 compatibility, removes 422 responses, injects the tunnel URL as the single server, and validates the result with `openapi-spec-validator`. The lab does not support hosting, so the API runs on a laptop and is exposed through a Cloudflare tunnel.

**"Show reasoning":** Orchestrate's reasoning view shows the supervisor delegating to Intake → Evidence Investigator → Compliance → recommend_outcome → Letter Writer in order, with every tool call and its result visible.

## The model

All agents in the team's lab instance use **GPT-OSS 120B – OpenAI (via Groq)**. Model selection is switched off by the lab account admin, so IBM Granite is not available in this instance. Orchestrate shows a notice that this model is under a third-party license; the team reviewed and accepted it.

## FastAPI, Pydantic and SQLite

The backend is a **FastAPI** application. Each tool endpoint has:
- an explicit `operation_id` (the tool name in Orchestrate),
- a `summary` and plain-English `description` (read by Orchestrate to decide when to call the tool),
- a **Pydantic v2** response model with field descriptions written for a non-expert.

All tool endpoints are read-only. They connect to `data/disputedesk.db` via the SQLite URI syntax `?mode=ro`, which prevents any accidental write. A separate writable database, `data/activity.db`, is used only by the activity log middleware and the `record_letter_draft` and `recommend_outcome` endpoints.

The middleware logs every `/tools/*` call (tool name, dispute ID, HTTP status, duration) in a try/except so a logging failure can never break a tool call.

## The dashboard

The analyst dashboard is a single HTML file (`ui/index.html`) served by FastAPI's `StaticFiles` at `/`. It uses:
- **Chart.js** (loaded from a CDN) for the reason-code bar chart and recommendation doughnut.
- Vanilla JavaScript fetch calls to the `/api/*` endpoints.
- A 2-second polling loop on the Agent Activity tab that lights up pipeline stages (Intake → Evidence → Compliance → Decision → Letter) as tool calls arrive.
- The case detail page shows the dispute, transaction, shipment, friendly-fraud signals, deadline timeline, the agent's 4-check recommendation, decision history, and — once the Letter Writer has run — the full draft letter and chargeback summary.

## Tests

The test suite has **121 tests across 6 files**:

| File | What it covers |
|---|---|
| `backend/tests/test_tools.py` | All 4 original tool endpoints: 404 for unknown IDs, correct response shapes |
| `backend/tests/test_health.py` | `/health` endpoint, connected and missing DB states |
| `backend/tests/test_deadline_and_export.py` | `check_deadline` logic and OpenAPI export validation |
| `backend/tests/test_recommendation.py` | **30/30 cases match the answer key**; demo case shapes; error responses |
| `backend/tests/test_api.py` | All `/api` dashboard endpoints, middleware, evaluation, export clean check |
| `backend/tests/test_letter.py` | `record_letter_draft` endpoint, activity stage, case detail inclusion, 7-tool export count |
| `data/tests/test_generated_data.py` | 27 data integrity checks: row counts, demo cases, no real PII, timing rules |

All tests run with `pytest` from the repo root. `recommend_outcome` is deterministic plain code, which is why 30/30 accuracy is verifiable without running the AI.
