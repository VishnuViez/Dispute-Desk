# DisputeDesk – Evaluation

## 1. Automated accuracy: recommend_outcome (backend)

The plain-code `recommend_outcome` endpoint is tested against the 30-case answer key on every `pytest` run.

```
pytest backend/tests/test_recommendation.py -v
```

Result: **30/30** (verified). This is the accuracy of the decision rules in code, independent of the AI.

---

## 2. End-to-end agent accuracy: through watsonx Orchestrate

This measures how often the full multi-agent system — including the language model's reason-code classification — matches the answer key.

### Method

1. Start the API (`uvicorn backend.app.main:app --port 8000`) and confirm `/health` shows `"database": "connected"`.
2. Start the tunnel and re-import the tools in Orchestrate with the current tunnel address.
3. For each of the 30 disputes in `data/cases.csv` (DSP-0021 to DSP-0052), type `Investigate dispute <ID>` in the DisputeDesk supervisor chat.
4. Do not correct the agent, even if the recommendation looks wrong: we are measuring what it produces. Its `recommend_outcome` call is saved automatically, so there is no need to approve. Start a new chat for each case so one case does not influence the next.
5. The `recommend_outcome` tool call is logged automatically. `GET /api/evaluation` compares the saved recommendations to `data/cases.csv` and returns accuracy.

### Reading the results

After running all 30 cases, run the evaluation report script (see Section 5), which calls `GET /api/evaluation` and writes `docs/evaluation_results.md`.

Alternatively, open the dashboard at `http://localhost:8000` and check the "Agent Accuracy" card on the Overview tab.

### Results

Run on 18 Nov 2026: all 30 disputes through the live DisputeDesk supervisor, one new chat per case, no corrections. The agents also chose the correct Visa reason code in 30 of 30 cases.

| Metric | Value |
|---|---|
| Total cases run | 30 |
| Correct | 30 |
| Accuracy | 100% |

See `docs/evaluation_results.md` for the per-case breakdown.

---

## 3. Time-per-case comparison

**Goal:** measure how long it takes a team member to investigate 5 cases by hand (using the transaction data directly) vs with DisputeDesk.

### Cases to time

Pick 5 cases from `data/cases.csv` that cover different reason codes — one per category is ideal. Suggested: DSP-0021 (12.6.1), DSP-0026 (13.1), DSP-0030 (13.2), DSP-0036 (13.3), DSP-0046 (10.4).

### Procedure

For each case, record:
- **Start time**: when you read the dispute ID.
- **End time**: when you have written down your recommended outcome.
- Do the manual run first (look up the dispute in the data, check the transaction, check the shipment, check the deadlines by hand).
- Do the DisputeDesk run second (type `Investigate dispute <ID>` in Orchestrate, read the result, type `approve`).

| Dispute | Manual time (s) | With DisputeDesk (s) | Manual outcome | DisputeDesk outcome | Match? |
|---|---|---|---|---|---|
| DSP-0021 | [to fill] | [to fill] | [to fill] | [to fill] | [to fill] |
| DSP-0026 | [to fill] | [to fill] | [to fill] | [to fill] | [to fill] |
| DSP-0030 | [to fill] | [to fill] | [to fill] | [to fill] | [to fill] |
| DSP-0036 | [to fill] | [to fill] | [to fill] | [to fill] | [to fill] |
| DSP-0046 | [to fill] | [to fill] | [to fill] | [to fill] | [to fill] |

Average manual time: **[to fill]** s. Average with DisputeDesk: **[to fill]** s.

---

## 4. Usability check

**Goal:** confirm that the dashboard and the Orchestrate chat are usable by someone who has not seen DisputeDesk before.

### Testers

3 people outside the development team. Ideally: one team member who did not build the UI, one person from a different team, one person with no technical background.

### Tasks

Give each tester the following tasks without explaining how to do them:

1. Find the dispute with the highest `days_to_deadline` value in the case queue.
2. Open DSP-0021. Read the complaint and describe what it is about.
3. Use the "Investigate with DisputeDesk" button (or type the prompt in Orchestrate) and describe what the agent recommended and why.
4. Record an "approve" decision for DSP-0021 using the analyst name "tester".
5. Find the draft letter for DSP-0021 on the case page.
6. Open the Audit Log tab and find the entry for DSP-0021.

### Observation template

For each tester, record:

| Task | Completed? | Time (s) | Errors or confusion | Quotes |
|---|---|---|---|---|
| 1. Find highest deadline | [to fill] | | | |
| 2. Read complaint | [to fill] | | | |
| 3. Investigate in Orchestrate | [to fill] | | | |
| 4. Approve decision | [to fill] | | | |
| 5. Find draft letter | [to fill] | | | |
| 6. Audit log | [to fill] | | | |

### Fixes made after usability check

| Issue observed | Fix made | Commit |
|---|---|---|
| [to fill] | [to fill] | [to fill] |

---

## 5. Evaluation report script

`scripts/evaluation_report.py` calls `GET /api/evaluation` on the running local API and writes `docs/evaluation_results.md` with the accuracy and per-case breakdown.

```bash
# with the API running on port 8000:
python scripts/evaluation_report.py
```

Output: `docs/evaluation_results.md`.
