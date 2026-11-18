# DisputeDesk – Video Script (≤ 3 minutes)

**Total runtime:** 3:00  
**Format:** screen recording with voice-over. No cuts between demo steps — keep the browser visible throughout.

---

## 0:00 – 0:20 | The problem

**On screen:** a simple slide or plain text: "15–25 disputes per day. Dozens of reason codes. Strict deadlines. Friendly fraud."

**Voice-over:**

> "Every day, dispute analysts read dozens of card-dispute complaints, pick the right reason code from a long list, check strict legal deadlines, spot friendly-fraud signals buried in transaction history, and write decision letters — all manually. One missed deadline or overlooked refund record can cost the bank or the customer money."

---

## 0:20 – 0:40 | User and solution

**On screen:** the analyst dashboard at `http://localhost:8000`. The case queue shows 30 open disputes with coloured outcome badges, days-to-deadline counts, and a "Deadlines at Risk" tile.

**Voice-over:**

> "DisputeDesk is an AI agent built on IBM watsonx Orchestrate. Maria, a dispute analyst, opens the dashboard, sees all open cases at a glance — which are near their 120-day deadline, what the agent recommends — and can jump straight into an investigation. She makes every final decision; the agent does the research."

---

## 0:40 – 1:10 | Demo B – DSP-0046 (friendly fraud → escalate)

**On screen:** click the "Agent Activity" tab, then switch to the Orchestrate chat tab.

**Voice-over:**

> "Let's start with the tricky one. Demo B: a customer says they never made a $340 online order."

Type `Investigate dispute DSP-0046` and press Enter. Switch back to the dashboard's Agent Activity tab.

**On screen:** the pipeline lights up — Intake → Evidence → Compliance → Decision — as the tool calls arrive (polling every 2 seconds).

**Voice-over:**

> "The supervisor delegates to four specialist agents in order. The Intake Agent classifies it as reason code 10.4 — card-absent fraud. The Evidence Investigator finds three earlier undisputed orders at the same merchant from the same device and address. The Compliance Agent confirms it is within time limits and cites Reg Z."

Switch back to the Orchestrate chat.

**On screen:** the supervisor's answer, showing `Recommendation: escalate`, `Confidence: Medium (3/4)`, the four checks with ❌ on "History fits the claim", and the key evidence bullet points.

**Voice-over:**

> "The agent recommends escalate. Confidence is Medium — three of four checks pass, but the customer's own history conflicts with their claim. The rule is cited. Maria can read the evidence and decide."

---

## 1:10 – 1:40 | Demo A – DSP-0021 (duplicate → approve → draft letter)

**On screen:** in Orchestrate, type `Investigate dispute DSP-0021`.

**Voice-over:**

> "Demo A is clearer: a duplicate coffee shop charge."

**On screen:** the response: `Recommendation: file_chargeback`, `Confidence: High (4/4)`, duplicate TXN-000501 two minutes apart.

**Voice-over:**

> "Four checks pass, High confidence. Same card, same merchant, same amount, two minutes apart — a clear duplicate. Maria types approve."

Type `approve`. Analyst name prompt: type `maria`.

**On screen:** the Letter Writer's draft appears under "Draft letter for your review".

**Voice-over:**

> "The Letter Writer drafts a customer letter. It covers only the duplicate charge, not the original purchase. Maria reviews it here before anything goes to the customer. Switch to the dashboard."

Switch to the dashboard case detail for DSP-0021.

**On screen:** the "Draft Letter for Review" card at the bottom of the case page, with the letter text and chargeback summary.

---

## 1:40 – 2:00 | Demo C – DSP-0049 (too late → deny)

**On screen:** in Orchestrate, type `Investigate dispute DSP-0049`.

**Voice-over:**

> "Demo C: a customer wants to dispute a charge from last spring — 150 days ago."

**On screen:** `Recommendation: deny`, ❌ Within time limits, deadline summary showing both the 120-day and 60-day windows were missed.

**Voice-over:**

> "The deadline check runs in plain code, not AI. It is exact: both the card network limit and the Reg Z notice window were missed. Maria approves the denial, and the agent drafts a letter explaining the time limit and what the customer can do next."

---

## 2:00 – 2:20 | Audit log

**On screen:** click the "Audit Log" tab on the dashboard. Filter by `DSP-0021`.

**Voice-over:**

> "Every tool call and analyst decision is in the audit log. Here is DSP-0021: Intake, Evidence, Compliance, the recommend_outcome call, then Maria's approve decision — timestamped and complete."

---

## 2:20 – 2:45 | Technology

**On screen:** brief slide or the architecture diagram from `docs/architecture.md`.

**Voice-over:**

> "DisputeDesk was built with IBM Bob, which read the whole codebase and built consistent, tested components. The agents run on watsonx Orchestrate with a multi-agent pattern — supervisor and four specialists. Deadlines and decisions are plain Python code, not AI, so they are testable: 121 tests pass, and the recommendation engine matches the 30-case answer key perfectly. The whole system runs locally with a Cloudflare tunnel for the demo, because the lab accounts don't support hosting."

---

## 2:45 – 3:00 | Impact and close

**On screen:** the Overview tab showing the accuracy card and open dispute tiles.

**Voice-over:**

> "DisputeDesk shows how a small AI team can take a repetitive, high-stakes workflow and make it faster, more consistent and fully auditable — without removing the human from any decision. Thank you."

---

*After recording: upload to YouTube as unlisted. Add the link to README.md under a "Demo video" heading.*  
*YouTube link: [to fill]*
