# DisputeDesk – Project Status

This file tracks the state of every checklist item. Update it when you fix something.

**Last updated:** 2026-11-18  
**Test suite:** 121 passed, 0 failed (`pytest -q`)

---

## A. Program requirements and submission rules

| ID | Status | Notes |
|---|---|---|
| A1 | 🟡 Partial | `bob_sessions/` folder exists but contains only `README.md`. Screenshots and exported markdown must be added by the team. |
| A2 | 🟡 Partial | `bob_sessions/` is committed in this batch. Screenshots and .md exports still needed from each team member. |
| A3 | ❌ Not done | No PNG screenshots in `bob_sessions/` yet. Team action required. |
| A4 | ❌ Not done | No exported task-history .md files in `bob_sessions/` yet. Team action required. |
| A5 | ✅ Done | Credential scan clean. Only hit is the checklist document describing the search terms. No `.env`, no API keys. |
| A6 | ✅ Done | All data is synthetic. `test_no_email_addresses` and `test_no_phone_numbers` pass. |
| A7 | ✅ Done | `docs/sources.md` now lists Reg Z, Reg E, Visa merchant disputes link, Mastercard chargeback guide link. |
| A8 | ✅ Done | No Visa or Mastercard PDFs in the repo. Only CFPB government PDFs in `data/rules/`. |
| A9 | ✅ Done | README has complete local run steps. All 121 tests pass. |

## B. Repo structure and hygiene

| ID | Status | Notes |
|---|---|---|
| B1 | ✅ Done | All required top-level directories present. |
| B2 | ✅ Done | `.gitignore` now covers `.DS_Store`. Any tracked `.DS_Store` files removed with `git rm --cached`. |
| B3 | ✅ Done | All staged and untracked files committed in this batch and pushed to origin main. |
| B4 | ✅ Done | Pushed to origin main in this batch. Verify with `git status -sb`. |
| B5 | ✅ Done | `requirements.txt` has all 6 required packages. |
| B6 | ✅ Done | `disputedesk-complete-system-reference.html` moved to `docs/`. |

## C. Synthetic data and answer key

| ID | Status | Notes |
|---|---|---|
| C1 | ✅ Done | `generate_data.py`: stdlib only, `seed(42)`, `REFERENCE_DATE=2026-10-15`, recreates DB each run. |
| C2 | ✅ Done | 8 required tables present. |
| C3 | ✅ Done | 60 customers, 25 merchants, 13 subscriptions (8 background + 5 planted), 543 transactions, 16 refunds, 30 open disputes, 22 resolved. |
| C4 | ✅ Done | 30 rows, correct columns, outcomes 17/4/6/3 (file_chargeback/request_more_info/deny/escalate). |
| C5 | ✅ Done | Demo A=DSP-0021 12.6.1 file_chargeback, B=DSP-0046 10.4 escalate, C=DSP-0049 13.1 deny. `test_demo_cases` passes. |
| C6 | ✅ Done | `cases.csv` only read by `/api/evaluation` and test files, never by `/tools` endpoints. |
| C7 | ✅ Done | 27 data tests pass. `data/README.md` exists. |

## D. Rules and knowledge sources

| ID | Status | Notes |
|---|---|---|
| D1 | ✅ Done | Reg Z and Reg E PDFs in `data/rules/`. |
| D2 | ✅ Done | `agent/knowledge/disputedesk_card_rules_summary.txt` committed in this batch. |
| D3 | ✅ Done | `docs/sources.md` lists all 4 sources including Visa and Mastercard links. |

## E. Agent tools

| ID | Status | Notes |
|---|---|---|
| E1–E6 | ✅ Done | All 6 original tool endpoints working. 30/30 recommendation accuracy. |
| E7 | ✅ Done | `/health` returns `{"status":"ok","database":"connected"}`. |
| E8 | ✅ Done | DB opened read-only via SQLite URI `?mode=ro`. |
| — | ✅ Done | 7th tool `record_letter_draft` added (`POST /tools/disputes/{dispute_id}/letter-draft`). |

## F. watsonx Orchestrate connection files

| ID | Status | Notes |
|---|---|---|
| F1 | ✅ Done | `export_openapi.py` updated — `EXPECTED_TOOLS` now has 7 tools. Validation and 3.0.3 export unchanged. |
| F2 | ⚠️ Action needed | `agent/disputedesk_tools_openapi.json` has stale tunnel address. Re-run `python agent/export_openapi.py --server-url https://CURRENT.trycloudflare.com` and re-import in Orchestrate before each demo session. |
| F3 | ✅ Done | All 5 instruction files correct. `instructions_evidence.txt` has "MEANING OF history_fits_claim". `instructions_letter_writer.txt` has ID-labelling rule, duplicate-only rule, and `record_letter_draft` call instruction. `instructions_supervisor.txt` shows "Draft letter for your review", never says letter was sent. |
| F4 | ✅ Done | `instructions_backup_single_agent.txt` calls `recommend_outcome` tool at step 7 and uses its result exactly. |
| F5 | ✅ Done | `ORCHESTRATE_SETUP.md` updated: specifies GPT-OSS 120B, 7 tools table, re-import steps, full test checklist. |
| F6 | ✅ Done | README updated: port 8000, tunnel command, export command, re-import-after-restart note, ad-blocker warning in troubleshooting. |

## G. Dashboard backend

| ID | Status | Notes |
|---|---|---|
| G1–G12 | ✅ Done | All endpoints implemented and tested. 36 API tests pass. |
| — | ✅ Done | `record_letter_draft` mapped to "Letter" stage in `_STAGE`. `letters` table added to `activity.db`. Latest letter included in `/api/cases/{dispute_id}`. |

## H. Dashboard UI

| ID | Status | Notes |
|---|---|---|
| H1–H4 | ✅ Done | Served at `/`, overview tiles, charts, case queue, case detail all present. |
| H5 | ✅ Done | `ORCHESTRATE_CHAT_URL` set to `https://ap-south-1.dl.watson-orchestrate.ibm.com/chat` in `ui/config.js`. |
| H6 | ✅ Done | "Letter" pipeline stage lights up when `record_letter_draft` is called. "Draft letter for review" card shown on case detail page when a draft exists. |
| H7–H8 | ✅ Done | Audit log with dispute filter, synthetic-data banner, responsive layout. |
| H9 | 👤 Manual | Optional embedded chat. Team to configure if desired. |
| H10 | ✅ Done | `TestDashboardUI` passes. |

## I. Testing, accuracy and governance

| ID | Status | Notes |
|---|---|---|
| I1 | ✅ Done | 121 passed, 0 failed. |
| I2 | ✅ Done | 30/30 recommendation accuracy. |
| I3 | ❌ Not done | End-to-end agent accuracy run through Orchestrate not yet recorded. Team action. |
| I4 | ❌ Not done | Time-per-case measurement not yet written up. Team action. |
| I5 | ❌ Not done | Governance write-up not yet in `docs/`. Team action. |
| I6 | ❌ Not done | Usability check not yet done. Team action. |

## J. Documentation and submission content

| ID | Status | Notes |
|---|---|---|
| J1 | ✅ Done | README has architecture, setup, run order, dashboard address (`http://localhost:8000`), tools table, dashboard API table, Orchestrate section, re-import instructions, troubleshooting. |
| J2 | ❌ Not done | Architecture diagram (`.png` or Mermaid) not yet in `docs/`. |
| J3 | ❌ Not done | Problem/solution statement not yet in `docs/`. |
| J4 | ❌ Not done | Technology statement not yet in `docs/`. |
| J5 | ❌ Not done | Video script not yet in `docs/`. YouTube link not in README. |
| J6 | 👤 Manual | Solution Design Guide slides. |
| J7 | 👤 Manual | Final submission on participant platform. |

## K. Outside the repo

All K items are 👤 manual (confirmed by the team, cannot be verified from the repo).

| ID | Notes |
|---|---|
| K1–K4 | Specialist agents live; supervisor and backup to deploy; empty duplicate Intake Agent to delete. |
| K5 | ⚠️ Re-import tools in Orchestrate with the current tunnel address before every demo session. |
| K6–K10 | Demo environment, test checklist, teammate bob_sessions, monday.com, mentor session. |

---

## Still outstanding (priority order)

1. **A3/A4** – Add Bob screenshots and exported .md files to `bob_sessions/`. Every teammate.
2. **K5/F2** – Re-export with the live tunnel and re-import in Orchestrate before each demo.
3. **I3** – Run all 30 disputes through the supervisor, record accuracy, write up in `docs/`.
4. **I4/I5** – Time-per-case measurement; governance write-up.
5. **J2** – Architecture diagram in `docs/`.
6. **J3/J4** – Problem/solution statement and technology statement in `docs/`.
7. **J5** – Video script; record and upload video; add YouTube link to README.
8. **I6** – Usability check with 2–3 people.
