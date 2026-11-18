# DisputeDesk – Problem and Solution Statement

## The problem

Every time a card is used in a dispute, a human analyst must do the same detective work: read a customer's complaint written in their own words, map it to the right Visa reason code from a list of dozens, check whether the dispute was filed within two overlapping time limits (the card network's 120-day window and the 60-day notice requirement under Regulation Z or Regulation E), gather supporting evidence from transaction records and shipment data, and write a decision letter. That work is repetitive but also consequential — a wrong reason code, a missed deadline, or an overlooked refund can cost the bank or the customer money.

A subtler problem is **friendly fraud**: a customer who disputes a purchase they actually made. The signals are in the data — the disputed device and shipping address match purchases the customer made last month, or they have already lost two similar disputes — but reading those signals consistently across dozens of open cases requires pulling data from multiple tables and comparing it in a structured way.

## The user: Maria

Maria is a mid-level dispute analyst at a regional bank. She handles 15–25 disputes a day. She knows Reg Z well but sometimes has to look up the exact deadline arithmetic. She can spot an obvious friendly-fraud case after reviewing the account, but it takes her several minutes per case to pull and read all the evidence. She has no AI tools today — she works in a ticketing system and reads raw transaction exports.

## The solution

DisputeDesk is an AI agent built on IBM watsonx Orchestrate. When Maria opens the analyst dashboard and clicks "Investigate with DisputeDesk", she types one line — `Investigate dispute DSP-0046` — and the system does the following automatically, in order:

1. The **Intake Agent** reads the complaint and the transaction record, identifies reason code 10.4 (card-absent fraud), and returns the key IDs.
2. The **Evidence Investigator** pulls the customer's purchase history and reports friendly-fraud signals: 3 prior undisputed orders at the same merchant using the same device and shipping address.
3. The **Compliance Agent** runs the deadline check in plain code and quotes the relevant Reg Z or Reg E rule.
4. The **supervisor** calls `recommend_outcome`, a plain-code function that applies the written decision rules and returns a recommendation, a confidence score (High / Medium / Low based on 4 named checks), and the key evidence.
5. Maria sees all of that formatted in a single response — recommendation, evidence, rule, confidence — and decides whether to approve, edit or override.
6. If she approves, the **Letter Writer** drafts a customer letter, which appears in the dashboard for her to review before it goes anywhere.

Nothing is sent to the customer automatically. Maria makes every final decision.

## Demo cases

**Demo A – DSP-0021 (duplicate charge, 12.6.1 → file_chargeback)**  
"I was charged twice at a coffee shop. Both charges are $6.50 and I only bought one drink."  
The transaction record shows two $6.50 charges on the same card at the same merchant, two minutes apart. The decision rule is clear: a duplicate within 60 minutes is a chargeback. Confidence: High (4/4). Expected outcome: file_chargeback. After Maria approves, the Letter Writer drafts a letter explaining that a dispute has been opened for the duplicate charge only.

**Demo B – DSP-0046 (friendly fraud, 10.4 → escalate)**  
"I never made this $340 online order. I don't know where this came from."  
The evidence shows the customer has 3 earlier undisputed orders at the same merchant from the same device and address, and has lost 2 prior disputes. The history does not fit the claim. Confidence: Medium (3/4 — history check fails). Expected outcome: escalate to a senior analyst.

**Demo C – DSP-0049 (filed too late, 13.1 → deny)**  
"I want to dispute this charge from last spring. The item never arrived and I forgot to call sooner."  
The transaction is about 150 days before the filing date, which is past the 120-day card network limit and the 60-day Reg Z notice window. The deadline check overrides all other evidence. Expected outcome: deny.

## Results

- Backend recommendation accuracy against the 30-case answer key: **30/30** (verified by `pytest backend/tests/test_recommendation.py`).
- End-to-end agent accuracy through watsonx Orchestrate: **[to fill after evaluation run]**.
- Average case investigation time with DisputeDesk vs without: **[to fill after timed comparison]**.

## What DisputeDesk does not do

- It does not make any decision without a human. The analyst always approves, edits or overrides.
- It does not cover Mastercard disputes or other card networks in this prototype.
- It does not send letters. It drafts them for analyst review.
- It does not use real customer data. All data is synthetic.
