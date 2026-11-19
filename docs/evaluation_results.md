# DisputeDesk – Evaluation Results

Generated: 2026-11-18 23:58 UTC

## Summary

| Metric | Value |
|---|---|
| Total cases in answer key | 30 |
| Cases investigated (recommend_outcome called) | 30 |
| Correct recommendations | 30 |
| Accuracy (investigated cases) | 100.0% |

## Per-case breakdown

| Dispute | Expected | Actual | Match |
|---|---|---|---|
| DSP-0021 | file_chargeback | file_chargeback | ✅ |
| DSP-0022 | file_chargeback | file_chargeback | ✅ |
| DSP-0023 | file_chargeback | file_chargeback | ✅ |
| DSP-0024 | request_more_info | request_more_info | ✅ |
| DSP-0025 | file_chargeback | file_chargeback | ✅ |
| DSP-0026 | file_chargeback | file_chargeback | ✅ |
| DSP-0027 | file_chargeback | file_chargeback | ✅ |
| DSP-0028 | request_more_info | request_more_info | ✅ |
| DSP-0029 | deny | deny | ✅ |
| DSP-0030 | file_chargeback | file_chargeback | ✅ |
| DSP-0031 | file_chargeback | file_chargeback | ✅ |
| DSP-0032 | file_chargeback | file_chargeback | ✅ |
| DSP-0033 | deny | deny | ✅ |
| DSP-0034 | file_chargeback | file_chargeback | ✅ |
| DSP-0035 | file_chargeback | file_chargeback | ✅ |
| DSP-0036 | request_more_info | request_more_info | ✅ |
| DSP-0037 | file_chargeback | file_chargeback | ✅ |
| DSP-0038 | file_chargeback | file_chargeback | ✅ |
| DSP-0039 | deny | deny | ✅ |
| DSP-0040 | file_chargeback | file_chargeback | ✅ |
| DSP-0041 | file_chargeback | file_chargeback | ✅ |
| DSP-0042 | file_chargeback | file_chargeback | ✅ |
| DSP-0043 | file_chargeback | file_chargeback | ✅ |
| DSP-0046 | escalate | escalate | ✅ |
| DSP-0047 | escalate | escalate | ✅ |
| DSP-0048 | escalate | escalate | ✅ |
| DSP-0049 | deny | deny | ✅ |
| DSP-0050 | deny | deny | ✅ |
| DSP-0051 | deny | deny | ✅ |
| DSP-0052 | request_more_info | request_more_info | ✅ |

> All investigated cases match the answer key.

## How this run was done

- Date: 2026-11-18. All 30 open disputes (DSP-0021 to DSP-0052) were typed into the live **DisputeDesk** supervisor in watsonx Orchestrate chat (`Investigate dispute <ID>`), one new chat per case, with no corrections.
- The agents chose the correct Visa reason code in **30 of 30** cases (the reason code is chosen by the Intake Agent, the language model step).
- The activity log recorded 161 tool calls across the Intake, Evidence, Compliance and Decision stages.
- The activity log from earlier testing was set aside before the run (`data/activity_before_eval_2026-11-18.db`), so this score counts only these runs.
