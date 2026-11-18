# DisputeDesk in watsonx Orchestrate – Setup and Current State

This page records how DisputeDesk is set up in the team's watsonx Orchestrate trial instance (`ap-south-1.dl.watson-orchestrate.ibm.com`), every value that was pasted in, and how to re-test or rebuild it.

## How the pieces connect

```
Analyst ── Orchestrate chat ── DisputeDesk (supervisor agent, IBM cloud)
                                   │ hands work to 4 specialist agents
                                   │ they call tools listed in agent/disputedesk_tools_openapi.json
                                   ▼
               Cloudflare tunnel (https://….trycloudflare.com)
                                   ▼
          FastAPI on the team laptop, port 8000 (/tools/*)
                                   ▼
          data/disputedesk.db (read-only)  +  data/activity.db (activity log)
                                   ▲
   Dashboard in the browser: http://localhost:8000 (/api/*) – no tunnel needed
```

- The lab's cloud accounts don't support hosting, so the API runs on a laptop. The tunnel lets Orchestrate (in IBM's cloud) reach it.
- The dashboard is opened at **http://localhost:8000** on the same laptop. Ad blockers sometimes block `trycloudflare.com` addresses in the browser. That only affects viewing through the tunnel, not the agents.

## Model

All agents use **GPT-OSS 120B – OpenAI (via Groq)**. This is the only model in the lab instance: model selection is switched off by the admin, so IBM Granite cannot be chosen. Orchestrate shows a notice that this model is under a third-party license, and the team agreed to use it.

## Tools (from `agent/disputedesk_tools_openapi.json`)

| Tool | What it does | Used by |
|---|---|---|
| `get_dispute` | Dispute record and card type | Intake, Backup |
| `get_transaction` | Transaction, duplicates, subscription dates, refunds | Intake, Evidence, Backup |
| `get_customer_history` | Purchase history and friendly-fraud signals | Evidence, Backup |
| `get_merchant_info` | Merchant, refund policy and shipment record | Evidence, Backup |
| `check_deadline` | Card network and Reg Z / Reg E time limits (plain code) | Compliance, Backup |
| `recommend_outcome` | The decision rules in plain code: recommendation, 4 checks, evidence | **DisputeDesk supervisor**, Backup |
| `record_letter_draft` *(once Bob adds it)* | Saves the drafted letter so the dashboard can show it and light up the "Letter" stage | Letter Writer |

## Agents

| Agent | Tools | Knowledge | Collaborators | Instructions file | Status |
|---|---|---|---|---|---|
| DisputeDesk Intake Agent | get_dispute, get_transaction | – | – | `instructions_intake.txt` | Live (v1.0.0) |
| DisputeDesk Evidence Investigator | get_transaction, get_customer_history, get_merchant_info | – | – | `instructions_evidence.txt` | Live (v1.0.0) |
| DisputeDesk Compliance Agent | check_deadline | "DisputeDesk Card Dispute Rules" | – | `instructions_compliance.txt` | Live (v1.0.0) |
| DisputeDesk Letter Writer | – (later: record_letter_draft) | – | – | `instructions_letter_writer.txt` | Live (v1.0.0) |
| **DisputeDesk** (supervisor) | recommend_outcome | – | Intake, Evidence Investigator, Compliance, Letter Writer | `instructions_supervisor.txt` | Built, **to deploy** after re-testing |
| DisputeDesk Backup | all 6 tools | "DisputeDesk Card Dispute Rules" | Letter Writer | `instructions_backup_single_agent.txt` | **To build** |

**Clean-up:** there is an empty duplicate "DisputeDesk Intake Agent" (0 tools, never deployed). Delete it. When adding collaborators, always pick the Intake Agent that has **2 tools**.

**Knowledge "DisputeDesk Card Dispute Rules"** contains three files: `reg_z_1026_13.pdf`, `reg_e_1005_11.pdf` (the two PDFs in `data/rules/`, renamed because the § and | characters cause problems) and `agent/knowledge/disputedesk_card_rules_summary.txt`. Its description:

```
Card dispute rules: Regulation Z 1026.13 (credit card billing errors), Regulation E 1005.11 (debit card error resolution) and the DisputeDesk team's own summary of Visa reason codes, required evidence and time limits. Search it to find and cite the rule behind a recommendation.
```

### Agent descriptions (Orchestrate uses these to route work)

- **Intake Agent:** Classifies a card dispute. Given a dispute ID such as DSP-0021, it reads the customer's complaint and the disputed transaction and returns the Visa reason code, the key IDs (transaction, customer, merchant), card type and anything missing. Use it first for every new dispute. It does not check deadlines, gather other evidence or decide outcomes.
- **Evidence Investigator:** Gathers evidence for a card dispute that has already been classified. Given a transaction_id, customer_id, merchant_id and Visa reason code, it looks up duplicate charges, shipment and delivery records, subscription cancellation dates, refunds and the customer's purchase history (friendly-fraud signals), and reports facts only. Use it after the Intake Agent. It does not check deadlines or decide outcomes.
- **Compliance Agent:** Checks time limits and rules for a card dispute. Given a dispute ID and Visa reason code, it runs the check_deadline tool (card network 120-day limit, Regulation Z for credit cards, Regulation E for debit cards) and searches the rules knowledge to quote the rule that applies, with its source. Use it once the reason code is known. It does not gather evidence or decide outcomes.
- **Letter Writer:** Drafts customer letters and chargeback summaries for card disputes after a human analyst has approved the decision. Use it only when DisputeDesk has an approved outcome to communicate.
- **DisputeDesk (supervisor):** Investigates credit and debit card disputes for bank dispute analysts. Given a dispute ID such as DSP-0021, it coordinates specialist agents to classify the dispute, gather evidence and check deadlines and rules, then recommends file_chargeback, deny, request_more_info or escalate with a confidence score. A human analyst makes every final decision.
- **DisputeDesk Backup:** the same as the supervisor, ending with "(single-agent backup)".

**Supervisor welcome message:** "Hi, I'm DisputeDesk. Give me a dispute ID (like DSP-0021) and my team of specialist agents will investigate it and recommend what to do. You make the final decision."
**Starter prompts:** `Investigate dispute DSP-0021` · `Investigate dispute DSP-0046` · `Investigate dispute DSP-0049`

## What we learned while testing (already in the instruction files)

- The supervisor model did not apply a long list of decision rules reliably (demo B came back as file_chargeback, then request_more_info, instead of escalate). The decision rules were therefore moved into plain code (`recommend_outcome`). The supervisor and the backup now present its result exactly.
- The Evidence Investigator first said "history fits the claim" for demo B. A "MEANING OF history_fits_claim" section fixed it.
- The Letter Writer first labelled the dispute ID as a transaction ID and disputed both coffee charges. Two rules fixed it: label IDs correctly, and dispute only the duplicate.
- The supervisor first replied "Letter Sent" without showing the letter. It must now copy the draft under "Draft letter for your review" and never say a letter was sent.

## How to deploy an agent (Orchestrate UI)

1. Open the agent → **Deploy** (top bar) → **Deploy to Live**.
2. **Create new version**: enter a name (for example `v2 recommend_outcome`) and a number (for example `1.1.0`) → **Create**.
3. Select the version → **Deploy**. Check the pre-deployment summary (tools and collaborators) → **Deploy**.
4. A deployed agent keeps a snapshot of its tools and collaborators. After changing them, deploy again.

## When the tunnel address changes (every time cloudflared restarts)

1. Start the API: `uvicorn backend.app.main:app --port 8000` (from the repo folder, with `.venv` active).
2. Start the tunnel: `cloudflared tunnel --url http://localhost:8000`, and copy the new `https://….trycloudflare.com` address.
3. Re-export: `python agent/export_openapi.py --server-url https://NEW-ADDRESS.trycloudflare.com`
4. In Orchestrate, import `agent/disputedesk_tools_openapi.json` again (Toolset → Add tool → OpenAPI) so every tool uses the new address. Then check each agent still has its tools, and deploy again.

To avoid this before the demo, keep the tunnel window open from testing through recording the video.

## Test checklist (supervisor and backup)

Type `Investigate dispute <ID>` in the agent's chat. "Show reasoning" should show Intake → Evidence Investigator → Compliance → recommend_outcome.

| Dispute | What it tests | Expected | Reason code |
|---|---|---|---|
| DSP-0021 | Demo A – charged twice, 2 minutes apart | file_chargeback | 12.6.1 |
| DSP-0046 | Demo B – $340 order, 3 earlier orders with same device and address | escalate | 10.4 |
| DSP-0049 | Demo C – about 150 days old | deny (too late) | 13.1 |
| DSP-0024 | Same amount, 5 hours apart | request_more_info | 12.6.1 |
| DSP-0029 | Expected delivery date not reached | deny (too early) | 13.1 |
| DSP-0028 | Carrier has proof of delivery | request_more_info | 13.1 |
| DSP-0033 | Charge was before the cancellation | deny | 13.2 |
| DSP-0036 | Customer never contacted the merchant | request_more_info | 13.3 |
| DSP-0039 | Refund already posted | deny | 13.6 |
| DSP-0040 | New device and new address, no history | file_chargeback | 10.4 |
| DSP-0052 | Vague complaint, forgotten subscription | request_more_info | N/A |

**Hand-off test:** after DSP-0021, reply `approve`. The answer must show "Draft letter for your review" with the letter and a chargeback summary for TXN-000502 ($6.50 only).

**Full accuracy run:** run all 30 disputes (DSP-0021 to DSP-0052, from `data/cases.csv`) through the supervisor. Every `recommend_outcome` call is saved, so `GET /api/evaluation` and the dashboard's accuracy card show the agents' score against the answer key automatically.

## Optional: chat inside the dashboard

In Orchestrate, open the supervisor → **Deploy** → Channels → **Embedded agent** to get a code snippet that embeds the DisputeDesk chat in a web page. It may require security settings. Until then, the dashboard's "Investigate with DisputeDesk" button opens the Orchestrate chat in a new tab.
