# DisputeDesk in watsonx Orchestrate – Multi-Agent Setup

DisputeDesk is one **supervisor** agent that hands work to **four specialist agents**. There is also a **single-agent backup** for demo day. This page has every value to paste and every test to run.

## The team of agents

| Build order | Agent name | Job | Tools | Knowledge | Instructions file |
|---|---|---|---|---|---|
| 1 | DisputeDesk Intake Agent | Classifies the dispute: reason code and key IDs | get_dispute, get_transaction | – | `instructions_intake.txt` |
| 2 | DisputeDesk Evidence Investigator | Gathers the facts for the reason code | get_transaction, get_customer_history, get_merchant_info | – | `instructions_evidence.txt` |
| 3 | DisputeDesk Compliance Agent | Checks deadlines and cites the rule | check_deadline | 3 rule files | `instructions_compliance.txt` |
| 4 | DisputeDesk Letter Writer | Writes the letter after approval | – | – | `instructions_letter_writer.txt` |
| 5 | **DisputeDesk** (supervisor) | Talks to the analyst, delegates, decides, waits for approval | – (agents 1–4 as collaborators) | – | `instructions_supervisor.txt` |
| 6 | DisputeDesk Backup | Does everything alone, in case the team misbehaves on demo day | all 5 tools | 3 rule files | `instructions_backup_single_agent.txt` |

Build the specialists before the supervisor. A collaborator must already exist (and be deployed) before you can add it.

## Before you start

1. Run the Bob prompt that adds `check_deadline` and `agent/export_openapi.py`.
2. Start the API and the tunnel, then run the export with the tunnel address:
   - Terminal 1: `source .venv/bin/activate` then `uvicorn backend.app.main:app --port 8000`
   - Terminal 2: `cloudflared tunnel --url http://localhost:8000`
   - Terminal 3: `python agent/export_openapi.py --server-url https://YOUR-ADDRESS.trycloudflare.com`
3. Check `https://YOUR-ADDRESS.trycloudflare.com/health` in a browser. It should show `"database": "connected"`.
4. If the knowledge upload rejects the PDF names because of the special characters, rename them to `reg_z_1026_13.pdf` and `reg_e_1005_11.pdf`.

## Steps that are the same for every agent

1. On the Orchestrate home page, click **Create agent** → **Create from scratch**.
2. Enter the **Name** and **Description** below and click **Create**.
3. In the agent editor, pick the **Model**. Use an IBM Granite model if one is listed.
4. If you see an **Agent style** option, leave it on **Default**.
5. Open `agent/<instructions file>`, select all (⌘A), copy, and paste it into **Behavior → Instructions**.
6. Add the tools or knowledge listed for that agent. Leave the others empty.
7. Test it in the **Preview** chat on the right using the tests below. Click **How did I get this response?** to see the tool calls.
8. Click **Deploy**.

### Adding tools (import once, reuse everywhere)

- **First agent with tools (Intake):** go to **Toolset → Add tool → Add from file or MCP server**, import `agent/disputedesk_tools_openapi.json`, and select **all 5** tools. This saves all 5 in your Orchestrate account. Then remove the tools this agent does not need (keep only get_dispute and get_transaction).
- **Every later agent:** go to **Toolset → Add tool → Add from local instance**, tick only the tools listed for that agent, and click **Add to agent**.
- If your screen has a separate **Tools** page in the left menu, you can import the file there once instead.

### Adding knowledge (Compliance Agent and Backup)

Upload these three files and paste the description:
- `data/rules/` Reg Z 1026.13 PDF
- `data/rules/` Reg E 1005.11 PDF
- `agent/knowledge/disputedesk_card_rules_summary.txt`

Knowledge description:
```
Card dispute rules: Regulation Z 1026.13 (credit card billing errors), Regulation E 1005.11 (debit card error resolution) and the DisputeDesk team's own summary of Visa reason codes, required evidence and time limits. Search it to find and cite the rule behind a recommendation.
```

---

## Agent 1 – DisputeDesk Intake Agent

**Name:** `DisputeDesk Intake Agent`

**Description** (the supervisor reads this to decide when to call it):
```
Classifies a card dispute. Given a dispute ID such as DSP-0021, it reads the customer's complaint and the disputed transaction and returns the Visa reason code, the key IDs (transaction, customer, merchant), card type and anything missing. Use it first for every new dispute. It does not check deadlines, gather other evidence or decide outcomes.
```

**Tools:** get_dispute, get_transaction · **Knowledge:** none · **Instructions:** `instructions_intake.txt`

**Tests:**

| Type in Preview | Expect |
|---|---|
| `Classify dispute DSP-0021` | reason_code 12.6.1, transaction TXN-000502, customer CUST-0001, merchant MERCH-001 |
| `Classify dispute DSP-0046` | reason_code 10.4 |
| `Classify dispute DSP-0036` | reason_code 13.3, customer_contacted_merchant: no |
| `Classify dispute DSP-0052` | reason_code N/A, reason_clear: no |

## Agent 2 – DisputeDesk Evidence Investigator

**Name:** `DisputeDesk Evidence Investigator`

**Description:**
```
Gathers evidence for a card dispute that has already been classified. Given a transaction_id, customer_id, merchant_id and Visa reason code, it looks up duplicate charges, shipment and delivery records, subscription cancellation dates, refunds and the customer's purchase history (friendly-fraud signals), and reports facts only. Use it after the Intake Agent. It does not check deadlines or decide outcomes.
```

**Tools:** get_transaction, get_customer_history, get_merchant_info · **Knowledge:** none · **Instructions:** `instructions_evidence.txt`

**Tests:**

| Type in Preview | Expect |
|---|---|
| `Gather evidence: transaction TXN-000502, customer CUST-0001, merchant MERCH-001, reason code 12.6.1` | one duplicate about 2 minutes apart |
| `Gather evidence: transaction TXN-000531, customer CUST-0024, merchant MERCH-009, reason code 10.4` | prior_undisputed_with_merchant 3, same device 3, same address 3 |
| `Gather evidence: transaction TXN-000512, customer CUST-0008, merchant MERCH-010, reason code 13.1` | proof_of_delivery true |
| `Gather evidence: transaction TXN-000523, customer CUST-0019, merchant MERCH-008, reason code 13.6` | a refund is listed |

## Agent 3 – DisputeDesk Compliance Agent

**Name:** `DisputeDesk Compliance Agent`

**Description:**
```
Checks time limits and rules for a card dispute. Given a dispute ID and Visa reason code, it runs the check_deadline tool (card network 120-day limit, Regulation Z for credit cards, Regulation E for debit cards) and searches the rules knowledge to quote the rule that applies, with its source. Use it once the reason code is known. It does not gather evidence or decide outcomes.
```

**Tools:** check_deadline · **Knowledge:** the 3 rule files (see above) · **Instructions:** `instructions_compliance.txt`

**Tests:**

| Type in Preview | Expect |
|---|---|
| `Check deadlines for dispute DSP-0049, reason code 13.1` | within_time_limits: no, with a time-limit rule cited |
| `Check deadlines for dispute DSP-0029, reason code 13.1` | too_early: yes |
| `Check deadlines for dispute DSP-0021, reason code 12.6.1` | within_time_limits: yes, regulation Reg Z |

## Agent 4 – DisputeDesk Letter Writer

**Name:** `DisputeDesk Letter Writer`

**Description:**
```
Drafts customer letters and chargeback summaries for card disputes after a human analyst has approved the decision. Use it only when DisputeDesk has an approved outcome to communicate.
```

**Tools:** none · **Knowledge:** none · **Instructions:** `instructions_letter_writer.txt`

**Test:** `Write the letter. Dispute DSP-0021, outcome file_chargeback, reason code 12.6.1, facts: two $6.50 charges at Bramble & Bean Coffee on 2026-10-01, 2 minutes apart.` Expect a letter signed "Card Disputes Team" plus a chargeback summary.

## Agent 5 – DisputeDesk (supervisor)

**Name:** `DisputeDesk`

**Description:**
```
Investigates credit and debit card disputes for bank dispute analysts. Given a dispute ID such as DSP-0021, it coordinates specialist agents to classify the dispute, gather evidence and check deadlines and rules, then recommends file_chargeback, deny, request_more_info or escalate with a confidence score. A human analyst makes every final decision.
```

**Tools:** none · **Knowledge:** none · **Instructions:** `instructions_supervisor.txt`

**Collaborators:** go to **Toolset → Agents → Add agent → Add from local instance**, tick all four specialists (Intake Agent, Evidence Investigator, Compliance Agent, Letter Writer), and click **Add to agent**.

**Welcome message:**
```
Hi, I'm DisputeDesk. Give me a dispute ID (like DSP-0021) and my team of specialist agents will investigate it and recommend what to do. You make the final decision.
```

**Starter prompts:** `Investigate dispute DSP-0021` · `Investigate dispute DSP-0046` · `Investigate dispute DSP-0049`

**Model note:** if the supervisor skips specialists or calls them in the wrong order, try a larger model for the supervisor only. Keep Granite on the specialists, and write down which models you used for the technology statement.

**Tests:** run the full checklist below. "How did I get this response?" should show Intake → Evidence Investigator → Compliance.

## Agent 6 – DisputeDesk Backup (single agent)

**Name:** `DisputeDesk Backup`

**Description:** the same as the supervisor's, ending with "(single-agent backup)".

**Tools:** all 5 · **Knowledge:** the 3 rule files · **Collaborators:** DisputeDesk Letter Writer · **Instructions:** `instructions_backup_single_agent.txt`

Run the same checklist. If the supervisor team misbehaves on demo day, use this one.

---

## Full test checklist (supervisor and backup)

Type `Investigate dispute <ID>`.

| Dispute | What it tests | Expected recommendation | Reason code |
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

**Hand-off test:** after DSP-0021, reply `approve`. The Letter Writer's letter should appear.

The answer key for all 30 cases is in `data/cases.csv`.

## If something goes wrong

- **Tool calls fail or time out.** Check that `uvicorn` and `cloudflared` are both running. A new tunnel gets a new address, so re-run the export and import the tools again.
- **The supervisor answers without asking its specialists.** Check that all four are listed under Toolset → Agents and that each one is deployed. Then try a larger model for the supervisor.
- **A specialist returns the wrong format.** Test that specialist alone in its own Preview and fix its instructions first.
- **"Not found" errors.** Only DSP-0021 to DSP-0052 are open test cases.
