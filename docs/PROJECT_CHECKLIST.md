# DisputeDesk – Project Checklist

Master checklist for the IBM SkillsBuild AI Experiential Learning Lab (Fall 2026) submission. It covers the program rules, everything planned for DisputeDesk, and the items that live outside this repo.

**How to use it:** check each item against the repo and report a status:

- ✅ **Done**: verified, with evidence (file path, test name or command output)
- 🟡 **Partial**: started but incomplete; say what is missing
- ❌ **Not done**: nothing found
- 👤 **Manual**: cannot be verified from the repo (for example, something in watsonx Orchestrate). The team confirms it.

Never mark an item ✅ without evidence. If unsure, use 🟡 or 👤.

---

## A. Program requirements and submission rules (from the lab guide)

- [ ] **A1** IBM Bob is used as the core build tool. *Verify:* `bob_sessions/` has evidence for every build task.
- [ ] **A2** A folder named exactly `bob_sessions/` exists at the repo root and is committed. The old `bob-reports/` folder is gone.
- [ ] **A3** For **every** Bob task related to the project there is a **screenshot (PNG)** of the task session consumption summary. *Verify:* list and count the files.
- [ ] **A4** For **every** Bob task there is also the **exported task history markdown (.md)**, via the "Export task history" icon. *Verify:* each screenshot has a matching .md file.
- [ ] **A5** **No credentials anywhere** in the repo or in the exported Bob markdown: no API keys, tokens, passwords, IBM Cloud keys or `.env` files. The guide says IBM will deactivate accounts if any are found. *Verify:* search for `apikey`, `api_key`, `API_KEY`, `token`, `Bearer`, `password`, `secret`, `IBM_CLOUD`, and long random-looking strings.
- [ ] **A6** **Synthetic data only.** No real names, emails, phone numbers, card numbers or street addresses. *Verify:* data tests plus a quick scan of `data/`.
- [ ] **A7** Every outside source is listed in `docs/sources.md` with URL, date accessed, license/terms and what it was used for.
- [ ] **A8** Visa and Mastercard documents are **not copied** into the repo (links only in `docs/sources.md`).
- [ ] **A9** The solution **runs locally** (lab cloud accounts don't support hosting), and the README has complete local run steps.

## B. Repo structure and hygiene

- [ ] **B1** Layout matches `docs/PROJECT_BRIEF.md`: `README.md`, `requirements.txt`, `.gitignore`, `pytest.ini`, `docs/`, `data/`, `backend/`, `agent/`, `ui/`, `bob_sessions/`.
- [ ] **B2** `.gitignore` covers `.venv/`, `__pycache__/`, `.pytest_cache/`, `.env`, `.DS_Store` and `data/activity.db`, and does **not** ignore `data/disputedesk.db`.
- [ ] **B3** **No uncommitted work.** *Verify:* `git status`, and list every modified, added, deleted or untracked file.
- [ ] **B4** **Local and GitHub are in sync** (`origin` = github.com/VishnuViez/Dispute-Desk). *Verify:* `git status -sb` shows nothing ahead or behind.
- [ ] **B5** `requirements.txt` is complete (fastapi, uvicorn[standard], pydantic>=2, pytest, httpx, openapi-spec-validator), and a fresh virtual environment can install it.
- [ ] **B6** Identify the file `disputedesk-complete-system-reference.html` at the repo root: what it is, whether it is current, and whether it should move to `docs/` or be removed. Recommend only; do not delete.

## C. Synthetic data and answer key

- [ ] **C1** `data/generate_data.py`: standard library only, `random.seed(42)`, `REFERENCE_DATE = 2026-10-15`, recreates the database on each run.
- [ ] **C2** `data/disputedesk.db` has exactly the schema in the brief: customers, cards, merchants, subscriptions, transactions, shipments, refunds, disputes.
- [ ] **C3** Row counts are in range: about 60 customers, 25 merchants, about 8 subscriptions, about 500 transactions, about 15 refunds, about 20 past disputes plus 30 open ones.
- [ ] **C4** `data/cases.csv` has 30 rows with the brief's columns, and outcomes are 17 file_chargeback / 6 deny / 4 request_more_info / 3 escalate.
- [ ] **C5** Demo cases are correct: **A** = DSP-0021 (12.6.1, file_chargeback), **B** = DSP-0046 (10.4, escalate), **C** = DSP-0049 (13.1, deny – filed too late).
- [ ] **C6** The answer key (`cases.csv`) is **never read by any `/tools` endpoint**, only by `/api/evaluation` and the tests.
- [ ] **C7** `data/tests/test_generated_data.py` passes, and `data/README.md` exists.

## D. Rules and knowledge sources

- [ ] **D1** `data/rules/` contains the Regulation Z §1026.13 and Regulation E §1005.11 PDFs.
- [ ] **D2** `agent/knowledge/disputedesk_card_rules_summary.txt` exists (our own-words Visa summary) and is committed.
- [ ] **D3** `docs/sources.md` lists Reg Z, Reg E, the Visa merchant dispute guide (link) and the Mastercard chargeback guide (link).

## E. Agent tools (`/tools`, called by watsonx Orchestrate)

Each tool must have an explicit `operation_id`, a summary, a plain-English description, a Pydantic response model with field descriptions, 404 for unknown IDs, 422 for bad input, read-only database access, and no AI calls.

- [ ] **E1** `get_dispute`: `GET /tools/disputes/{dispute_id}`
- [ ] **E2** `get_transaction`: `GET /tools/transactions/{transaction_id}`, including `possible_duplicates` within 24 hours.
- [ ] **E3** `get_customer_history`: `GET /tools/customers/{customer_id}/history`, including `friendly_fraud_signals`.
- [ ] **E4** `get_merchant_info`: `GET /tools/merchants/{merchant_id}`, including the shipment record.
- [ ] **E5** `check_deadline`: `GET /tools/disputes/{dispute_id}/deadline-check?reason_code=…`. Covers the 120-day network limit (13.1 counted from the expected delivery date), the 60-day Reg Z / Reg E notice limit, `too_early`, and bank response deadlines.
- [ ] **E6** `recommend_outcome`: `GET /tools/disputes/{dispute_id}/recommendation?reason_code=…&customer_contacted_merchant=…`. Matches the answer key on **30/30** cases (`backend/tests/test_recommendation.py`).
- [ ] **E7** `/health` returns `{"status":"ok","database":"connected"}`.
- [ ] **E8** The data database is opened **read-only** (`backend/app/db.py`).

## F. watsonx Orchestrate connection files (`agent/`)

- [ ] **F1** `agent/export_openapi.py`: produces OpenAPI **3.0.3** with exactly one server, only `/tools` paths, nullable fields converted, 422 responses removed, validated with openapi-spec-validator. `EXPECTED_TOOLS` has all **6** tools.
- [ ] **F2** `agent/disputedesk_tools_openapi.json` exists and has the 6 operationIds. **Report its server URL**; the team will check it matches the tunnel address currently running.
- [ ] **F3** All instruction files exist and are committed:
  - `instructions_intake.txt`
  - `instructions_evidence.txt`, which must include the "MEANING OF history_fits_claim" section
  - `instructions_compliance.txt`
  - `instructions_letter_writer.txt`, which must include the ID-labelling rule and the "duplicate charge only" rule
  - `instructions_supervisor.txt`, which must use `recommend_outcome`, show the "Draft letter for your review", and never say a letter was sent
- [ ] **F4** `instructions_backup_single_agent.txt` **calls `recommend_outcome`** for the final decision, like the supervisor, instead of applying the decision rules itself.
- [ ] **F5** `agent/ORCHESTRATE_SETUP.md` is **up to date**:
  - 6 tools, with `recommend_outcome` attached to the supervisor
  - model is **GPT-OSS 120B** (Granite is not selectable in the lab account)
  - knowledge is on the Compliance Agent, with renamed PDFs
  - current test checklist
  - steps to **re-import the tools whenever the tunnel address changes**
- [ ] **F6** The README's "Connect to watsonx Orchestrate" section is accurate: port **8000**, tunnel command, export command, re-import after a tunnel restart, and the note that ad blockers may block `trycloudflare.com`.

## G. Dashboard backend (`/api`, activity log)

- [ ] **G1** `data/activity.db` is created automatically, is gitignored, and has the tables `tool_calls`, `recommendations` and `decisions`.
- [ ] **G2** Middleware logs every `/tools/*` call (tool, IDs, status, duration) and never breaks a tool call (wrapped in try/except).
- [ ] **G3** `recommend_outcome` saves its result to `recommendations`.
- [ ] **G4** `GET /api/stats`
- [ ] **G5** `GET /api/cases` with filters status, card_type, reason_code, recommendation, deadline_within_days, q (search) and sort.
- [ ] **G6** `GET /api/cases/{dispute_id}` returns everything the case page needs.
- [ ] **G7** `POST /api/cases/{dispute_id}/decision`: approve / edit / override, with a reason **required** for edit and override.
- [ ] **G8** `GET /api/activity?since=…` maps stages: get_dispute and get_transaction → Intake; get_customer_history and get_merchant_info → Evidence; check_deadline → Compliance; recommend_outcome → Decision.
- [ ] **G9** `GET /api/audit` returns the merged timeline of tool calls and decisions.
- [ ] **G10** `GET /api/evaluation` returns accuracy of saved recommendations against `cases.csv`.
- [ ] **G11** `/api` routes **never** appear in the exported OpenAPI file.
- [ ] **G12** Tests cover `/api` and the middleware (`backend/tests/test_api.py`).

## H. Dashboard UI (`ui/`)

- [ ] **H1** Served by FastAPI at `/`, with StaticFiles mounted after all API routes.
- [ ] **H2** Overview: tiles, cases-by-reason-code chart, recommendations chart, agent accuracy card.
- [ ] **H3** Case queue: filters, search, sortable columns, coloured outcome badges, click a row to open the case.
- [ ] **H4** Case detail: complaint, transaction / merchant / shipment facts, fraud signals, deadline timeline, recommendation with 4 ✅/❌ checks and the rule, Approve / Edit / Override buttons (reason required), decision history.
- [ ] **H5** The "Investigate with DisputeDesk" button works, **and `ORCHESTRATE_CHAT_URL` in `ui/config.js` is filled in** with the team's Orchestrate chat link.
- [ ] **H6** Agent activity: the pipeline Intake → Evidence → Compliance → Decision → **Letter** lights up, polling every 2 seconds. **Check what lights up the "Letter" stage.** The Letter Writer agent calls no tool, so the activity log may never see it. Propose a fix, for example lighting it when an "approve" decision is saved.
- [ ] **H7** Audit log page with a dispute filter.
- [ ] **H8** Synthetic-data banner, polite empty and error states, usable on a phone.
- [ ] **H9** *(Optional)* The Orchestrate chat embedded inside the dashboard (Orchestrate: Deploy → Channels → Embedded agent).
- [ ] **H10** A test confirms `GET /` returns the dashboard.

## I. Testing, accuracy and governance

- [ ] **I1** The full test suite passes. *Verify:* run `pytest -q` and report the counts.
- [ ] **I2** `recommend_outcome` matches the answer key on 30/30 cases.
- [ ] **I3** **End-to-end agent accuracy**: all 30 cases run through the DisputeDesk agent in Orchestrate, with results recorded in `/api/evaluation` and written up in `docs/`.
- [ ] **I4** Time per case is measured, by hand compared with DisputeDesk, and written up in `docs/`.
- [ ] **I5** Governance write-up in `docs/` covering:
  - no names, ZIP codes or demographics used in decisions
  - a human makes every final decision (no automatic denial)
  - the audit log is complete
  - synthetic data only
  - deadlines and decisions are made by plain code, not AI
- [ ] **I6** A usability check was done with 2–3 people, and the main fixes were made.

## J. Documentation and submission content

- [ ] **J1** README is complete: what DisputeDesk is, architecture, setup, run API, tunnel, export, dashboard address, tests, Tools API, `/api`, Orchestrate setup, troubleshooting.
- [ ] **J2** Architecture diagram in `docs/`: Orchestrate agents ↔ tunnel ↔ FastAPI ↔ SQLite, plus the dashboard and activity log.
- [ ] **J3** **Problem and solution statement** in `docs/` (based on the checkpoint answers, updated with real results).
- [ ] **J4** **Technology statement** in `docs/` covering:
  - IBM Bob (what it built)
  - watsonx Orchestrate (supervisor and 4 collaborator agents, knowledge, OpenAPI tools)
  - **GPT-OSS 120B** as the model
  - FastAPI and SQLite
  - local run with a Cloudflare tunnel (lab accounts don't support hosting)
  - plain-code deadline and decision tools
- [ ] **J5** Video script for a demo of 3 minutes or less in `docs/`. 👤 The video is recorded and uploaded to YouTube, and its link is in the README.
- [ ] **J6** 👤 Solution Design Guide slides are filled in.
- [ ] **J7** 👤 The final submission is made on the participant platform (confirm the exact deadline).

## K. Outside the repo – team confirms (Bob marks these 👤)

- [ ] **K1** Orchestrate specialists are **Live**: DisputeDesk Intake Agent, Evidence Investigator, Compliance Agent, Letter Writer.
- [ ] **K2** **DisputeDesk supervisor**: `recommend_outcome` attached, new instructions pasted, demos A / B / C pass, **deployed**.
- [ ] **K3** **DisputeDesk Backup** (single agent) is created, tested and deployed.
- [ ] **K4** The empty duplicate "DisputeDesk Intake Agent" (0 tools) is deleted or renamed.
- [ ] **K5** Tools in Orchestrate point to the **current** tunnel address (re-imported after each tunnel restart).
- [ ] **K6** The API on port 8000 and the tunnel both run during the demo, and no ad blocker is blocking the tunnel.
- [ ] **K7** The 11-case test checklist passes in Orchestrate chat, and replying "approve" shows the draft letter.
- [ ] **K8** Every teammate has added their own Bob screenshots and exported markdown to `bob_sessions/`.
- [ ] **K9** The monday.com board is updated, and teammates are invited.
- [ ] **K10** The coach or mentor session is held, and feedback is noted.
